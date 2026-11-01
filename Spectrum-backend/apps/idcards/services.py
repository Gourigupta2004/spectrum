from django.db import transaction
from django.utils import timezone

from apps.orders.services import ProviderError

from .models import DuplicateIdCardRequest


def mark_paid(request_id, payment_id: str, *, via: str, amount_paise: int = 0) -> DuplicateIdCardRequest:
    """The single place a request becomes paid. Safe to call twice (checkout and webhook)."""
    with transaction.atomic():
        card = DuplicateIdCardRequest.objects.select_for_update().get(pk=request_id)
        if card.status == DuplicateIdCardRequest.PAID:
            return card
        if amount_paise and amount_paise != card.amount_paise:
            raise ProviderError(f"Amount mismatch for {card}: {amount_paise} != {card.amount_paise}")
        card.status = DuplicateIdCardRequest.PAID
        card.razorpay_payment_id = payment_id
        card.paid_via = via
        card.paid_at = timezone.now()
        card.save(update_fields=["status", "razorpay_payment_id", "paid_via", "paid_at"])
    return card


def handle_razorpay_event(event_type: str, payment: dict) -> bool:
    """A Razorpay webhook for one of these requests. False when the payment isn't for one."""
    card = DuplicateIdCardRequest.objects.filter(razorpay_order_id=payment.get("order_id")).first()
    if card is None:
        return False
    if event_type in ("payment.captured", "order.paid"):
        mark_paid(card.pk, payment["id"], via="webhook", amount_paise=int(payment.get("amount") or 0))
    elif event_type == "payment.failed":
        DuplicateIdCardRequest.objects.filter(pk=card.pk, status=DuplicateIdCardRequest.CREATED).update(
            status=DuplicateIdCardRequest.FAILED)
    return True
