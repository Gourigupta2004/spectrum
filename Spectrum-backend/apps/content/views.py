from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from apps.catalog.models import Event, EventPhoto, Institution
from apps.catalog.serializers import event_list, institution_list
from apps.core.cache import cached_bytes
from apps.core.http import ApiError, api, client_ip, json_response, rate_limit, text
from apps.core.models import ImageStatus, public_url, storage_url
from apps.core.tasks import enqueue

from .models import (
    AboutPage, Capability, ContactDetail, ContactPage, Enquiry, Faq, HeroSlide, HomePage, PortalPage, Service,
    SiteSettings, Stat, StoryBlock, TieUp,
)
from .serializers import copy_of

PAGE_MAX_AGE = 60


def build_site() -> dict:
    site = SiteSettings.load()
    return {
        "logoLight": public_url(site.logo_light),
        "logoMark": public_url(site.logo_mark),
        "favicon": public_url(site.favicon),
        "introVideoWebm": public_url(site.intro_video_webm),
        "introVideoMp4": public_url(site.intro_video_mp4),
        "copy": copy_of(site),
        "seo": {
            "title": site.seo_title,
            "description": site.seo_description,
            "ogTitle": site.og_title,
            "ogDescription": site.og_description,
        },
    }


@api(max_age=PAGE_MAX_AGE)
def site(request):
    return cached_bytes("site", build_site)


def services() -> list[str]:
    return list(Service.objects.values_list("label", flat=True))


def live_counts(sources: set[str]) -> dict[str, int]:
    """What the platform has actually delivered, per Stat.source. Queried only for the sources in use."""
    counts: dict[str, int] = {}
    if Stat.EVENTS in sources:
        counts[Stat.EVENTS] = Event.objects.filter(is_published=True).count()
    if Stat.INSTITUTIONS in sources:
        counts[Stat.INSTITUTIONS] = Institution.objects.filter(is_published=True).count()
    if Stat.PHOTOS in sources:
        from apps.orders.models import Order, OrderItem

        paid = (Order.PAID, Order.DELIVERED)
        singles = OrderItem.objects.filter(order__status__in=paid).count()
        # A bundle order has no items; it delivers every photo of its event.
        bundles = EventPhoto.objects.filter(event__orders__status__in=paid,
                                            event__orders__kind=Order.BUNDLE).count()
        counts[Stat.PHOTOS] = singles + bundles
    return counts


def build_home() -> dict:
    page = HomePage.load()
    slides = HeroSlide.objects.filter(image_status=ImageStatus.READY).values_list("pk", "caption", "web")
    stats = list(Stat.objects.values_list("value", "suffix", "label", "source"))
    counts = live_counts({source for *_, source in stats if source})
    return {
        "seo": page.seo(),
        "copy": copy_of(page),
        "heroSlides": [{"id": pk, "src": storage_url(web), "caption": caption} for pk, caption, web in slides],
        "stats": [{"to": value + counts.get(source, 0), "suffix": suffix, "label": label}
                  for value, suffix, label, source in stats],
        "services": services(),
        "institutions": institution_list(),
        "events": event_list(limit=page.featured_count),
    }


@api(max_age=PAGE_MAX_AGE)
def home(request):
    return cached_bytes("home", build_home)


def build_about() -> dict:
    page = AboutPage.load()
    return {
        "seo": page.seo(),
        "copy": copy_of(page),
        "capabilities": list(Capability.objects.values_list("label", flat=True)),
        "story": [
            {"title": title, "body": body, "alt": alt, "image": storage_url(web)}
            for title, body, alt, web in StoryBlock.objects.values_list("title", "body", "alt", "web")
        ],
        "tieUps": [
            {"name": name, "years": years, "image": storage_url(web)}
            for name, years, web in TieUp.objects.values_list("name", "years", "web")
        ],
        "faqs": [{"q": q, "a": a} for q, a in Faq.objects.values_list("question", "answer")],
    }


@api(max_age=PAGE_MAX_AGE)
def about(request):
    return cached_bytes("about", build_about)


def build_contact() -> dict:
    page = ContactPage.load()
    return {
        "seo": page.seo(),
        "copy": copy_of(page),
        "services": services(),
        "details": [
            {"icon": icon, "label": label, "value": value}
            for icon, label, value in ContactDetail.objects.values_list("icon", "label", "value")
        ],
    }


@api(max_age=PAGE_MAX_AGE)
def contact_page(request):
    return cached_bytes("contact", build_contact)


@api(max_age=PAGE_MAX_AGE)
def portal_page(request):
    return cached_bytes("portal-copy", lambda: {"copy": copy_of(PortalPage.load())})


@api(methods=("POST",))
def contact_submit(request):
    rate_limit(request, "contact", limit=5, window=600)
    data = request.json
    name = text(data, "name", 120, required=True)
    email = text(data, "email", 254)
    phone = text(data, "phone", 30)
    if not email and not phone:
        raise ApiError("Please add an email address or phone number.", field="email")
    if email:
        try:
            validate_email(email)
        except ValidationError:
            raise ApiError("Please check the email address.", field="email")
    service = text(data, "service", 160)
    other = text(data, "serviceOther", 160)
    if other:
        service = f"{service}: {other}" if service else other
    enquiry = Enquiry.objects.create(
        name=name,
        email=email,
        phone=phone,
        institution=text(data, "institution", 160),
        service=service,
        message=text(data, "message", 5000),
        ip=client_ip(request) or None,
    )
    if settings.ENQUIRY_NOTIFY_EMAILS:
        enqueue("content.notify_enquiry", enquiry.pk)
    return json_response({"ok": True}, status=201)
