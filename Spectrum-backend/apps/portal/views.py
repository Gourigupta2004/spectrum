import os
import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from apps.catalog.models import Event, Institution
from apps.content.models import PortalPage
from apps.core.http import ApiError, api, rate_limit, text
from apps.core.models import ImageStatus, storage_url

from .auth import (
    REFRESH_SALT, PortalLogin, authenticate_portal, issue_tokens, member_from_token, read_token, require_member,
)
from .models import CaptionItem, CaptionStatus, CaptionWorkspace, PortalAccessEmail, SchoolClass, Student, natural_key

CAPTION_FIELDS = ("pk", "moment_title", "caption", "requested", "status", "updated_at", "action_by",
                  "action_by_phone", "web", "thumb", "width", "height", "event__name")
MAX_PHOTO_BYTES = 40 * 1024 * 1024


def date_label(value) -> str:
    local = timezone.localtime(value)
    return f"{local:%B} {local.day}, {local.year}"


def acting_institution(member: PortalLogin, request) -> Institution:
    """Institution logins see their own data; Spectrum team logins may pick one with ?institution=."""
    if not member.is_spectrum:
        if member.institution is None:
            raise ApiError("This login is not linked to an institution.", status=403)
        return member.institution
    slug = request.GET.get("institution")
    queryset = Institution.objects.all()
    institution = queryset.filter(slug=slug).first() if slug else (member.institution or queryset.first())
    if institution is None:
        raise ApiError("No institution found.", status=404)
    return institution


def institution_dict(institution: Institution) -> dict:
    return {"id": institution.slug, "name": institution.name, "city": institution.city}


def member_dict(member: PortalLogin, institution: Institution | None) -> dict:
    return {
        "id": member.id,
        "loginId": member.login_id,
        "displayName": member.display_name or member.login_id,
        "role": member.role,
        "institution": institution_dict(institution) if institution else None,
    }


def _clean_email(value: str) -> str:
    email = value.strip().lower()
    if not email:
        return ""
    try:
        validate_email(email)
    except ValidationError:
        raise ApiError("Please enter a valid email address.", field="email")
    return email


@api(methods=("POST",))
def access(request):
    """
    Step one of getting into the portal: is this email on an institution's
    access list? Says which institution it unlocks, so the sign-in screen can
    be personalised; the issued login is still required after this.
    """
    rate_limit(request, "portal-access", limit=15, window=600)
    email = _clean_email(text(request.json, "email", 254, required=True))
    row = PortalAccessEmail.objects.select_related("institution").filter(email=email).first()
    if row is None:
        raise ApiError(PortalPage.load().access_error or "This email doesn't have portal access.", status=403,
                       field="email")
    return {"email": email, "institution": institution_dict(row.institution)}


@api(methods=("POST",))
def login(request):
    rate_limit(request, "portal-login", limit=10, window=600)
    username = text(request.json, "username", 150, required=True)
    rate_limit(request, "portal-login-user", limit=20, window=3600, extra=username.lower())
    password = request.json.get("password") or ""
    email = _clean_email(text(request.json, "email", 254))
    member = authenticate_portal(request, username, password, email)
    if member is None:
        row = PortalAccessEmail.objects.filter(email=email).only("username", "password").first() if email else None
        if row is not None and not row.has_login:
            raise ApiError("No username and password have been set up for this email yet. Please contact Spectrum.",
                           status=401)
        raise ApiError(PortalPage.load().login_error or "Invalid login.", status=401)
    # With an email, an institution sign-in is that email's own, so one
    # school's credentials can never open another school's workspace.
    institution = member.institution if not member.is_spectrum else Institution.objects.first()
    return {**issue_tokens(member), "member": member_dict(member, institution)}


@api(methods=("POST",))
def refresh(request):
    token = str(request.json.get("refresh", ""))
    member = member_from_token(token, REFRESH_SALT, settings.PORTAL_REFRESH_TTL)
    if member is None:
        raise ApiError("Your session has expired. Please sign in again.", status=401)
    return issue_tokens(member, signed_in_at=read_token(token, REFRESH_SALT, settings.PORTAL_REFRESH_TTL)["t"])


@api()
def me(request):
    member = require_member(request)
    return member_dict(member, acting_institution(member, request))


@api()
def summary(request):
    member = require_member(request)
    institution = acting_institution(member, request)
    pending = CaptionItem.objects.filter(institution=institution, image_status=ImageStatus.READY).exclude(
        status__in=[CaptionStatus.APPROVED, CaptionStatus.CORRECTED]).count()
    students = Student.objects.filter(school_class__institution=institution).aggregate(
        total=Count("pk"), named=Count("pk", filter=~Q(name="")))
    return {"pendingCaptions": pending, "students": students["total"], "named": students["named"]}


def caption_dict(row) -> dict:
    return {
        "id": str(row.pk),
        "momentTitle": row.moment_title,
        "image": storage_url(row.web.name if row.web else ""),
        "thumb": storage_url(row.thumb.name if row.thumb else ""),
        "width": row.width,
        "height": row.height,
        "caption": row.caption,
        "requested": row.requested,
        "status": row.status,
        "updatedAt": date_label(row.updated_at),
        "actionBy": row.action_by,
        "actionByPhone": row.action_by_phone,
        "event": row.event.name if row.event_id else "",
    }


def scoped_captions(member, request):
    institution = acting_institution(member, request)
    return CaptionItem.objects.filter(institution=institution).select_related("event").only(*CAPTION_FIELDS)


@api(methods=("GET", "POST"))
def captions(request):
    member = require_member(request)
    if request.method == "GET":
        items = scoped_captions(member, request).filter(image_status=ImageStatus.READY)
        # File-name order (the title is taken from the file name at upload),
        # alphabetical and numerical — the same order the admin table shows.
        ordered = sorted(items, key=lambda item: (natural_key(item.moment_title), item.pk))
        return {"items": [caption_dict(item) for item in ordered]}
    return create_caption(request, member)


def _uploaded_image(request):
    upload = request.FILES.get("image")
    if upload is None:
        raise ApiError("Choose an image.", field="image")
    if upload.size > MAX_PHOTO_BYTES:
        raise ApiError("That image is too large.", field="image")
    return upload


def create_caption(request, member):
    if not member.is_spectrum:
        raise ApiError("Only the Spectrum team can add photos.", status=403)
    institution = acting_institution(member, request)
    slug = request.POST.get("event")
    event = Event.objects.filter(institution=institution, slug=slug).first() if slug else None
    if slug and event is None:
        raise ApiError("Event not found", status=404)
    requested = request.POST.get("requested", CaptionStatus.NEEDS_APPROVAL)
    if requested not in {CaptionStatus.NEEDS_APPROVAL, CaptionStatus.NEEDS_CAPTION}:
        requested = CaptionStatus.NEEDS_APPROVAL
    upload = _uploaded_image(request)
    item = CaptionItem(
        workspace=CaptionWorkspace.for_institution(institution.pk),
        event=event,
        institution=institution,
        moment_title=(request.POST.get("momentTitle") or "").strip()[:200],
        source_name=(upload.name or "")[:200],
        caption=(request.POST.get("caption") or "").strip()[:5000],
        requested=requested,
        status=requested,
        sort_order=0,
    )
    item.original = upload
    item.save()
    item.refresh_from_db()
    return caption_dict(item)


@api(methods=("POST",))
def caption_image(request, item_id):
    member = require_member(request)
    if not member.is_spectrum:
        raise ApiError("Only the Spectrum team can replace photos.", status=403)
    if not scoped_captions(member, request).filter(pk=item_id).exists():
        raise ApiError("Not found", status=404)
    item = CaptionItem.objects.select_related("event").get(pk=item_id)  # full row, so the old original is cleaned up
    item.original = _uploaded_image(request)
    item.save()
    item.refresh_from_db()
    return caption_dict(item)


@api(methods=("POST",))
def caption_resolve(request, item_id):
    member = require_member(request)
    data = request.json
    by = text(data, "actionBy", 120, required=True)
    if len(by) < 2:
        raise ApiError("Please add your full name.", field="actionBy")
    phone = text(data, "actionByPhone", 20, required=True)
    if len(re.sub(r"\D", "", phone)) < 7:
        raise ApiError("Please add your mobile number.", field="actionByPhone")
    wanted = text(data, "status", 30)
    body = text(data, "text", 5000)
    with transaction.atomic():
        item = scoped_captions(member, request).select_for_update(of=("self",)).filter(pk=item_id).first()
        if item is None:
            raise ApiError("Not found", status=404)
        # Saving or approving locks the item: one teacher acts on each photo
        # and any later change is made by the Spectrum team in the admin
        # (re-tagging it there sends it back to the institution).
        if item.status in (CaptionStatus.APPROVED, CaptionStatus.CORRECTED):
            raise ApiError("This title is locked and can no longer be edited.", status=409)
        fields = ["status", "action_by", "action_by_phone", "updated_at"]
        if item.status == CaptionStatus.NEEDS_CAPTION:  # first round: the title is written -> Submitted
            if not body:
                raise ApiError("Write the title first.", field="text")
            item.caption = body
            item.status = CaptionStatus.CORRECTED
            fields.append("caption")
        else:  # needs-approval: the last chance to adjust the wording, then Approved
            if wanted != CaptionStatus.APPROVED:
                raise ApiError("This title is waiting for approval.")
            if body:
                item.caption = body
                fields.append("caption")
            item.status = CaptionStatus.APPROVED
        item.action_by = by
        item.action_by_phone = phone
        item.updated_at = timezone.now()
        item.save(update_fields=fields)
    return caption_dict(item)


@api()
def classes(request):
    member = require_member(request)
    institution = acting_institution(member, request)
    rows = (  # school order: Nursery, LKG, UKG, 1A … 12C (SchoolClass.sort_key)
        SchoolClass.objects.filter(institution=institution)
        .annotate(size=Count("students"), named=Count("students", filter=~Q(students__name="")))
        .values_list("slug", "name", "group", "size", "named")
    )
    items = [{"id": slug, "name": name, "group": group, "size": size, "namedCount": named}
             for slug, name, group, size, named in rows]
    return {
        "classes": items,
        "totals": {"students": sum(i["size"] for i in items), "named": sum(i["namedCount"] for i in items)},
    }


def scoped_class(member, request, slug) -> SchoolClass:
    institution = acting_institution(member, request)
    cls = SchoolClass.objects.filter(institution=institution, slug=slug).first()
    if cls is None:
        raise ApiError("Class not found", status=404)
    return cls


def student_dict(pk, name, web, width, height, absentee) -> dict:
    return {"id": str(pk), "name": name, "photo": storage_url(web), "width": width, "height": height,
            "absentee": absentee}


@api()
def class_detail(request, slug):
    member = require_member(request)
    cls = scoped_class(member, request, slug)
    # File-name order (numbers numeric), the same order the admin shows; absentees last.
    rows = Student.objects.filter(school_class=cls).values_list("pk", "name", "web", "width", "height", "is_absentee")
    students = [student_dict(*row) for row in rows]
    return {
        "class": {"id": cls.slug, "name": cls.name, "group": cls.group, "size": len(students),
                  "namedCount": sum(1 for s in students if s["name"]), "comment": cls.comment},
        "students": students,
    }


MAX_ABSENTEE_FILES = 20


@api(methods=("POST",))
def class_absentees(request, slug):
    """Photos of absent students, uploaded by the institution; they are then
    named like every other student. Their web copies are made in the
    background, so `photo` may be empty in the reply."""
    from apps.core.models import IMAGE_EXTENSIONS

    member = require_member(request)
    rate_limit(request, "portal-absentees", limit=120, window=600)
    cls = scoped_class(member, request, slug)
    uploads = request.FILES.getlist("images")[:MAX_ABSENTEE_FILES]
    if not uploads:
        raise ApiError("Choose at least one photo.", field="images")
    for upload in uploads:
        if os.path.splitext(upload.name or "")[1].lower() not in IMAGE_EXTENSIONS:
            raise ApiError(f"{upload.name} is not a photo.", field="images")
        if upload.size > MAX_PHOTO_BYTES:
            raise ApiError(f"{upload.name} is too large.", field="images")
    created = []
    with transaction.atomic():
        for upload in uploads:
            student = Student(school_class=cls, is_absentee=True, source_name=(upload.name or "")[:200])
            student.original = upload
            student.save()
            created.append(student)
    return {"students": [student_dict(s.pk, s.name, s.web.name if s.web else "", s.width, s.height, True)
                         for s in created]}


@api(methods=("DELETE",))
def class_absentee(request, slug, student_id):
    """Removes an absentee photo added by mistake. Only absentees: the class's
    own photos come from Spectrum and stay."""
    member = require_member(request)
    cls = scoped_class(member, request, slug)
    student = Student.objects.filter(school_class=cls, pk=student_id, is_absentee=True).first()
    if student is None:
        raise ApiError("Not found", status=404)
    student.delete()  # the delete signal queues the storage cleanup
    return {"deleted": 1}


@api(methods=("PUT", "POST"))
def class_comment(request, slug):
    member = require_member(request)
    cls = scoped_class(member, request, slug)
    cls.comment = text(request.json, "comment", 5000)
    cls.save(update_fields=["comment"])
    return {"comment": cls.comment}


@api(methods=("PUT", "POST"))
def class_names(request, slug):
    member = require_member(request)
    cls = scoped_class(member, request, slug)
    names = request.json.get("names")
    if not isinstance(names, dict):
        raise ApiError("Expected names")
    wanted = {int(k): str(v or "").strip()[:120] for k, v in list(names.items())[:1000] if str(k).isdigit()}
    changed = []
    for student in Student.objects.filter(school_class=cls, pk__in=wanted).only("pk", "name"):
        if student.name != wanted[student.pk]:
            student.name = wanted[student.pk]
            changed.append(student)
    if changed:
        Student.objects.bulk_update(changed, ["name"], batch_size=200)
    named = Student.objects.filter(school_class=cls).exclude(name="").count()
    return {"updated": len(changed), "namedCount": named}
