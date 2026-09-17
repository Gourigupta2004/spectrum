"""Shared admin building blocks: singletons, bulk upload drop zones, thumbnails."""

from django.conf import settings
from django.contrib import admin, messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.html import format_html

from .models import ImageStatus
from .tasks import enqueue
from .uploads import TARGETS, grid_context

STATUS_COLOURS = {
    ImageStatus.READY: "#2fbf8f",
    ImageStatus.PENDING: "#b58900",
    ImageStatus.PROCESSING: "#7c4de0",
    ImageStatus.FAILED: "#e8503a",
    ImageStatus.EMPTY: "#999",
}


def thumb_html(obj, size: int = 56):
    url = obj.thumb_url if obj and obj.pk else ""
    if url:
        return format_html(
            '<img src="{}" style="width:{}px;height:{}px;object-fit:cover;border-radius:6px" loading="lazy">',
            url, size, size,
        )
    status = getattr(obj, "image_status", ImageStatus.EMPTY)
    return format_html(
        '<span style="color:{};font-size:11px">{}</span>', STATUS_COLOURS.get(status, "#999"),
        obj.get_image_status_display() if obj and obj.pk else "No image",
    )


class ImagePreviewMixin:
    """Adds a `preview` readonly column/field and a Reprocess action."""

    @admin.display(description="Preview")
    def preview(self, obj):
        return thumb_html(obj)

    @admin.action(description="Re-make image variants")
    def reprocess_images(self, request, queryset):
        ids = list(queryset.exclude(image_status=ImageStatus.EMPTY).values_list("pk", flat=True))
        queryset.filter(pk__in=ids).update(image_status=ImageStatus.PENDING)
        for pk in ids:
            enqueue("core.process_image", queryset.model._meta.label_lower, pk)
        messages.success(request, f"Queued {len(ids)} image(s) for processing.")


class BulkUploadMixin:
    """Renders one drag-drop / paste uploader per target on the change form."""

    bulk_upload_targets: tuple[str, ...] = ()
    change_form_template = "admin/core/change_form_bulk.html"

    def render_change_form(self, request, context, add=False, change=False, form_url="", obj=None):
        uploads = []
        if obj is not None and obj.pk:
            for key in self.bulk_upload_targets:
                target = TARGETS[key]
                meta = target.model_class._meta
                if not request.user.has_perm(f"{meta.app_label}.add_{meta.model_name}"):
                    continue
                uploads.append({
                    "target": key,
                    "label": target.label,
                    "parent_id": obj.pk,
                    "choices": target.choice_fields(),
                    "grid": grid_context(key, obj.pk),
                })
        context["bulk_uploads"] = uploads
        context["bulk_upload_after_save"] = bool(self.bulk_upload_targets) and obj is None
        context["bulk_upload_prepare_url"] = reverse("admin-upload-prepare")
        context["bulk_upload_grid_url"] = reverse("admin-upload-grid")
        context["upload_max_bytes"] = settings.UPLOAD_MAX_BYTES
        return super().render_change_form(request, context, add, change, form_url, obj)

    def response_add(self, request, obj, post_url_continue=None):
        # Land on the change page, where the uploader lives, instead of the list.
        if self.bulk_upload_targets and "_addanother" not in request.POST and "_popup" not in request.POST:
            request.POST = request.POST.copy()
            request.POST["_continue"] = "1"
        return super().response_add(request, obj, post_url_continue)


class SingletonAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        obj = self.model.load()
        meta = self.model._meta
        return redirect(reverse(f"admin:{meta.app_label}_{meta.model_name}_change", args=[obj.pk]))

    def response_change(self, request, obj):
        messages.success(request, f"{obj} saved.")
        return redirect(request.path)
