import os
import uuid

from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import ProcessedImage
from spectrum.storages import private_storage, public_storage

VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm"}


def validate_video_extension(value):
    ext = os.path.splitext(value.name)[1].lower()
    if ext and ext not in VIDEO_EXTENSIONS:
        raise ValidationError(f"Unsupported video type {ext}. Use MP4, MOV or WebM.")


def video_upload_to(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    if ext not in VIDEO_EXTENSIONS:
        ext = ".mp4"
    return f"catalog/eventvideo/videos/{uuid.uuid4().hex}{ext}"


class InstitutionKind(models.Model):
    """A type of institution — School, College… Add a row here to introduce a new one."""

    slug = models.SlugField(unique=True, help_text="Short id used in filters, e.g. school.")
    name = models.CharField(max_length=60, help_text='Singular, e.g. "School".')
    plural = models.CharField(max_length=60, help_text='Filter chip on the events page, e.g. "Schools".')
    sort_order = models.PositiveIntegerField("order", default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name = "institution type"

    def __str__(self):
        return self.name


class Institution(ProcessedImage):
    VARIANTS = {"web": 500, "thumb": 200}

    slug = models.SlugField(unique=True, help_text="Short id used in links, e.g. dps.")
    name = models.CharField(max_length=160)
    short = models.CharField("short name", max_length=80, blank=True, help_text="Shown under the round photo.")
    city = models.CharField(max_length=80, blank=True)
    kind = models.ForeignKey(InstitutionKind, on_delete=models.PROTECT, related_name="institutions",
                             verbose_name="type")
    is_published = models.BooleanField("published", default=True)
    sort_order = models.PositiveIntegerField("order", default=0)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name


class Event(ProcessedImage):
    VARIANTS = {"web": 1000, "thumb": 400}

    slug = models.SlugField(unique=True, max_length=120)
    name = models.CharField(max_length=160)
    institution = models.ForeignKey(Institution, on_delete=models.PROTECT, related_name="events")
    date = models.DateField(null=True, blank=True)
    date_label = models.CharField(max_length=60, blank=True, help_text='Optional display text. Blank shows the date, e.g. "March 15, 2025".')
    price_per_photo = models.PositiveIntegerField("price per photo (₹)", default=29)
    price_per_video = models.PositiveIntegerField("price per video (₹)", default=199)
    bundle_price = models.PositiveIntegerField("full album price (₹)", default=299,
                                               help_text="All photos. Videos are priced per video on top.")
    is_recent = models.BooleanField("tag: recent", default=False)
    is_popular = models.BooleanField("tag: popular", default=False)
    is_published = models.BooleanField("published", default=True)
    sort_order = models.PositiveIntegerField("order", default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "-date", "pk"]
        indexes = [models.Index(fields=["is_published", "sort_order"])]

    def __str__(self):
        return self.name

    @property
    def display_date(self) -> str:
        if self.date_label:
            return self.date_label
        return f"{self.date:%B} {self.date.day}, {self.date.year}" if self.date else ""

    @property
    def tags(self) -> list[str]:
        return [tag for tag, on in (("recent", self.is_recent), ("popular", self.is_popular)) if on]


class EventPhoto(ProcessedImage):
    """Gallery photos. The public only ever sees the watermarked preview and a small thumb."""

    VARIANTS = {"preview": 1200, "thumb": 400}
    WATERMARKED = frozenset({"preview"})

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="photos")
    title = models.CharField(max_length=200, blank=True)
    preview = models.FileField(storage=public_storage, max_length=255, blank=True, editable=False)
    sort_order = models.PositiveIntegerField("order", default=0)

    class Meta:
        ordering = ["sort_order", "pk"]
        indexes = [models.Index(fields=["event", "image_status", "sort_order"])]
        verbose_name = "event photo"
        verbose_name_plural = "all photos"

    def __str__(self):
        return self.title or f"Photo {self.pk}"

    @property
    def image_url(self) -> str:
        from apps.core.models import public_url

        return public_url(self.preview)


class EventVideo(ProcessedImage):
    """
    A purchasable event video. The video file itself stays private until bought;
    the public only sees the poster image (`original`, watermarked like a photo).
    """

    VARIANTS = {"preview": 1200, "thumb": 400}
    WATERMARKED = frozenset({"preview"})
    EXTRA_PRIVATE_FILES = ("video",)  # cleaned from storage with the row, like the original

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="videos")
    title = models.CharField(max_length=200, blank=True)
    video = models.FileField("video file", storage=private_storage, upload_to=video_upload_to, max_length=255,
                             validators=[validate_video_extension])
    duration_label = models.CharField("duration", max_length=20, blank=True,
                                      help_text='Shown on the card, e.g. "2:41".')
    preview = models.FileField(storage=public_storage, max_length=255, blank=True, editable=False)
    sort_order = models.PositiveIntegerField("order", default=0)

    class Meta:
        ordering = ["sort_order", "pk"]
        indexes = [models.Index(fields=["event", "sort_order"])]
        verbose_name = "event video"

    def __str__(self):
        return self.title or f"Video {self.pk}"
