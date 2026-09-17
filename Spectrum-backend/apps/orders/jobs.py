import logging
import os
import shutil
import tempfile
import zipfile

from django.conf import settings
from django.core.files import File
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.text import slugify

from apps.core.tasks import enqueue, job
from spectrum.storages import private_storage

log = logging.getLogger(__name__)


@job("orders.fulfil_order")
def fulfil_order(order_id: str) -> None:
    from apps.catalog.models import EventPhoto
    from apps.core.models import ImageStatus

    from .models import Delivery, Order, OrderItem

    order = Order.objects.get(pk=order_id)
    if order.status not in (Order.PAID, Order.DELIVERED):
        return
    if order.kind == Order.BUNDLE and not order.items.exists():
        ids = EventPhoto.objects.filter(event_id=order.event_id, image_status=ImageStatus.READY).values_list("pk", flat=True)
        OrderItem.objects.bulk_create([OrderItem(order=order, photo_id=pk) for pk in ids.iterator()],
                                      batch_size=500, ignore_conflicts=True)
    channels = ([Delivery.WHATSAPP] if order.deliver_whatsapp else []) + ([Delivery.EMAIL] if order.deliver_email else [])
    for channel in channels:
        delivery, _ = Delivery.objects.get_or_create(order=order, channel=channel)
        if delivery.status == Delivery.PENDING:
            enqueue("orders.send_delivery", delivery.pk)
    count = order.items.count()
    if not order.zip_file and 1 < count <= settings.ORDER_ZIP_MAX_ITEMS:
        enqueue("orders.build_zip", str(order.pk))


@job("orders.send_delivery")
def send_delivery(delivery_id: int) -> None:
    from .models import Delivery, Order
    from .services import twilio_send_whatsapp
    from .views import download_page_url

    delivery = Delivery.objects.select_related("order__event__institution").get(pk=delivery_id)
    if delivery.status in (Delivery.SENT, Delivery.DELIVERED):
        return
    order = delivery.order
    link = download_page_url(order)
    count = order.items.count()
    context = {"order": order, "event": order.event, "count": count, "link": link}
    try:
        if delivery.channel == Delivery.EMAIL:
            message = EmailMultiAlternatives(
                subject=f"Your photos from {order.event.name} are ready",
                body=render_to_string("orders/delivery_email.txt", context),
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[order.email],
            )
            message.attach_alternative(render_to_string("orders/delivery_email.html", context), "text/html")
            message.send()
            message_id = ""
        else:
            body = (f"Hi {order.name}, your {count} photos from {order.event.name} "
                    f"({order.event.institution.name}) are ready. Download them here: {link}")
            message_id = twilio_send_whatsapp(order.phone, {"1": order.event.name, "2": str(count), "3": link}, body)
    except Exception as exc:
        attempts = delivery.attempts + 1
        failed = attempts >= 3
        Delivery.objects.filter(pk=delivery.pk).update(
            attempts=attempts, last_error=str(exc)[:2000], status=Delivery.FAILED if failed else Delivery.PENDING)
        if failed:
            log.error("Delivery %s failed permanently: %s", delivery, exc)
            return
        raise
    Delivery.objects.filter(pk=delivery.pk).update(
        status=Delivery.SENT, attempts=delivery.attempts + 1, sent_at=timezone.now(), last_error="",
        provider_message_id=message_id)
    if not order.deliveries.exclude(status__in=[Delivery.SENT, Delivery.DELIVERED]).exists():
        Order.objects.filter(pk=order.pk, status=Order.PAID).update(status=Order.DELIVERED, delivered_at=timezone.now())


@job("orders.build_zip")
def build_zip(order_id: str) -> None:
    """Streams originals into an uncompressed zip on disk (JPEGs don't compress), then stores it privately."""
    from .models import Order

    order = Order.objects.select_related("event").get(pk=order_id)
    if order.zip_file:
        return
    storage = private_storage()
    rows = order.items.order_by("photo__sort_order", "pk").values_list("pk", "photo__title", "photo__original")
    settings.WORK_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(suffix=".zip", dir=settings.WORK_DIR) as tmp:
        with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
            for pk, title, name in rows.iterator():
                if not name:
                    continue
                ext = os.path.splitext(name)[1] or ".jpg"
                arcname = f"{slugify(title) or 'photo'}-{pk}{ext}"
                with storage.open(name, "rb") as source, archive.open(arcname, "w", force_zip64=True) as target:
                    shutil.copyfileobj(source, target, 1024 * 1024)
        tmp.flush()
        tmp.seek(0)
        saved = storage.save(f"orders/{order.public_id}.zip", File(tmp))
    Order.objects.filter(pk=order.pk).update(zip_file=saved)
