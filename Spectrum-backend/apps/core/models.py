import os
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from spectrum.storages import private_storage, public_storage

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".tif", ".tiff", ".bmp", ".gif"}


# --------------------------------------------------------------------------- tasks


class Task(models.Model):
    """A queued background job. Successful tasks are deleted, so the table stays tiny."""

    QUEUED, RUNNING, FAILED = "queued", "running", "failed"

    name = models.CharField(max_length=100)
    args = models.JSONField(default=list, blank=True)
    status = models.CharField(
        max_length=10, choices=[(QUEUED, "Queued"), (RUNNING, "Running"), (FAILED, "Failed")], default=QUEUED
    )
    attempts = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=3)
    run_after = models.DateTimeField(default=timezone.now)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["run_after", "id"]
        indexes = [models.Index(fields=["status", "run_after"])]
        verbose_name = "background task"

    def __str__(self):
        return f"{self.name}{tuple(self.args)}"


# --------------------------------------------------------------------------- singletons


class SingletonModel(models.Model):
    """One row per table (pk=1): page copy and site settings."""

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        return 0, {}

    @classmethod
    def load(cls):
        obj = cls.objects.filter(pk=1).first()
        if obj is None:
            obj = cls(pk=1)
            obj.save()
        return obj

    def __str__(self):
        return str(self._meta.verbose_name).capitalize()


# --------------------------------------------------------------------------- images


def validate_image_extension(value):
    ext = os.path.splitext(value.name)[1].lower()
    if ext and ext not in IMAGE_EXTENSIONS:
        raise ValidationError(f"Unsupported image type {ext}. Use JPG, PNG, WebP or HEIC.")


def original_upload_to(instance, filename):
    return original_key(instance.__class__, filename)


def original_key(model, filename):
    ext = os.path.splitext(filename)[1].lower()
    if ext not in IMAGE_EXTENSIONS:
        ext = ".jpg"
    return f"{model._meta.app_label}/{model._meta.model_name}/{uuid.uuid4().hex}{ext}"


class ImageStatus(models.TextChoices):
    EMPTY = "empty", "No image"
    PENDING = "pending", "Waiting"
    PROCESSING = "processing", "Processing"
    READY = "ready", "Ready"
    FAILED = "failed", "Failed"


def storage_url(name: str) -> str:
    """Absolute URL for a file name in public storage ("" when missing). No DB or network access."""
    if not name:
        return ""
    url = public_storage().url(name)
    return url if url.startswith("http") else f"{settings.API_URL}{url}"


def public_url(field_file) -> str:
    """Absolute URL for a public variant; empty string when it does not exist yet."""
    return storage_url(field_file.name if field_file else "")


class ProcessedImage(models.Model):
    """
    Keeps the uploaded original private and serves resized WebP variants publicly.

    VARIANTS maps a variant field name to its longest edge in pixels. Subclasses may
    add variant fields (EventPhoto adds `preview`) and list watermarked ones in
    WATERMARKED. The worker fills the variants; web requests never touch Pillow.
    """

    VARIANTS: dict[str, int] = {"web": 1600, "thumb": 400}
    WATERMARKED: frozenset[str] = frozenset()

    original = models.FileField(
        "image",
        storage=private_storage,
        upload_to=original_upload_to,
        max_length=255,
        blank=True,
        validators=[validate_image_extension],
    )
    web = models.FileField(storage=public_storage, max_length=255, blank=True, editable=False)
    thumb = models.FileField(storage=public_storage, max_length=255, blank=True, editable=False)
    width = models.PositiveIntegerField(null=True, blank=True, editable=False)
    height = models.PositiveIntegerField(null=True, blank=True, editable=False)
    image_status = models.CharField(
        "image", max_length=12, choices=ImageStatus.choices, default=ImageStatus.EMPTY, editable=False, db_index=True
    )
    image_error = models.TextField(blank=True, editable=False)

    class Meta:
        abstract = True

    @classmethod
    def from_db(cls, db, field_names, values):
        obj = super().from_db(db, field_names, values)
        obj._loaded_original = obj.__dict__.get("original")
        return obj

    @property
    def image_url(self) -> str:
        return public_url(self.web)

    @property
    def thumb_url(self) -> str:
        return public_url(self.thumb)

    def variant_names(self) -> list[str]:
        return list(self.VARIANTS)

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        changed = False
        before = ""
        if update_fields is None or "original" in update_fields:
            before = str(getattr(self, "_loaded_original", "") or "")
            current = self.original.name or ""
            if current != before:
                changed = True
                self.image_status = ImageStatus.PENDING if current else ImageStatus.EMPTY
                self.image_error = ""
                if update_fields is not None:
                    kwargs["update_fields"] = set(update_fields) | {"image_status", "image_error"}
        super().save(*args, **kwargs)
        if not changed:
            return
        self._loaded_original = self.original.name or ""
        from .tasks import enqueue

        if before:
            transaction.on_commit(lambda: delete_files(private_storage(), [before]))
        if self._loaded_original:
            label, pk = self._meta.label_lower, self.pk
            transaction.on_commit(lambda: enqueue("core.process_image", label, pk))
        else:
            old_variants = [getattr(self, name).name for name in self.variant_names() if getattr(self, name)]
            for name in self.variant_names():
                setattr(self, name, "")
            type(self).objects.filter(pk=self.pk).update(**{name: "" for name in self.variant_names()})
            transaction.on_commit(lambda: delete_files(public_storage(), old_variants))


def delete_files(storage, names):
    for name in names:
        if name:
            try:
                storage.delete(name)
            except Exception:  # a missing file must never break a save or delete
                pass


# --------------------------------------------------------------------------- uploads


class UploadBatch(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    target = models.CharField(max_length=60)
    parent_id = models.PositiveBigIntegerField(null=True)
    base_sort_order = models.PositiveIntegerField(default=0)
    prepared_keys = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)


class UploadBatchFile(models.Model):
    batch = models.ForeignKey(UploadBatch, related_name="files", on_delete=models.CASCADE)
    client_id = models.CharField(max_length=64)
    object_id = models.PositiveBigIntegerField()
    # False when the file replaced an existing row's photo (same file name),
    # which keeps that row's own tag; a batch tag picked later skips it.
    created = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["batch", "client_id"], name="uniq_batch_client")]
