import hashlib
import logging

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError

from apps.catalog.models import Institution
from apps.content.models import IdCardPage
from apps.content.serializers import copy_of
from apps.core.cache import cached_bytes
from apps.core.http import ApiError, api, rate_limit, text
from apps.orders.services import ProviderError, normalise_phone, razorpay_create_order, verify_checkout_signature

from .models import DuplicateIdCardRequest
from .services import mark_paid

log = logging.getLogger(__name__)
PAGE_MAX_AGE = 60


def offering():
    """Institutions that offer duplicate ID cards. Listed whether or not their events are published."""
    return Institution.objects.filter(offers_duplicate_id_cards=True, duplicate_id_card_price__gt=0)


def build_page() -> dict:
    page = IdCardPage.load()
    return {
        "seo": page.seo(),
        "copy": copy_of(page),
        "institutions": [{"id": slug, "name": name, "price": price} for slug, name, price in
                         offering().values_list("slug", "name", "duplicate_id_card_price")],
    }


@api(max_age=PAGE_MAX_AGE)
def page(request):
    return cached_bytes("id-card", build_page)


def request_payload(card: DuplicateIdCardRequest) -> dict:
    return {
        "id": str(card.pk),
        "publicId": card.public_id,
        "status": card.status,
        "amount": card.amount,
        "amountPaise": card.amount_paise,
        "currency": card.currency,
        "mock": settings.PAYMENTS_MOCK,
        "razorpay": {"keyId": settings.RAZORPAY_KEY_ID, "orderId": card.razorpay_order_id}
        if card.razorpay_order_id else None,
        "prefill": {"name": card.student_name, "email": card.email, "contact": card.phone},
        "paid": card.status == DuplicateIdCardRequest.PAID,
    }


@api(methods=("POST",))
def create_duplicate(request):
    rate_limit(request, "idcards", limit=20, window=600)
    data = request.json
    fields = {
        "institution": text(data, "institutionId", 50),
        "student_name": text(data, "studentName", 120),
        "class_name": text(data, "className", 40),
        "admission_no": text(data, "admissionNo", 40),
        "email": text(data, "email", 254),
        "phone": text(data, "phone", 30),
    }
    client_key = text(data, "idempotencyKey", 64)
    idempotency_key = None
    if len(client_key) >= 16:
        # Bound to every detail, so a guessed key never returns someone else's request.
        idempotency_key = hashlib.sha256("|".join([client_key, *fields.values()]).encode()).hexdigest()
        existing = DuplicateIdCardRequest.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            return request_payload(existing)

    institution = offering().filter(slug=fields["institution"]).first()
    if institution is None:
        raise ApiError("Please choose your school.", field="institutionId")
    for key, label in (("student_name", "studentName"), ("class_name", "className"),
                       ("admission_no", "admissionNo"), ("email", "email"), ("phone", "phone")):
        if not fields[key]:
            raise ApiError("Please fill in every field.", field=label)
    try:
        validate_email(fields["email"])
    except ValidationError:
        raise ApiError("Please check the email address.", field="email")
    phone = normalise_phone(fields["phone"])
    if not phone:
        raise ApiError("Please enter a valid phone number.", field="phone")

    try:
        card = DuplicateIdCardRequest.objects.create(
            institution=institution, student_name=fields["student_name"], class_name=fields["class_name"],
            admission_no=fields["admission_no"], email=fields["email"], phone=phone,
            amount_paise=institution.duplicate_id_card_price * 100, idempotency_key=idempotency_key,
        )
    except IntegrityError:
        existing = DuplicateIdCardRequest.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            return request_payload(existing)
        raise

    if not settings.PAYMENTS_MOCK:
        try:
            card.razorpay_order_id = razorpay_create_order(card)
        except ProviderError as exc:
            log.error("Razorpay order failed for %s: %s", card, exc)
            card.status = DuplicateIdCardRequest.FAILED
            card.save(update_fields=["status"])
            raise ApiError("Payment could not be started. Please try again.", status=502)
        card.save(update_fields=["razorpay_order_id"])
    return request_payload(card)


@api(methods=("POST",))
def verify_duplicate(request, request_id):
    card = DuplicateIdCardRequest.objects.filter(pk=request_id).first()
    if card is None:
        raise ApiError("Request not found", status=404)
    data = request.json
    if settings.PAYMENTS_MOCK:
        if not data.get("mock"):
            raise ApiError("Payments are in test mode.")
        return request_payload(mark_paid(card.pk, f"mock_{card.public_id}", via="mock"))
    payment_id = text(data, "razorpayPaymentId", 40)
    signature = text(data, "razorpaySignature", 128)
    if text(data, "razorpayOrderId", 40) != card.razorpay_order_id or not verify_checkout_signature(
        card.razorpay_order_id or "", payment_id, signature
    ):
        raise ApiError("Payment could not be verified.", status=400)
    return request_payload(mark_paid(card.pk, payment_id, via="client"))
