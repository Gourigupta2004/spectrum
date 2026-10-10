from django.db.models import Count, OuterRef, Q, Subquery

from apps.core.models import ImageStatus, public_url

from .models import Event, EventPhoto, EventVideo, Institution, InstitutionKind

EVENT_FIELDS = (
    "slug", "name", "date", "date_label", "price_per_photo", "price_per_video", "bundle_price",
    "is_recent", "is_popular", "web", "institution__slug", "institution__name", "institution__kind__slug",
)


def published_events():
    return Event.objects.filter(is_published=True, institution__is_published=True)


def event_queryset():
    return (
        published_events()
        .select_related("institution__kind")
        .only(*EVENT_FIELDS)
        .order_by("sort_order", "-date", "pk")
        .annotate(photo_count=Count("photos", filter=Q(photos__image_status=ImageStatus.READY), distinct=True),
                  video_count=Count("videos", filter=~Q(videos__video=""), distinct=True))
    )


def event_dict(event) -> dict:
    return {
        "slug": event.slug,
        "name": event.name,
        "institutionId": event.institution.slug,
        "institution": event.institution.name,
        "institutionType": event.institution.kind.slug,
        "date": event.display_date,
        "photos": event.photo_count,
        "videos": event.video_count,
        "pricePerPhoto": event.price_per_photo,
        "pricePerVideo": event.price_per_video,
        "bundlePrice": event.bundle_price,
        "notForSale": event.not_for_sale,
        "image": public_url(event.web),
        "tags": event.tags,
    }


def event_list(limit: int | None = None) -> list[dict]:
    queryset = event_queryset()
    if limit:
        queryset = queryset[:limit]
    return [event_dict(event) for event in queryset]


def institution_list() -> list[dict]:
    first_event = published_events().filter(institution=OuterRef("pk")).order_by("sort_order", "-date", "pk")
    queryset = (
        Institution.objects.filter(is_published=True)
        .select_related("kind")
        .only("slug", "name", "short", "city", "web", "kind__slug")
        .order_by("sort_order", "name")
        .annotate(
            event_count=Count("events", filter=Q(events__is_published=True)),
            first_event_slug=Subquery(first_event.values("slug")[:1]),
        )
    )
    return [
        {
            "id": inst.slug,
            "name": inst.name,
            "short": inst.short or inst.name,
            "city": inst.city,
            "type": inst.kind.slug,
            "image": public_url(inst.web),
            "eventCount": inst.event_count,
            "firstEventSlug": inst.first_event_slug,
        }
        for inst in queryset
    ]


def kind_list() -> list[dict]:
    """The filter chips the events page shows between "All" and "Recent"."""
    return [{"id": slug, "label": plural}
            for slug, plural in InstitutionKind.objects.values_list("slug", "plural")]


def bundle_savings(photos: int, price_per_photo: int, bundle_price: int) -> int:
    full = photos * price_per_photo
    if full <= 0:
        return 0
    return max(0, round((1 - bundle_price / full) * 100))


def gallery(event_id: int) -> list[dict]:
    rows = (
        EventPhoto.objects.filter(event_id=event_id, image_status=ImageStatus.READY)
        .order_by("sort_order", "pk")
        .values_list("pk", "title", "preview", "thumb", "width", "height")
    )
    from apps.core.models import storage_url

    # Width and height travel with every photo so the site can lay each one out
    # at its own proportions instead of forcing a frame on it.
    return [
        {"id": str(pk), "title": title, "image": storage_url(preview), "thumb": storage_url(thumb),
         "width": width, "height": height}
        for pk, title, preview, thumb, width, height in rows
    ]


def video_gallery(event_id: int) -> list[dict]:
    """Purchasable videos: watermarked poster + duration; the video file itself stays private."""
    from apps.core.models import storage_url

    rows = (
        EventVideo.objects.filter(event_id=event_id).exclude(video="")
        .order_by("sort_order", "pk")
        .values_list("pk", "title", "preview", "thumb", "duration_label")
    )
    return [
        {"id": str(pk), "title": title, "image": storage_url(preview), "thumb": storage_url(thumb),
         "duration": duration}
        for pk, title, preview, thumb, duration in rows
    ]
