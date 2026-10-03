import hashlib
import json
import logging
import os

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.http import FileResponse, HttpResponse, HttpResponseRedirect
from django.utils.text import slugify
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.catalog.models import Event, EventPhoto
from apps.core.http import ApiError, api, rate_limit, text
from apps.core.models import ImageStatus, storage_url
from spectrum.storages import private_storage

from .models import Delivery, Order, OrderItem, WebhookEvent
from .services import (
    ProviderError, mark_paid, normalise_phone, razorpay_create_order, verify_checkout_signature,
    verify_twilio_signature, verify_webhook_signature,
)

log = logging.getLogger(__name__)
PAID_STATES = (Order.PAID, Order.DELIVERED)


def download_page_url(order: Order) -> str:
    return f"{settings.SITE_URL}/downloads/{order.download_token}"


def order_payload(order: Order) -> dict:
    paid = order.status in PAID_STATES
    return {
        "id": str(order.pk),
        "publicId": order.public_id,
        "status": order.status,
        "amount": order.amount,
        "amountPaise": order.amount_paise,
        "currency": order.currency,
        "deliverVia": "whatsapp" if order.deliver_whatsapp else "email",
        "mock": settings.PAYMENTS_MOCK,
        "razorpay": {"keyId": settings.RAZORPAY_KEY_ID, "orderId": order.razorpay_order_id}
        if order.razorpay_order_id else None,
        "prefill": {"name": order.name, "email": order.email, "contact": order.phone},
        "downloadUrl": download_page_url(order) if paid else None,
        "downloadToken": order.download_token if paid else None,
    }


@api(methods=("POST",))
def create_order(request):
    rate_limit(request, "orders", limit=20, window=600)
    data = request.json
    raw_ids = data.get("photoIds") or []
    if not isinstance(raw_ids, list):
        raise ApiError("photoIds must be a list.")
    client_key = text(data, "idempotencyKey", 64)
    idempotency_key = None
    if len(client_key) >= 16:
        # Bound to the basket and contact, so a guessed key never returns someone else's order.
        basket = "|".join([client_key, text(data, "eventSlug", 120), str(bool(data.get("bundle"))),
                           ",".join(sorted(str(x) for x in raw_ids)), text(data, "phone", 30), text(data, "email", 254)])
        idempotency_key = hashlib.sha256(basket.encode()).hexdigest()
        existing = Order.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            return order_payload(existing)

    event = Event.objects.filter(slug=text(data, "eventSlug", 120), is_published=True).first()
    if event is None:
        raise ApiError("Event not found", status=404)
    name = text(data, "name", 120, required=True)
    email = text(data, "email", 254)
    phone = normalise_phone(text(data, "phone", 30))
    via = "email" if data.get("deliverVia") == "email" else "whatsapp"
    if via == "whatsapp" and not phone:
        raise ApiError("Please enter a valid WhatsApp number.", field="phone")
    if email:
        try:
            validate_email(email)
        except ValidationError:
            raise ApiError("Please check the email address.", field="email")
    if via == "email" and not email:
        raise ApiError("Please enter your email address.", field="email")

    photos = EventPhoto.objects.filter(event=event, image_status=ImageStatus.READY)
    bundle = bool(data.get("bundle"))
    if bundle:
        if not photos.exists():
            raise ApiError("This album has no photos yet.")
        photo_ids, amount = [], event.bundle_price * 100
    else:
        requested = {int(x) for x in raw_ids[:2000] if str(x).isdigit()}
        photo_ids = list(photos.filter(pk__in=requested).values_list("pk", flat=True))
        if not photo_ids:
            raise ApiError("Select at least one photo.")
        amount = len(photo_ids) * event.price_per_photo * 100
    if amount <= 0:
        raise ApiError("This order has no amount to pay.")

    try:
        with transaction.atomic():
            order = Order.objects.create(
                event=event, kind=Order.BUNDLE if bundle else Order.PHOTOS, name=name, email=email, phone=phone,
                deliver_whatsapp=via == "whatsapp", deliver_email=via == "email" or bool(email),
                amount_paise=amount, idempotency_key=idempotency_key,
            )
            OrderItem.objects.bulk_create(
                [OrderItem(order=order, photo_id=pk, unit_price_paise=event.price_per_photo * 100) for pk in photo_ids],
                batch_size=500,
            )
    except IntegrityError:
        existing = Order.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            return order_payload(existing)
        raise

    if not settings.PAYMENTS_MOCK:
        try:
            order.razorpay_order_id = razorpay_create_order(order)
        except ProviderError as exc:
            log.error("Razorpay order failed for %s: %s", order, exc)
            order.status = Order.FAILED
            order.save(update_fields=["status"])
            raise ApiError("Payment could not be started. Please try again.", status=502)
        order.save(update_fields=["razorpay_order_id"])
    return order_payload(order)


def _order(order_id) -> Order:
    order = Order.objects.filter(pk=order_id).first()
    if order is None:
        raise ApiError("Order not found", status=404)
    return order


@api(methods=("POST",))
def verify_order(request, order_id):
    order = _order(order_id)
    data = request.json
    if settings.PAYMENTS_MOCK:
        if not data.get("mock"):
            raise ApiError("Payments are in test mode.")
        order = mark_paid(order.pk, f"mock_{order.public_id}", via="mock")
        return order_payload(order)
    payment_id = text(data, "razorpayPaymentId", 40)
    signature = text(data, "razorpaySignature", 128)
    if text(data, "razorpayOrderId", 40) != order.razorpay_order_id or not verify_checkout_signature(
        order.razorpay_order_id or "", payment_id, signature
    ):
        raise ApiError("Payment could not be verified.", status=400)
    try:
        order = mark_paid(order.pk, payment_id, via="client")
    except ProviderError as exc:
        log.error("%s", exc)
        raise ApiError("Payment could not be verified.", status=400)
    return order_payload(order)


@api()
def order_status(request, order_id):
    return order_payload(_order(order_id))


@csrf_exempt
@require_POST
def razorpay_webhook(request):
    body = request.body
    if not verify_webhook_signature(body, request.headers.get("X-Razorpay-Signature", "")):
        return HttpResponse(status=400)
    try:
        data = json.loads(body)
    except ValueError:
        return HttpResponse(status=400)
    event_type = data.get("event", "")
    event_id = request.headers.get("X-Razorpay-Event-Id") or hashlib.sha256(body).hexdigest()[:64]
    payment = ((data.get("payload") or {}).get("payment") or {}).get("entity") or {}
    try:
        # One transaction: if handling fails, the dedupe row rolls back too and
        # Razorpay's retry is processed instead of being ignored.
        with transaction.atomic():
            WebhookEvent.objects.create(provider="razorpay", event_id=event_id, event_type=event_type)
            order = Order.objects.filter(razorpay_order_id=payment.get("order_id")).first() if payment else None
            if order is not None and event_type in ("payment.captured", "order.paid"):
                try:
                    mark_paid(order.pk, payment["id"], via="webhook",
                              amount_paise=int(payment.get("amount") or 0), method=payment.get("method", ""))
                except ProviderError as exc:
                    log.error("Webhook for %s rejected: %s", order, exc)
            elif order is not None and event_type == "payment.failed":
                Order.objects.filter(pk=order.pk, status=Order.CREATED).update(status=Order.FAILED)
    except IntegrityError:
        return HttpResponse(status=200)  # already handled
    return HttpResponse(status=200)


TWILIO_STATUS = {"delivered": Delivery.DELIVERED, "read": Delivery.DELIVERED, "failed": Delivery.FAILED,
                 "undelivered": Delivery.FAILED}


@csrf_exempt
@require_POST
def twilio_webhook(request):
    params = {key: request.POST.get(key) for key in request.POST}
    url = f"{settings.API_URL}{request.get_full_path()}"
    if not verify_twilio_signature(url, params, request.headers.get("X-Twilio-Signature", "")):
        return HttpResponse(status=403)
    status = TWILIO_STATUS.get(params.get("MessageStatus", ""))
    sid = params.get("MessageSid", "")
    if status and sid:
        updates = {"status": status}
        if status == Delivery.FAILED:
            updates["last_error"] = f"Twilio error {params.get('ErrorCode', '')}"
        Delivery.objects.filter(provider_message_id=sid).update(**updates)
    return HttpResponse(status=204)


def _paid_order(token: str) -> Order:
    order = (Order.objects.select_related("event__institution")
             .filter(download_token=token, status__in=PAID_STATES).first())
    if order is None:
        raise ApiError("This download link is not valid.", status=404)
    return order


@api()
def download(request, token):
    order = _paid_order(token)
    base = f"{settings.API_URL}/api/downloads/{token}"
    rows = order.items.order_by("photo__sort_order", "pk").values_list("pk", "photo__title", "photo__thumb")
    items = [{"id": pk, "title": title, "thumb": storage_url(thumb), "url": f"{base}/photos/{pk}/"}
             for pk, title, thumb in rows]
    return {
        "publicId": order.public_id,
        "event": {"name": order.event.name, "institution": order.event.institution.name},
        "items": items,
        "zipUrl": f"{base}/zip/" if order.zip_file else None,
        "preparing": not items,
    }


def _serve_private(name: str, filename: str):
    storage = private_storage()
    if hasattr(storage, "bucket_name"):
        url = storage.url(name, parameters={"ResponseContentDisposition": f'attachment; filename="{filename}"'},
                          expire=settings.PRIVATE_URL_EXPIRE)
        return HttpResponseRedirect(url)
    if settings.PRIVATE_ACCEL_PREFIX:
        # nginx streams the file itself; the Django thread is freed immediately.
        response = HttpResponse()
        response["X-Accel-Redirect"] = f"{settings.PRIVATE_ACCEL_PREFIX}{name}"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response["Content-Type"] = ""
        return response
    return FileResponse(storage.open(name, "rb"), as_attachment=True, filename=filename)


def download_photo(request, token, item_id):
    try:
        order = _paid_order(token)
    except ApiError:
        return HttpResponse("This download link is not valid.", status=404)
    item = order.items.select_related("photo").only("pk", "photo__title", "photo__original").filter(pk=item_id).first()
    if item is None or not item.photo.original:
        return HttpResponse("Not found", status=404)
    ext = os.path.splitext(item.photo.original.name)[1] or ".jpg"
    filename = f"{slugify(item.photo.title) or 'photo'}-{item.pk}{ext}"
    return _serve_private(item.photo.original.name, filename)


def download_zip(request, token):
    try:
        order = _paid_order(token)
    except ApiError:
        return HttpResponse("This download link is not valid.", status=404)
    if not order.zip_file:
        return HttpResponse("The zip file is still being prepared.", status=404)
    return _serve_private(order.zip_file.name, f"{slugify(order.event.name)}-{order.public_id}.zip")
