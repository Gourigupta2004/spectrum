"""
ID card services. Duplicate ID cards come first: a student's details, the
institution's price, and a Razorpay payment. Later ID card services belong here too.
"""

import secrets
import uuid

from django.db import models


def request_number() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "ID" + "".join(secrets.choice(alphabet) for _ in range(8))


class DuplicateIdCardRequest(models.Model):
    CREATED, PAID, FAILED = "created", "paid", "failed"
    STATUSES = [(CREATED, "Awaiting payment"), (PAID, "Paid"), (FAILED, "Payment failed")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    public_id = models.CharField("request no.", max_length=12, unique=True, default=request_number, editable=False)
    institution = models.ForeignKey("catalog.Institution", on_delete=models.PROTECT,
                                    related_name="duplicate_id_card_requests", verbose_name="school name/branch")
    student_name = models.CharField("name", max_length=120)
    class_name = models.CharField("class", max_length=40)
    admission_no = models.CharField("admission no.", max_length=40)
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
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "duplicate ID card request"
        verbose_name_plural = "duplicate ID card"  # the admin table's name

    def __str__(self):
        return self.public_id

    @property
    def amount(self) -> int:
        return self.amount_paise // 100
