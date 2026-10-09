from django import forms
from django.contrib import admin, messages
from django.contrib.auth.password_validation import validate_password
from django.db.models import Count, F, Q

from apps.core.admin_tools import AppendOrderMixin, BulkUploadMixin, ImagePreviewMixin
from apps.core.models import ImageStatus

from apps.portal.models import PortalAccessEmail

from .models import Event, EventPhoto, EventVideo, Institution, InstitutionKind


@admin.register(InstitutionKind)
class InstitutionKindAdmin(AppendOrderMixin, admin.ModelAdmin):
    list_display = ("name", "plural", "slug", "institution_count", "sort_order")
    list_editable = ("sort_order",)
    prepopulated_fields = {"slug": ("name",)}

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(total=Count("institutions"))

    @admin.display(description="Institutions", ordering="total")
    def institution_count(self, obj):
        return obj.total


class PortalAccessEmailInline(admin.TabularInline):
    """Emails that unlock the institution portal for this institution."""

    model = PortalAccessEmail
    extra = 1
    fields = ("email", "note")
    verbose_name = "access email"
    verbose_name_plural = "institution credentials — emails that unlock the portal"


class InstitutionForm(forms.ModelForm):
    """The portal password is set here and stored hashed: it can be replaced,
    never read back."""

    new_portal_password = forms.CharField(
        label="Portal password", required=False, strip=False,
        widget=forms.PasswordInput(render_value=False, attrs={"autocomplete": "new-password"}),
        help_text="Type a password to set or change it; leave blank to keep the current one. A new password signs "
                  "the institution out of the portal on every device.")

    class Meta:
        model = Institution
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "new_portal_password" in self.fields and self.instance.portal_password:
            self.fields["new_portal_password"].help_text = "A password is set. " + \
                self.fields["new_portal_password"].help_text

    def clean_portal_username(self):
        username = (self.cleaned_data.get("portal_username") or "").strip()
        if not username:
            return None
        taken = Institution.objects.filter(portal_username__iexact=username).exclude(pk=self.instance.pk)
        if taken.exists():
            raise forms.ValidationError("Another institution already signs in with that username.")
        return username

    def clean_new_portal_password(self):
        password = self.cleaned_data.get("new_portal_password")
        if password:
            validate_password(password)
        return password

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("portal_username") and not (cleaned.get("new_portal_password") or self.instance.portal_password):
            self.add_error("new_portal_password", "Set a password for this username.")
        return cleaned

    def save(self, commit=True):
        institution = super().save(commit=False)
        if self.cleaned_data.get("new_portal_password"):
            institution.set_portal_password(self.cleaned_data["new_portal_password"])
        if commit:
            institution.save()
            self.save_m2m()
        return institution


@admin.register(Institution)
class InstitutionAdmin(AppendOrderMixin, BulkUploadMixin, ImagePreviewMixin, admin.ModelAdmin):
    # No uploader here: student photos are dropped on the institution's
    # workspace ("Individual Photographs Upload"). The mixin stays for its page
    # template, which gives the access-email rows a tick-all-for-deletion box.
    form = InstitutionForm
    inlines = (PortalAccessEmailInline,)
    list_display = ("thumbnail", "name", "short", "city", "kind", "event_count", "portal_username", "is_published",
                    "sort_order")
    list_display_links = ("thumbnail", "name")
    list_editable = ("is_published", "sort_order")
    list_filter = ("kind", "is_published")
    search_fields = ("name", "short", "city", "portal_username")
    prepopulated_fields = {"slug": ("name",)}
    fieldsets = (
        (None, {"fields": ("name", "short", "slug", "city", "kind", "original", "is_published", "sort_order")}),
        ("Institution portal sign-in", {
            "description": "The username and password this institution signs in to the website portal with, after "
                           "entering one of the access emails listed below.",
            "fields": ("portal_username", "new_portal_password"),
        }),
    )
    actions = ["reprocess_images", "sign_out_of_portal"]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(event_total=Count("events"))

    @admin.display(description="Events", ordering="event_total")
    def event_count(self, obj):
        return obj.event_total

    @admin.action(description="Sign out of the portal everywhere")
    def sign_out_of_portal(self, request, queryset):
        count = queryset.update(portal_token_version=F("portal_token_version") + 1)
        messages.success(request, f"Signed {count} institution(s) out of the portal on every device.")


class EventVideoInline(ImagePreviewMixin, admin.TabularInline):
    """Upload the event's purchasable videos right on the event page."""

    model = EventVideo
    extra = 1
    ordering = ("sort_order", "pk")
    fields = ("video", "title", "duration_label", "original", "sort_order")

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == "original":
            kwargs["label"] = "Poster image"
            kwargs["help_text"] = "Shown in the gallery with the watermark; buyers get the video file."
        return super().formfield_for_dbfield(db_field, request, **kwargs)


@admin.register(Event)
class EventAdmin(AppendOrderMixin, BulkUploadMixin, ImagePreviewMixin, admin.ModelAdmin):
    bulk_upload_targets = ("catalog.eventphoto",)
    inlines = (EventVideoInline,)
    list_display = ("thumbnail", "name", "institution", "date", "gallery_count", "video_count", "price_per_photo",
                    "price_per_video", "bundle_price", "is_published")
    list_display_links = ("thumbnail", "name")
    list_editable = ("is_published",)
    list_filter = ("is_published", "institution", "is_recent", "is_popular")
    list_select_related = ("institution",)
    search_fields = ("name", "slug", "institution__name")
    prepopulated_fields = {"slug": ("name",)}
    autocomplete_fields = ("institution",)
    date_hierarchy = "date"
    actions = ["reprocess_images"]
    fieldsets = (
        (None, {"fields": ("name", "slug", "institution", "date", "date_label")}),
        ("Cover & pricing", {"fields": ("original", "price_per_photo", "price_per_video", "bundle_price")}),
        ("Listing", {"fields": ("is_recent", "is_popular", "is_published", "sort_order")}),
    )

    def changelist_view(self, request, extra_context=None):
        return super().changelist_view(request, {"title": "Select event to edit", **(extra_context or {})})

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            photo_total=Count("photos", filter=Q(photos__image_status=ImageStatus.READY), distinct=True),
            video_total=Count("videos", distinct=True))

    @admin.display(description="Photos", ordering="photo_total")
    def gallery_count(self, obj):
        return obj.photo_total

    @admin.display(description="Videos", ordering="video_total")
    def video_count(self, obj):
        return obj.video_total


@admin.register(EventPhoto)
class EventPhotoAdmin(AppendOrderMixin, ImagePreviewMixin, admin.ModelAdmin):
    list_display = ("thumbnail", "title", "event", "image_status", "sort_order")
    list_editable = ("title", "sort_order")
    list_filter = ("image_status", "event__institution", "event")
    list_select_related = ("event",)
    list_per_page = 100
    search_fields = ("title", "event__name")
    readonly_fields = ("image_status", "image_error", "width", "height")
    fields = ("event", "title", "original", "sort_order", "image_status", "image_error", "width", "height")
    autocomplete_fields = ("event",)
    actions = ["reprocess_images"]

    def get_queryset(self, request):
        return super().get_queryset(request).only(
            "pk", "title", "thumb", "image_status", "sort_order", "event__name", "original", "image_error",
            "width", "height", "event_id")


@admin.register(EventVideo)
class EventVideoAdmin(AppendOrderMixin, ImagePreviewMixin, admin.ModelAdmin):
    list_display = ("thumbnail", "title", "event", "duration_label", "image_status", "sort_order")
    list_editable = ("title", "duration_label", "sort_order")
    list_filter = ("event__institution", "event")
    list_select_related = ("event",)
    search_fields = ("title", "event__name")
    readonly_fields = ("image_status", "image_error")
    fields = ("event", "title", "video", "duration_label", "original", "sort_order", "image_status", "image_error")
    autocomplete_fields = ("event",)
    actions = ["reprocess_images"]

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        field = form.base_fields.get("original")
        if field is not None:
            field.label = "Poster image"
            field.help_text = "Shown in the gallery with the watermark; buyers get the video file."
        return form
