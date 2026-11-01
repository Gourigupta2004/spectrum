"""
ID card services. Duplicate ID cards come first: a student's details, the
institution's price, and a Razorpay payment. Later ID card services belong here too.
"""

import os
import secrets
import uuid

from django.core.exceptions import ValidationError
from django.db import models

from spectrum.storages import private_storage

RECEIPT_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".webp"}
RECEIPT_MAX_MB = 10  # it goes out as an email attachment


def validate_receipt(value):
    ext = os.path.splitext(value.name)[1].lower()
    if ext not in RECEIPT_EXTENSIONS:
        raise ValidationError("Upload the receipt as a PDF, JPG, PNG or WebP.")
    if value.size > RECEIPT_MAX_MB * 1024 * 1024:
        raise ValidationError(f"The receipt must be under {RECEIPT_MAX_MB} MB, so it can be emailed.")


def receipt_upload_to(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    return f"idcards/receipts/{instance.public_id}-{uuid.uuid4().hex[:8]}{ext}"


def request_number() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "ID" + "".join(secrets.choice(alphabet) for _ in range(8))


class DuplicateIdCardRequest(models.Model):
    CREATED, PAID, SHIPPED, FAILED = "created", "paid", "shipped", "failed"
    STATUSES = [(CREATED, "Awaiting payment"), (PAID, "Paid"), (SHIPPED, "Shipped"), (FAILED, "Payment failed")]
    PAID_STATES = (PAID, SHIPPED)

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    public_id = models.CharField("request no.", max_length=12, unique=True, default=request_number, editable=False)
    institution = models.ForeignKey("catalog.Institution", on_delete=models.PROTECT,
                                    related_name="duplicate_id_card_requests", verbose_name="school name/branch")
    student_name = models.CharField("name", max_length=120)
    class_name = models.CharField("class", max_length=40)
    admission_no = models.CharField("admission no.", max_length=40)
    # The chosen labels, as they read then (renaming a choice later never changes a request).
    card_type = models.CharField("type of card", max_length=60, blank=True)
    lanyard_colour = models.CharField("color of lanyard", max_length=60, blank=True)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    # The institution's price when the request was made; changing it later never reprices a request.
    amount_paise = models.PositiveIntegerField()
    currency = models.CharField(max_length=3, default="INR")
    status = models.CharField(max_length=10, choices=STATUSES, default=CREATED, db_index=True)
    razorpay_order_id = models.CharField(max_length=40, unique=True, null=True, blank=True)
    razorpay_payment_id = models.CharField(max_length=40, blank=True)
    paid_via = models.CharField(max_length=10, blank=True, choices=[("client", "Checkout"), ("webhook", "Webhook"),
                                                                     ("mock", "Test mode")])
    idempotency_key = models.CharField(max_length=64, unique=True, null=True, blank=True)
    handled = models.BooleanField("done", default=False, db_index=True,
                                  help_text="Tick once the duplicate card has been made.")
    # Uploading it marks a paid request Shipped and emails it to the requester.
    shipment_receipt = models.FileField(
        "shipment receipt", storage=private_storage, upload_to=receipt_upload_to, max_length=255, blank=True,
        validators=[validate_receipt],
        help_text=f"PDF or photo, under {RECEIPT_MAX_MB} MB. Saving it marks the request Shipped and emails it "
                  "to the requester.")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    receipt_emailed_at = models.DateTimeField("receipt emailed", null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "duplicate ID card request"
        verbose_name_plural = "duplicate ID card"  # the admin table's name

    def __str__(self):
        return self.public_id

    def clean(self):
        super().clean()
        if self.shipment_receipt and self.status not in self.PAID_STATES:
            raise ValidationError({"shipment_receipt": "Only a paid request can be shipped."})

    @property
    def amount(self) -> int:
        return self.amount_paise // 100
