from django.contrib import admin
from django.db.models import Count, Q

from apps.core.admin_tools import BulkUploadMixin, ImagePreviewMixin
from apps.core.models import ImageStatus

from apps.portal.models import PortalAccessEmail

from .models import Event, EventPhoto, Institution, InstitutionKind


@admin.register(InstitutionKind)
class InstitutionKindAdmin(admin.ModelAdmin):
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
    verbose_name_plural = "portal access emails"


@admin.register(Institution)
class InstitutionAdmin(ImagePreviewMixin, admin.ModelAdmin):
    inlines = (PortalAccessEmailInline,)
    list_display = ("preview", "name", "short", "city", "kind", "event_count", "is_published", "sort_order")
    list_display_links = ("preview", "name")
    list_editable = ("is_published", "sort_order")
    list_filter = ("kind", "is_published")
    search_fields = ("name", "short", "city")
    prepopulated_fields = {"slug": ("name",)}
    fields = ("name", "short", "slug", "city", "kind", "original", "is_published", "sort_order")
    actions = ["reprocess_images"]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(event_total=Count("events"))

    @admin.display(description="Events", ordering="event_total")
    def event_count(self, obj):
        return obj.event_total


@admin.register(Event)
class EventAdmin(BulkUploadMixin, ImagePreviewMixin, admin.ModelAdmin):
    bulk_upload_targets = ("catalog.eventphoto",)
    list_display = ("preview", "name", "institution", "date", "gallery_count", "price_per_photo", "bundle_price",
                    "is_published")
    list_display_links = ("preview", "name")
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
        ("Cover & pricing", {"fields": ("original", "price_per_photo", "bundle_price")}),
        ("Listing", {"fields": ("is_recent", "is_popular", "is_published", "sort_order")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            photo_total=Count("photos", filter=Q(photos__image_status=ImageStatus.READY)))

    @admin.display(description="Photos", ordering="photo_total")
    def gallery_count(self, obj):
        return obj.photo_total


@admin.register(EventPhoto)
class EventPhotoAdmin(ImagePreviewMixin, admin.ModelAdmin):
    list_display = ("preview", "title", "event", "image_status", "sort_order")
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
