from apps.content.models import EventsPage, GalleryPage
from apps.content.serializers import copy_of
from apps.core.cache import cached_bytes
from apps.core.http import ApiError, api

from .serializers import bundle_savings, event_dict, event_list, event_queryset, gallery, institution_list, kind_list

MAX_AGE = 60


def build_events() -> dict:
    page = EventsPage.load()
    return {"seo": page.seo(), "copy": copy_of(page), "types": kind_list(), "events": event_list(),
            "institutions": institution_list()}


@api(max_age=MAX_AGE)
def events(request):
    return cached_bytes("events", build_events)


class _NotFound(Exception):
    pass


def build_event(slug: str) -> dict:
    event = event_queryset().filter(slug=slug).first()
    if event is None:
        raise _NotFound
    data = event_dict(event)
    data["bundleSavings"] = bundle_savings(data["photos"], event.price_per_photo, event.bundle_price)
    page = GalleryPage.load()
    fill = {"event": event.name, "institution": event.institution.name}
    return {
        "event": data,
        "photos": gallery(event.pk),
        "seo": {
            "title": page.seo_title_template.format_map(_Safe(fill)),
            "description": page.seo_description_template.format_map(_Safe(fill)),
        },
        "copy": copy_of(page),
    }


class _Safe(dict):
    def __missing__(self, key):
        return "{" + key + "}"


@api(max_age=MAX_AGE)
def event_detail(request, slug):
    try:
        return cached_bytes(f"event:{slug}", lambda: build_event(slug))
    except _NotFound:
        raise ApiError("Event not found", status=404)
