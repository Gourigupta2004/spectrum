from django.contrib import admin, messages
from django.db.models import Count, F, Q

from apps.core.admin_tools import AppendOrderMixin, BulkUploadMixin, ImagePreviewMixin
from apps.core.models import ImageStatus

from apps.portal.forms import AccessEmailForm, password_status
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
    """The institution's sign-ins, one row each: an email that unlocks the
    portal, with the username and password that then sign in through it."""

    model = PortalAccessEmail
    form = AccessEmailForm
    extra = 1
    fields = ("email", "username", "new_password", "password_set", "note")
    readonly_fields = ("password_set",)
    verbose_name = "sign-in"
    verbose_name_plural = "institution credentials — email, username and password for the portal"

    @admin.display(description="Password set?")
    def password_set(self, obj):
        return password_status(obj)


@admin.register(Institution)
class InstitutionAdmin(AppendOrderMixin, BulkUploadMixin, ImagePreviewMixin, admin.ModelAdmin):
    # No uploader here: student photos are dropped on the institution's
    # workspace ("Individual Photographs Upload"). The mixin stays for its page
    # template, which gives the sign-in rows a tick-all-for-deletion box.
    inlines = (PortalAccessEmailInline,)
    list_display = ("thumbnail", "name", "short", "city", "kind", "event_count", "is_published", "sort_order")
    list_display_links = ("thumbnail", "name")
    list_editable = ("is_published", "sort_order")
    list_filter = ("kind", "is_published")
    search_fields = ("name", "short", "city", "portal_emails__email", "portal_emails__username")
    prepopulated_fields = {"slug": ("name",)}
    fields = ("name", "short", "slug", "city", "kind", "original", "is_published", "sort_order")
    actions = ["reprocess_images", "sign_out_of_portal"]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(event_total=Count("events"))

    @admin.display(description="Events", ordering="event_total")
    def event_count(self, obj):
        return obj.event_total

    def get_search_results(self, request, queryset, search_term):
        queryset, _ = super().get_search_results(request, queryset, search_term)
        return queryset.distinct(), False  # one row per institution, whichever sign-in matched

    @admin.action(description="Sign out of the portal everywhere")
    def sign_out_of_portal(self, request, queryset):
        PortalAccessEmail.objects.filter(institution__in=queryset).update(token_version=F("token_version") + 1)
        messages.success(request, f"Signed {queryset.count()} institution(s) out of the portal on every device.")


class EventVideoInline(ImagePreviewMixin, admin.TabularInline):
    """The event's purchasable videos, uploaded and edited only here on the
    event page (they have no admin list of their own)."""

    model = EventVideo
    extra = 1
    ordering = ("sort_order", "pk")
    fields = ("video", "title", "duration_label", "original", "image_status", "sort_order")
    readonly_fields = ("image_status",)

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
