from django import forms
from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.db import models
from django.db.models import Count, F, Q
from django.utils import timezone

from apps.core.admin_tools import AppendOrderMixin, BulkUploadMixin, ImagePreviewMixin, thumb_html
from apps.core.models import ImageStatus

from .forms import AccessEmailForm, password_status
from .models import (
    SPECTRUM_PORTAL_CODENAME, CaptionItem, CaptionStatus, CaptionWorkspace, PortalAccessEmail, SchoolClass, Student,
    natural_key,
)


def _institution_code(name: str) -> str:
    """Initials, as the website's download used: Delhi Public School -> DPS."""
    return "".join(word[0] for word in str(name).split()).upper()


def _safe_file_name(name: str) -> str:
    """A file name every OS accepts: no path separators or reserved characters."""
    import re as _re

    cleaned = _re.sub(r"\s+", " ", _re.sub(r'[\\/:*?"<>|]+', " ", name.strip())).lstrip(".")[:100].strip()
    return cleaned or "Student"


def class_photos_zip(request, classes):
    """
    The class folder the website used to build, now admin-only: one folder
    per class ({CODE}-{CLASS}-Photos), one file per student — called after
    the student once named, else "Unnamed <uploaded file name>" — from the
    uploaded originals, at full size, instead of the website's re-encoded web
    copies. None (with a warning) when there is nothing to put in it.
    """
    import os
    import tempfile
    import zipfile

    from django.http import FileResponse

    if not request.user.has_perm("portal.view_student"):
        raise PermissionDenied
    classes = list(classes)
    buffer = tempfile.TemporaryFile()  # spooled to disk, so huge classes never sit in RAM
    included = 0
    folders = []
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as archive:  # photos are already compressed
        for cls in classes:
            folder = _safe_file_name(f"{_institution_code(cls.institution.name)}-{cls.name.upper()}-Photos")
            folders.append(folder)
            used: dict[str, int] = {}
            for position, student in enumerate(cls.students.all(), 1):  # file-name order (Student.Meta)
                if not student.original:
                    continue
                if student.name.strip():
                    base = _safe_file_name(student.name)
                else:
                    stem = os.path.splitext(student.source_name)[0].strip()
                    base = _safe_file_name(f"Unnamed {stem or position}")
                n = used.get(base.lower(), 0) + 1
                used[base.lower()] = n
                ext = os.path.splitext(student.original.name)[1].lower() or ".jpg"
                filename = f"{base}{'' if n == 1 else f' ({n})'}{ext}"
                with student.original.open("rb") as handle:
                    archive.writestr(f"{folder}/{filename}", handle.read())
                included += 1
    if not included:
        buffer.close()
        messages.warning(request, "Nothing to download: no student photos in the selection.")
        return None
    buffer.seek(0)
    zip_name = f"{folders[0]}.zip" if len(folders) == 1 else (
        f"{_institution_code(classes[0].institution.name)}-Class-Photos.zip")
    return FileResponse(buffer, as_attachment=True, filename=zip_name, content_type="application/zip")


@admin.register(SchoolClass)
class SchoolClassAdmin(BulkUploadMixin, admin.ModelAdmin):
    # Listed in school order (Nursery, LKG, UKG, 1A … 12C), from the names.
    bulk_upload_targets = ("portal.student",)
    list_display = ("name", "institution", "group", "student_count", "named_count")
    list_editable = ("group",)
    list_filter = ("institution", "group")
    list_select_related = ("institution",)
    search_fields = ("name", "institution__name")
    prepopulated_fields = {"slug": ("name",)}
    fields = ("institution", "name", "slug", "group")
    autocomplete_fields = ("institution",)
    actions = ["download_photos"]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            size=Count("students"), named=Count("students", filter=~Q(students__name="")))

    @admin.action(description="Download photos — folder of originals, named after the students")
    def download_photos(self, request, queryset):
        return class_photos_zip(request, queryset.select_related("institution"))

    @admin.display(description="Students", ordering="size")
    def student_count(self, obj):
        return obj.size

    @admin.display(description="Named", ordering="named")
    def named_count(self, obj):
        return obj.named


@admin.register(Student)
class StudentAdmin(AppendOrderMixin, ImagePreviewMixin, admin.ModelAdmin):
    # Listed by class, then file name (numbers numeric) — the portal's order.
    list_display = ("thumbnail", "name", "source_name", "school_class", "image_status")
    list_editable = ("name",)
    list_filter = ("school_class__institution", "school_class")
    list_select_related = ("school_class__institution",)
    list_per_page = 100
    search_fields = ("name", "source_name")
    fields = ("school_class", "name", "original", "source_name", "sort_order")
    readonly_fields = ("source_name",)
    ordering = ("school_class__institution", "school_class__sort_key", "school_class", "sort_key", "sort_order", "pk")
    autocomplete_fields = ("school_class",)
    actions = ["reprocess_images"]


# --------------------------------------------------------------------------- caption workspace


class CaptionItemForm(forms.ModelForm):
    """
    Re-tagging an item sends it back to the institution in that state: change
    "Requested" from For Title to For Approval once the title is written and
    the teacher sees it under Pending again. Approved items stay approved.
    """

    class Meta:
        model = CaptionItem
        fields = "__all__"

    def save(self, commit=True):
        item = super().save(commit=False)
        if "requested" in self.changed_data and item.status != CaptionStatus.APPROVED:
            item.status = item.requested
            item.updated_at = timezone.now()
        if commit:
            item.save()
            self.save_m2m()
        return item


class NaturalTitleFormSet(forms.models.BaseInlineFormSet):
    """
    Rows in file-name order: the title comes from the uploaded file's name, and
    plain DB ordering would put "IMG_10" before "IMG_2". Sorting in Python keeps
    numbers numeric — the same order the website's workspace shows.
    """

    def get_queryset(self):
        if not hasattr(self, "_natural_order"):
            self._natural_order = sorted(
                super().get_queryset(), key=lambda item: (natural_key(item.moment_title), item.pk))
        return self._natural_order


class CaptionItemInline(admin.TabularInline):
    """
    Every photo in the workspace as a row: image, the title Spectrum wrote and
    — once the teacher has acted — who did it. A teacher's correction rewrites
    the title in place, so there is one text per photo, always current.
    """

    model = CaptionItem
    form = CaptionItemForm
    formset = NaturalTitleFormSet
    fk_name = "workspace"
    extra = 0
    fields = ("image", "moment_title", "caption", "requested", "status", "action_by",
              "action_by_phone", "updated_at")
    readonly_fields = ("image", "status", "action_by", "action_by_phone", "updated_at")
    ordering = ("sort_order", "pk")
    formfield_overrides = {
        models.TextField: {"widget": forms.Textarea(attrs={"rows": 3, "cols": 34})},
        models.CharField: {"widget": forms.TextInput(attrs={"size": 22})},
    }

    @admin.display(description="Photo")
    def image(self, obj):
        return thumb_html(obj, 84)

    def has_add_permission(self, request, obj=None):
        return False  # photos come in through the uploader below


@admin.register(CaptionWorkspace)
class CaptionWorkspaceAdmin(BulkUploadMixin, admin.ModelAdmin):
    # Class photographs go to the institution for titles (edited in the table
    # on this page — they have no admin list of their own); individual
    # (student) photographs come in as class folders, one class per folder.
    bulk_upload_targets = ("portal.captionitem", "portal.workspacestudent")
    inlines = (CaptionItemInline,)
    list_display = ("institution", "photo_count", "needs_caption", "awaiting", "corrected_count", "approved_count",
                    "created_at")
    list_select_related = ("institution",)
    search_fields = ("institution__name", "institution__short")
    autocomplete_fields = ("institution",)
    fields = ("institution", "notes")

    # ---- Workspace tools: export every class photograph to Excel, and one button
    # ---- that clears the workspace so a fresh batch can be uploaded.

    def get_urls(self):
        from django.urls import path

        return [
            path("<path:object_id>/delete-photos/", self.admin_site.admin_view(self.delete_photos),
                 name="portal_captionworkspace_delete_photos"),
            path("<path:object_id>/export-titles/", self.admin_site.admin_view(self.export_titles),
                 name="portal_captionworkspace_export_titles"),
            path("<path:object_id>/download-students/", self.admin_site.admin_view(self.download_students),
                 name="portal_captionworkspace_download_students"),
            *super().get_urls(),
        ]

    def export_titles(self, request, object_id):
        """Every photo's S3 link with its title beside it, as an .xlsx download."""
        from django.http import HttpResponse
        from django.shortcuts import get_object_or_404
        from django.utils.text import slugify

        from apps.core.models import storage_url
        from apps.core.xlsx import workbook_bytes

        if not request.user.has_perm("portal.view_captionitem"):
            raise PermissionDenied
        workspace = get_object_or_404(CaptionWorkspace, pk=object_id)
        items = sorted(workspace.items.all(), key=lambda i: (natural_key(i.moment_title), i.pk))
        rows = [("File name", "Image (S3 link)", "Title", "Status", "Action by", "Mobile number", "Updated")]
        for item in items:
            rows.append((
                item.source_name or item.moment_title,
                storage_url(item.web.name if item.web else ""),
                item.caption,
                item.get_status_display(),
                item.action_by,
                item.action_by_phone,
                timezone.localtime(item.updated_at).strftime("%d %b %Y, %H:%M"),
            ))
        content = workbook_bytes(rows, widths=(30, 85, 60, 14, 22, 16, 18), sheet_name="Titles")
        filename = f"{slugify(str(workspace.institution)) or 'workspace'}-titles.xlsx"
        response = HttpResponse(
            content, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    def download_students(self, request, object_id):
        """The zip of one class's (or every class's) originals, from the pick
        under Individual Photographs."""
        from django.shortcuts import get_object_or_404, redirect

        workspace = get_object_or_404(CaptionWorkspace, pk=object_id)
        classes = SchoolClass.objects.filter(institution_id=workspace.institution_id).select_related("institution")
        choice = request.GET.get("class", "all")
        if choice != "all":
            classes = classes.filter(pk=int(choice) if choice.isdigit() else 0)
        response = class_photos_zip(request, classes)
        return response or redirect("admin:portal_captionworkspace_change", workspace.pk)

    def delete_photos(self, request, object_id):
        from django.http import HttpResponseNotAllowed
        from django.shortcuts import get_object_or_404, redirect

        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])
        if not request.user.has_perm("portal.delete_captionitem"):
            raise PermissionDenied
        workspace = get_object_or_404(CaptionWorkspace, pk=object_id)
        count, _ = workspace.items.all().delete()  # signals queue the S3 cleanup
        messages.success(request, f"Deleted {count} class photograph(s) from {workspace}.")
        return redirect("admin:portal_captionworkspace_change", workspace.pk)

    def render_change_form(self, request, context, add=False, change=False, form_url="", obj=None):
        from django.urls import reverse

        context["bulk_tools_target"] = "portal.captionitem"
        if obj is not None and obj.pk:
            count = obj.items.count()
            if count and request.user.has_perm("portal.view_captionitem"):
                context["bulk_export_url"] = reverse("admin:portal_captionworkspace_export_titles",
                                                     args=[obj.pk])
            if count and request.user.has_perm("portal.delete_captionitem"):
                context["bulk_delete_all_url"] = reverse("admin:portal_captionworkspace_delete_photos",
                                                         args=[obj.pk])
                context["bulk_delete_all_count"] = count
        return super().render_change_form(request, context, add, change, form_url, obj)

    def get_queryset(self, request):
        ready = Q(items__image_status=ImageStatus.READY)
        return super().get_queryset(request).annotate(
            photos=Count("items", filter=ready),
            n_caption=Count("items", filter=ready & Q(items__status=CaptionStatus.NEEDS_CAPTION)),
            n_waiting=Count("items", filter=ready & Q(
                items__status__in=[CaptionStatus.NEEDS_APPROVAL, CaptionStatus.NEEDS_CORRECTION])),
            n_corrected=Count("items", filter=ready & Q(items__status=CaptionStatus.CORRECTED)),
            n_approved=Count("items", filter=ready & Q(items__status=CaptionStatus.APPROVED)),
        )

    def get_readonly_fields(self, request, obj=None):
        return ("institution",) if obj else ()  # one workspace per institution; never re-pointed

    @admin.display(description="Photos", ordering="photos")
    def photo_count(self, obj):
        return obj.photos

    @admin.display(description="Titled", ordering="n_caption")
    def needs_caption(self, obj):
        return obj.n_caption

    @admin.display(description="Pending", ordering="n_waiting")
    def awaiting(self, obj):
        return obj.n_waiting

    @admin.display(description="Corrected", ordering="n_corrected")
    def corrected_count(self, obj):
        return obj.n_corrected

    @admin.display(description="Approved", ordering="n_approved")
    def approved_count(self, obj):
        return obj.n_approved


# --------------------------------------------------------------------------- institution credentials (access emails)


@admin.register(PortalAccessEmail)
class PortalAccessEmailAdmin(admin.ModelAdmin):
    """Every sign-in: an email that unlocks an institution's portal, with the
    username and password that sign in through it. The password is stored
    hashed, so it can be replaced here but never shown."""

    form = AccessEmailForm
    list_display = ("email", "institution", "username", "password_set", "note", "created_at")
    list_filter = ("institution",)
    list_select_related = ("institution",)
    search_fields = ("email", "username", "note", "institution__name")
    autocomplete_fields = ("institution",)
    fields = ("institution", "email", "username", "new_password", "password_set", "note")
    readonly_fields = ("password_set",)
    actions = ["sign_out_everywhere"]

    @admin.display(description="Password set?")
    def password_set(self, obj):
        return password_status(obj)

    @admin.action(description="Sign out of the portal everywhere")
    def sign_out_everywhere(self, request, queryset):
        count = queryset.update(token_version=F("token_version") + 1)
        messages.success(request, f"Signed {count} sign-in(s) out of the portal on every device.")


# --------------------------------------------------------------------------- Spectrum team portal access


def _portal_permission():
    return Permission.objects.get(content_type__app_label="portal", codename=SPECTRUM_PORTAL_CODENAME)


class PortalAccessUserForm(UserAdmin.form):
    portal_access = forms.BooleanField(
        label="Institution portal access", required=False,
        help_text="Lets this user sign in to the website's institution portal with this username and password, as "
                  "the Spectrum team, and open every institution. Superusers always can.")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["portal_access"].initial = self.instance.user_permissions.filter(
                content_type__app_label="portal", codename=SPECTRUM_PORTAL_CODENAME).exists()


class PortalAccessUserAdmin(UserAdmin):
    """The Users table, with the Spectrum team's portal access beside the rest
    of what a user may do (it replaces the old Portal logins table)."""

    form = PortalAccessUserForm
    list_display = (*UserAdmin.list_display, "portal_access")
    fieldsets = (
        UserAdmin.fieldsets[0],
        UserAdmin.fieldsets[1],
        ("Institution portal", {"fields": ("portal_access",)}),
        *UserAdmin.fieldsets[2:],
    )

    @admin.display(description="Portal access", boolean=True)
    def portal_access(self, obj):
        from .auth import has_spectrum_access

        return has_spectrum_access(obj)

    def save_related(self, request, form, formsets, change):
        # After the permissions list is saved, so the tick box has the last word.
        super().save_related(request, form, formsets, change)
        if "portal_access" in form.cleaned_data:
            permission = _portal_permission()
            if form.cleaned_data["portal_access"]:
                form.instance.user_permissions.add(permission)
            else:
                form.instance.user_permissions.remove(permission)


User = get_user_model()
if admin.site.is_registered(User):
    admin.site.unregister(User)
admin.site.register(User, PortalAccessUserAdmin)
