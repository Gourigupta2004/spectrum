import mimetypes
import os

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

from apps.core.tasks import job


@job("idcards.email_receipt")
def email_receipt(request_id: str) -> None:
    """Emails the shipment receipt to the requester, attached, from the same
    mailbox as photo deliveries. A failure is retried, then shows under
    System › Background tasks."""
    from .models import DuplicateIdCardRequest

    card = DuplicateIdCardRequest.objects.select_related("institution").filter(pk=request_id).first()
    if card is None or not card.shipment_receipt:
        return
    context = {"card": card}
    message = EmailMultiAlternatives(
        subject=f"Your duplicate ID card has been shipped ({card.public_id})",
        body=render_to_string("idcards/receipt_email.txt", context),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[card.email],
    )
    message.attach_alternative(render_to_string("idcards/receipt_email.html", context), "text/html")
    name = card.shipment_receipt.name
    ext = os.path.splitext(name)[1].lower()
    with card.shipment_receipt.open("rb") as receipt:
        message.attach(f"shipment-receipt-{card.public_id}{ext}", receipt.read(),
                       mimetypes.guess_type(name)[0] or "application/octet-stream")
    message.send()
    # Only if the receipt is still the one just sent (it may have been replaced meanwhile).
    DuplicateIdCardRequest.objects.filter(pk=card.pk, shipment_receipt=name).update(
        receipt_emailed_at=timezone.now())
