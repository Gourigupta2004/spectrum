from django import forms
from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import PermissionDenied
from django.db import models
from django.db.models import Count, F, Q
from django.utils import timezone

from apps.core.admin_tools import AppendOrderMixin, BulkUploadMixin, ImagePreviewMixin, thumb_html
from apps.core.models import ImageStatus

from .models import (
    CaptionItem, CaptionStatus, CaptionWorkspace, Member, PortalAccessEmail, SchoolClass, Student, natural_key,
)


@admin.register(SchoolClass)
class SchoolClassAdmin(AppendOrderMixin, BulkUploadMixin, admin.ModelAdmin):
    bulk_upload_targets = ("portal.student",)
    list_display = ("name", "institution", "group", "student_count", "named_count", "sort_order")
    list_editable = ("group", "sort_order")
    list_filter = ("institution", "group")
    list_select_related = ("institution",)
    search_fields = ("name", "institution__name")
    prepopulated_fields = {"slug": ("name",)}
    fields = ("institution", "name", "slug", "group", "sort_order")
    autocomplete_fields = ("institution",)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            size=Count("students"), named=Count("students", filter=~Q(students__name="")))

    @admin.display(description="Students", ordering="size")
    def student_count(self, obj):
        return obj.size

    @admin.display(description="Named", ordering="named")
    def named_count(self, obj):
        return obj.named


@admin.register(Student)
class StudentAdmin(AppendOrderMixin, ImagePreviewMixin, admin.ModelAdmin):
    list_display = ("thumbnail", "name", "school_class", "image_status", "sort_order")
    list_editable = ("name", "sort_order")
    list_filter = ("school_class__institution", "school_class")
    list_select_related = ("school_class__institution",)
    list_per_page = 100
    search_fields = ("name",)
    fields = ("school_class", "name", "original", "sort_order")
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


def _retag(queryset, tag: str) -> int:
    return queryset.exclude(status=CaptionStatus.APPROVED).update(status=tag, requested=tag, updated_at=timezone.now())


class RetagActionsMixin:
    """Actions for the tags the institution sees on the workspace cards."""

    @admin.action(description="Ask the institution to write a title")
    def mark_needs_caption(self, request, queryset):
        messages.success(request, f"{_retag(queryset, CaptionStatus.NEEDS_CAPTION)} item(s) now need a title.")

    @admin.action(description="Ask the institution to approve")
    def mark_needs_approval(self, request, queryset):
        messages.success(request, f"{_retag(queryset, CaptionStatus.NEEDS_APPROVAL)} item(s) sent for approval.")

    @admin.action(description="Ask the institution to correct")
    def mark_needs_correction(self, request, queryset):
        messages.success(request, f"{_retag(queryset, CaptionStatus.NEEDS_CORRECTION)} item(s) sent for correction.")


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
    show_change_link = True
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
    bulk_upload_targets = ("portal.captionitem",)
    inlines = (CaptionItemInline,)
    list_display = ("institution", "photo_count", "needs_caption", "awaiting", "corrected_count", "approved_count",
                    "created_at")
    list_select_related = ("institution",)
    search_fields = ("institution__name", "institution__short")
    autocomplete_fields = ("institution",)
    fields = ("institution", "notes")

    # ---- Delete all photos: one button that clears the workspace so a fresh
    # ---- batch (say, the edited versions of all 100 files) can be uploaded.

    def get_urls(self):
        from django.urls import path

        return [
            path("<path:object_id>/delete-photos/", self.admin_site.admin_view(self.delete_photos),
                 name="portal_captionworkspace_delete_photos"),
            *super().get_urls(),
        ]

    def delete_photos(self, request, object_id):
        from django.http import HttpResponseNotAllowed
        from django.shortcuts import get_object_or_404, redirect

        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])
        if not request.user.has_perm("portal.delete_captionitem"):
            raise PermissionDenied
        workspace = get_object_or_404(CaptionWorkspace, pk=object_id)
        count, _ = workspace.items.all().delete()  # signals queue the S3 cleanup
        messages.success(request, f"Deleted {count} photo(s) from {workspace}.")
        return redirect("admin:portal_captionworkspace_change", workspace.pk)

    def render_change_form(self, request, context, add=False, change=False, form_url="", obj=None):
        from django.urls import reverse

        if obj is not None and obj.pk and request.user.has_perm("portal.delete_captionitem"):
            count = obj.items.count()
            if count:
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

    @admin.display(description="For title", ordering="n_caption")
    def needs_caption(self, obj):
        return obj.n_caption

    @admin.display(description="Awaiting institution", ordering="n_waiting")
    def awaiting(self, obj):
        return obj.n_waiting

    @admin.display(description="Corrected", ordering="n_corrected")
    def corrected_count(self, obj):
        return obj.n_corrected

    @admin.display(description="Approved", ordering="n_approved")
    def approved_count(self, obj):
        return obj.n_approved


@admin.register(CaptionItem)
class CaptionItemAdmin(RetagActionsMixin, ImagePreviewMixin, admin.ModelAdmin):
    form = CaptionItemForm
    list_display = ("thumbnail", "moment_title", "institution", "status", "action_by", "action_by_phone",
                    "updated_at")
    list_editable = ("moment_title",)
    list_filter = ("status", "institution", "event")
    list_select_related = ("institution", "event")
    list_per_page = 100
    search_fields = ("moment_title", "caption", "institution__name")
    readonly_fields = ("institution", "status", "action_by", "action_by_phone", "updated_at")
    fields = ("institution", "event", "original", "moment_title", "caption", "requested",
              "status", "action_by", "action_by_phone", "updated_at", "sort_order")
    autocomplete_fields = ("event",)
    actions = ["reprocess_images", "mark_needs_caption", "mark_needs_approval", "mark_needs_correction"]

    def get_readonly_fields(self, request, obj=None):
        # A brand-new item needs an event to know which institution it belongs to.
        return self.readonly_fields if obj else tuple(f for f in self.readonly_fields if f != "institution")

    def get_fields(self, request, obj=None):
        return self.fields if obj else tuple(f for f in self.fields if f != "institution")


# --------------------------------------------------------------------------- access & logins


@admin.register(PortalAccessEmail)
class PortalAccessEmailAdmin(admin.ModelAdmin):
    list_display = ("email", "institution", "note", "created_at")
    list_filter = ("institution",)
    list_select_related = ("institution",)
    search_fields = ("email", "note", "institution__name")
    autocomplete_fields = ("institution",)
    fields = ("institution", "email", "note")


class MemberForm(forms.ModelForm):
    login_id = forms.CharField(label="Login ID", max_length=150, help_text='What they type to sign in, e.g. "dps-newdelhi".')
    password = forms.CharField(widget=forms.PasswordInput(render_value=False), required=False,
                               help_text="Leave blank to keep the current password.")

    class Meta:
        model = Member
        fields = ("institution", "role", "display_name")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["login_id"].initial = self.instance.user.get_username()
        else:
            self.fields["password"].required = True

    def clean_login_id(self):
        login_id = self.cleaned_data["login_id"].strip()
        users = get_user_model().objects.filter(username=login_id)
        if self.instance.pk:
            users = users.exclude(pk=self.instance.user_id)
        if users.exists():
            raise forms.ValidationError("That login ID is already taken.")
        return login_id

    def clean_password(self):
        password = self.cleaned_data.get("password")
        if password:
            validate_password(password)
        return password

    def save(self, commit=True):
        member = super().save(commit=False)
        user = member.user if member.pk else get_user_model()(is_staff=False)
        user.username = self.cleaned_data["login_id"]
        if self.cleaned_data.get("password"):
            user.set_password(self.cleaned_data["password"])
            if member.pk:
                member.token_version += 1  # a new password signs out every device
        user.save()
        member.user = user
        if commit:
            member.save()
        return member


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    form = MemberForm
    list_display = ("login", "display_name", "institution", "role")
    list_filter = ("role", "institution")
    list_select_related = ("user", "institution")
    search_fields = ("user__username", "display_name")
    fields = ("login_id", "password", "display_name", "institution", "role")
    autocomplete_fields = ("institution",)
    actions = ["sign_out_everywhere"]

    @admin.display(description="Login ID", ordering="user__username")
    def login(self, obj):
        return obj.user.get_username()

    @admin.action(description="Sign out everywhere")
    def sign_out_everywhere(self, request, queryset):
        count = queryset.update(token_version=F("token_version") + 1)
        messages.success(request, f"Signed out {count} login(s) on every device.")
