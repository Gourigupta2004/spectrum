import re

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import ProcessedImage


def natural_key(value: str) -> tuple:
    """
    Sort key for file-name-like titles: numeric first, then alphabetical. The
    first number in the name is the primary key, whatever text surrounds it
    ("2.jpg" < "DSC_10" < "IMG_11"); names sharing that number — and names with
    no number at all, which sort after every numbered one — fall back to a
    natural alphabetical order ("IMG_2" < "IMG_10").
    """
    value = (value or "").lower()
    match = re.search(r"\d+", value)
    return (
        0 if match else 1,
        int(match.group()) if match else 0,
        [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", value)],
    )


class Member(models.Model):
    INSTITUTION, SPECTRUM = "institution", "spectrum"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="member")
    institution = models.ForeignKey(
        "catalog.Institution", null=True, blank=True, on_delete=models.CASCADE, related_name="members",
        help_text="Leave blank for Spectrum team logins, which can see every institution.",
    )
    role = models.CharField(max_length=12, choices=[(INSTITUTION, "Institution"), (SPECTRUM, "Spectrum team")],
                            default=INSTITUTION)
    display_name = models.CharField(max_length=120, blank=True)
    token_version = models.PositiveIntegerField(default=1, editable=False)

    class Meta:
        verbose_name = "portal login"

    def __str__(self):
        return self.user.get_username()

    @property
    def is_spectrum(self) -> bool:
        return self.role == self.SPECTRUM


class PortalAccessEmail(models.Model):
    """
    An email address that unlocks the portal for one institution. Visitors enter
    their email on the website; only addresses listed here reveal the Portal
    link and the institution's personalised sign-in, where the issued login
    (Member) is still required.
    """

    institution = models.ForeignKey("catalog.Institution", on_delete=models.CASCADE, related_name="portal_emails")
    email = models.EmailField(unique=True)
    note = models.CharField(max_length=120, blank=True, help_text='Who this is, e.g. "Principal" or "Class 6 coordinator".')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["institution__name", "email"]
        verbose_name = "portal access email"

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        self.email = self.email.strip().lower()
        super().save(*args, **kwargs)


class CaptionWorkspace(models.Model):
    """
    One per institution: the batch of photos that institution titles, approves
    and corrects. Photos are bulk-uploaded onto this entry in the admin and
    every row appears beneath it with its title and state.
    """

    institution = models.OneToOneField("catalog.Institution", on_delete=models.CASCADE,
                                       related_name="caption_workspace")
    notes = models.TextField(blank=True, help_text="Internal notes, e.g. who to talk to at the institution.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["institution__name"]
        verbose_name = "title workspace"

    def __str__(self):
        return str(self.institution)

    @classmethod
    def for_institution(cls, institution_id: int) -> "CaptionWorkspace":
        return cls.objects.get_or_create(institution_id=institution_id)[0]


class CaptionStatus(models.TextChoices):
    """Stored values keep their historic names; the labels say "title". The
    definition order is the order admin dropdowns offer the request tags."""

    NEEDS_CAPTION = "needs-caption", "For Title"
    NEEDS_CORRECTION = "needs-correction", "For Correction"
    NEEDS_APPROVAL = "needs-approval", "For Approval"
    APPROVED = "approved", "Approved"
    CORRECTED = "corrected", "Corrected"


REQUEST_CHOICES = [c for c in CaptionStatus.choices if c[0].startswith("needs-")]


class CaptionItem(ProcessedImage):
    """
    A photo the institution titles, approves or corrects. Separate from the
    public gallery. A correction is the teacher rewriting the title, so it is
    saved straight into `caption`; re-uploading a file with the same name
    replaces this row's photo (see `source_name`) and keeps its text and state.
    """

    VARIANTS = {"web": 1600, "thumb": 400}

    workspace = models.ForeignKey(CaptionWorkspace, on_delete=models.CASCADE, related_name="items", null=True,
                                  blank=True, editable=False)
    event = models.ForeignKey("catalog.Event", on_delete=models.CASCADE, related_name="caption_items", null=True,
                              blank=True, help_text="Optional: the event this photo is from.")
    institution = models.ForeignKey("catalog.Institution", on_delete=models.CASCADE, related_name="caption_items",
                                    editable=False)
    moment_title = models.CharField(max_length=200, blank=True)
    # The uploaded file's name, the lookup key for re-uploads: a file arriving
    # with the same name lands in this row (new photo, same title and status).
    source_name = models.CharField("file name", max_length=200, blank=True, editable=False)
    caption = models.TextField("title", blank=True)
    requested = models.CharField(max_length=20, choices=REQUEST_CHOICES, default=CaptionStatus.NEEDS_APPROVAL)
    status = models.CharField(max_length=20, choices=CaptionStatus.choices, default=CaptionStatus.NEEDS_APPROVAL,
                              db_index=True)
    action_by = models.CharField(max_length=120, blank=True)
    action_by_phone = models.CharField("action by (phone)", max_length=20, blank=True,
                                       help_text="Mobile number given alongside the name when the action was taken.")
    updated_at = models.DateTimeField(default=timezone.now)
    sort_order = models.PositiveIntegerField("order", default=0)

    class Meta:
        ordering = ["sort_order", "pk"]
        indexes = [models.Index(fields=["institution", "image_status", "sort_order"])]
        verbose_name = "class photograph item"
        verbose_name_plural = "class photograph items"

    def __str__(self):
        return self.moment_title or f"Title item {self.pk}"

    def save(self, *args, **kwargs):
        # The institution and its workspace follow from whichever was given:
        # an event (public gallery flow), a workspace (admin bulk upload) or the
        # institution itself (portal upload / seed data).
        if self.event_id and not self.institution_id:
            from apps.catalog.models import Event

            self.institution_id = Event.objects.values_list("institution_id", flat=True).get(pk=self.event_id)
        if self.workspace_id and not self.institution_id:
            self.institution_id = CaptionWorkspace.objects.values_list("institution_id", flat=True).get(
                pk=self.workspace_id)
        if self.institution_id and not self.workspace_id:
            self.workspace_id = CaptionWorkspace.for_institution(self.institution_id).pk
        super().save(*args, **kwargs)


class SchoolClass(models.Model):
    GROUPS = [("Primary", "Primary"), ("Middle", "Middle"), ("Senior", "Senior")]

    institution = models.ForeignKey("catalog.Institution", on_delete=models.CASCADE, related_name="classes")
    name = models.CharField(max_length=20, help_text='e.g. "6C" or "Nursery".')
    slug = models.SlugField(max_length=30, blank=True, help_text="Filled from the name.")
    group = models.CharField(max_length=10, choices=GROUPS, default="Primary")
    sort_order = models.PositiveIntegerField("order", default=0)

    class Meta:
        ordering = ["institution", "sort_order", "pk"]
        constraints = [models.UniqueConstraint(fields=["institution", "slug"], name="uniq_class_slug")]
        verbose_name = "class"
        verbose_name_plural = "classes"

    def __str__(self):
        return f"{self.name} · {self.institution}" if self.institution_id else self.name

    def clean(self):
        from django.core.exceptions import ValidationError
        from django.utils.text import slugify

        if not (self.slug or slugify(self.name)):
            raise ValidationError({"name": "Use letters or numbers, e.g. 6C."})

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify

            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Student(ProcessedImage):
    VARIANTS = {"web": 600, "thumb": 300}

    school_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE, related_name="students",
                                     verbose_name="class")
    name = models.CharField(max_length=120, blank=True)
    sort_order = models.PositiveIntegerField("order", default=0)

    class Meta:
        ordering = ["sort_order", "pk"]
        indexes = [models.Index(fields=["school_class", "sort_order"])]

    def __str__(self):
        return self.name or f"Student {self.pk}"
