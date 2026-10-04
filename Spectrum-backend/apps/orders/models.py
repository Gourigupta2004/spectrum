import secrets
import uuid

from django.db import models

from spectrum.storages import private_storage


def public_id() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "SP" + "".join(secrets.choice(alphabet) for _ in range(8))


def download_token() -> str:
    return secrets.token_urlsafe(32)


class Order(models.Model):
    CREATED, PAID, FAILED, DELIVERED, REFUNDED = "created", "paid", "failed", "delivered", "refunded"
    STATUSES = [(CREATED, "Awaiting payment"), (PAID, "Paid"), (FAILED, "Payment failed"),
                (DELIVERED, "Delivered"), (REFUNDED, "Refunded")]
    PHOTOS, BUNDLE = "photos", "bundle"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    public_id = models.CharField("order no.", max_length=12, unique=True, default=public_id, editable=False)
    event = models.ForeignKey("catalog.Event", on_delete=models.PROTECT, related_name="orders")
    kind = models.CharField(max_length=10, choices=[(PHOTOS, "Selected photos"), (BUNDLE, "Full album")])
    name = models.CharField(max_length=120)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    deliver_whatsapp = models.BooleanField(default=True)
    deliver_email = models.BooleanField(default=False)
    amount_paise = models.PositiveIntegerField()
    currency = models.CharField(max_length=3, default="INR")
    status = models.CharField(max_length=10, choices=STATUSES, default=CREATED, db_index=True)
    razorpay_order_id = models.CharField(max_length=40, unique=True, null=True, blank=True)
    idempotency_key = models.CharField(max_length=64, unique=True, null=True, blank=True)
    download_token = models.CharField(max_length=64, unique=True, default=download_token, editable=False)
    zip_file = models.FileField(storage=private_storage, max_length=255, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.public_id

    @property
    def amount(self) -> int:
        return self.amount_paise // 100


class OrderItem(models.Model):
    """One purchased photo or video — exactly one of the two is set."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    photo = models.ForeignKey("catalog.EventPhoto", on_delete=models.PROTECT, related_name="+",
                              null=True, blank=True)
    video = models.ForeignKey("catalog.EventVideo", on_delete=models.PROTECT, related_name="+",
                              null=True, blank=True)
    unit_price_paise = models.PositiveIntegerField(default=0)
    video_used_at = models.DateTimeField(null=True, blank=True,
                                         help_text="Video links are one-time; set when the download is taken.")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["order", "photo"], name="uniq_order_photo"),
            models.UniqueConstraint(fields=["order", "video"], name="uniq_order_video"),
            models.CheckConstraint(
                condition=(models.Q(photo__isnull=False, video__isnull=True)
                           | models.Q(photo__isnull=True, video__isnull=False)),
                name="orderitem_photo_or_video"),
        ]

    @property
    def media(self):
        return self.photo if self.photo_id else self.video


class Payment(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="payments")
    razorpay_payment_id = models.CharField(max_length=40, unique=True)
    method = models.CharField(max_length=30, blank=True)
    amount_paise = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, default="captured")
    verified_via = models.CharField(max_length=10, choices=[("client", "Checkout"), ("webhook", "Webhook"),
                                                            ("mock", "Test mode")])
    created_at = models.DateTimeField(auto_now_add=True)


class WebhookEvent(models.Model):
    provider = models.CharField(max_length=20)
    event_id = models.CharField(max_length=80)
    event_type = models.CharField(max_length=60, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["provider", "event_id"], name="uniq_webhook_event")]


class Delivery(models.Model):
    EMAIL, WHATSAPP = "email", "whatsapp"
    PENDING, SENT, DELIVERED, FAILED = "pending", "sent", "delivered", "failed"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="deliveries")
    channel = models.CharField(max_length=10, choices=[(EMAIL, "Email"), (WHATSAPP, "WhatsApp")])
    status = models.CharField(max_length=10, default=PENDING, db_index=True, choices=[
        (PENDING, "Pending"), (SENT, "Sent"), (DELIVERED, "Delivered"), (FAILED, "Failed")])
    attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.TextField(blank=True)
    provider_message_id = models.CharField(max_length=64, blank=True, db_index=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["order", "channel"], name="uniq_delivery_channel")]
        verbose_name_plural = "deliveries"

    def __str__(self):
        return f"{self.order} · {self.get_channel_display()}"
