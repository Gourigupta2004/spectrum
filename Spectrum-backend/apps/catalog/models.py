import os
import uuid

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils.text import slugify

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


# Events dated within this many months of today are tagged Recent on their own.
RECENT_MONTHS = 2


def months_before(day, months: int):
    """The same day `months` calendar months earlier (the month's last day
    when it is shorter: 31 Dec -> 31 Oct, 30 Apr -> 28/29 Feb)."""
    import calendar

    month_index = day.year * 12 + day.month - 1 - months
    year, month = divmod(month_index, 12)
    return day.replace(year=year, month=month + 1, day=min(day.day, calendar.monthrange(year, month + 1)[1]))


class InstitutionKind(models.Model):
    """A type of institution — School, College… Add a row here to introduce a new one."""

    slug = models.SlugField(unique=True, help_text="Short id used in filters, e.g. school.")
    name = models.CharField(max_length=60, help_text='Singular, e.g. "School".')
    plural = models.CharField(max_length=60, help_text='Filter chip on the events page, e.g. "Schools".')
    sort_order = models.PositiveIntegerField("order", default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name = "type"

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

    slug = models.SlugField(
        unique=True, max_length=120, blank=True,
        help_text="The event's link, spectrumphotographics.in/events/<slug>. Leave blank to make it from the name "
                  "and the event's number, e.g. prize-distribution-42, so events with the same name never clash.")
    name = models.CharField(max_length=160)
    institution = models.ForeignKey(Institution, on_delete=models.PROTECT, related_name="events")
    date = models.DateField(null=True, blank=True)
    date_label = models.CharField(max_length=60, blank=True, help_text='Optional display text. Blank shows the date, e.g. "March 15, 2025".')
    price_per_photo = models.PositiveIntegerField("price per photo (₹)", default=29)
    price_per_video = models.PositiveIntegerField("price per video (₹)", default=199)
    bundle_price = models.PositiveIntegerField("full album price (₹)", default=299,
                                               help_text="All photos. Videos are priced per video on top.")
    not_for_sale = models.BooleanField(
        "not for sale", default=False,
        help_text="The gallery shows as usual, but checkout only says these photographs aren't for sale "
                  "(Gallery & checkout pages › Not for sale message), and no order can be placed.")
    is_recent = models.BooleanField(
        "tag: recent", default=False,
        help_text=f"Events dated within the last {RECENT_MONTHS} months are tagged Recent automatically; tick this "
                  "to tag an older one too.")
    is_popular = models.BooleanField("tag: popular", default=False)
    is_published = models.BooleanField("published", default=True)
    sort_order = models.PositiveIntegerField("order", default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "-date", "pk"]
        indexes = [models.Index(fields=["is_published", "sort_order"])]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.slug:
            return super().save(*args, **kwargs)
        # The number isn't known until the row exists: save under a placeholder,
        # then settle on "<name>-<id>". Slugs already set are never touched.
        with transaction.atomic():
            self.slug = f"new-{uuid.uuid4().hex}"
            super().save(*args, **kwargs)
            base = slugify(self.name)[:100].strip("-") or "event"
            slug, n = f"{base}-{self.pk}", 1
            while Event.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                n += 1
                slug = f"{base}-{self.pk}-{n}"
            self.slug = slug
            Event.objects.filter(pk=self.pk).update(slug=slug)

    @property
    def display_date(self) -> str:
        if self.date_label:
            return self.date_label
        return f"{self.date:%B} {self.date.day}, {self.date.year}" if self.date else ""

    @property
    def is_recent_by_date(self) -> bool:
        from django.utils import timezone

        return bool(self.date and self.date >= months_before(timezone.localdate(), RECENT_MONTHS))

    @property
    def tags(self) -> list[str]:
        recent = self.is_recent or self.is_recent_by_date
        return [tag for tag, on in (("recent", recent), ("popular", self.is_popular)) if on]


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
    the public only sees the poster image (`original`, watermarked like a photo,
    but saying the video itself can't be previewed).
    """

    VARIANTS = {"preview": 1200, "thumb": 400}
    WATERMARKED = frozenset({"preview"})
    WATERMARK_TEXT = "Video preview not available"
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

    def save(self, *args, **kwargs):
        before = type(self).objects.filter(pk=self.pk).values_list("video", flat=True).first() if self.pk else ""
        super().save(*args, **kwargs)
        if before and before != self.video.name:
            # A replaced video is gigabytes nobody can buy any more.
            from django.db import transaction

            from apps.core.models import delete_files

            transaction.on_commit(lambda: delete_files(private_storage(), [before]))
