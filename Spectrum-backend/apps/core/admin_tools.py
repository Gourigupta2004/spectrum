"""Shared admin building blocks: singletons, bulk upload drop zones, thumbnails."""

from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.db import models
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


class ImageFileInput(forms.ClearableFileInput):
    """The upload widget with a thumbnail instead of the raw storage path."""

    template_name = "admin/core/image_file_input.html"

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        instance = getattr(value, "instance", None)
        context["thumb"] = thumb_html(instance, 84) if instance is not None else ""
        try:
            context["link"] = value.url if value else ""
        except Exception:  # a storage without URLs, or a missing file
            context["link"] = ""
        return context


class AppendOrderMixin:
    """New rows land at the end: the Add form pre-fills `order` with max + 1.

    Without this every new row defaults to 0 and jumps to the front, which
    reads as "ordering is broken" the moment a curated list gains a row.
    """

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        if "sort_order" not in initial:
            top = self.model.objects.aggregate(top=models.Max("sort_order"))["top"]
            initial["sort_order"] = 0 if top is None else top + 1
        return initial


class ImagePreviewMixin:
    """Adds a `thumbnail` list column, a thumbnail upload widget, and a Reprocess action."""

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == "original":
            kwargs.setdefault("widget", ImageFileInput)
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    # Named `thumbnail`, not `preview`: a model field of the same name (EventPhoto
    # has one) would win the admin's lookup and render as a file link instead.
    @admin.display(description="Preview")
    def thumbnail(self, obj):
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
                    "hint": target.hint,
                    "folders": target.folders,
                    "parent_id": obj.pk,
                    "choices": target.choice_fields(),
                    "grid": grid_context(key, obj.pk, request.user),
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
        if "_continue" in request.POST:
            return redirect(request.path)
        # "Save" closes the form. The changelist just bounces back here, so go to the admin home.
        return redirect("admin:index")
