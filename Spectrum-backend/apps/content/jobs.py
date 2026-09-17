from django.conf import settings
from django.core.mail import send_mail

from apps.core.tasks import job


@job("content.notify_enquiry")
def notify_enquiry(enquiry_id: int) -> None:
    from .models import Enquiry

    enquiry = Enquiry.objects.filter(pk=enquiry_id).first()
    if enquiry is None or not settings.ENQUIRY_NOTIFY_EMAILS:
        return
    body = "\n".join([
        f"Name: {enquiry.name}",
        f"Email: {enquiry.email}",
        f"Phone: {enquiry.phone}",
        f"Institution: {enquiry.institution}",
        f"Service: {enquiry.service}",
        "",
        enquiry.message,
        "",
        f"{settings.API_URL}/admin/content/enquiry/{enquiry.pk}/change/",
    ])
    send_mail(f"New enquiry from {enquiry.name}", body, settings.DEFAULT_FROM_EMAIL, settings.ENQUIRY_NOTIFY_EMAILS)
