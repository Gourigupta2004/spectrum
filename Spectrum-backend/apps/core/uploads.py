"""
Bulk image upload for the admin.

Flow (one JS uploader for every batch in the admin):
  1. prepare  -> per file: a signed token and an upload URL (presigned S3 PUT, or the
                 local `direct` endpoint when storage is the filesystem)
  2. upload   -> browser sends bytes straight to S3 (the server never proxies them)
  3. commit   -> rows are created in chunks; idempotent per (batch, clientId)
  4. status   -> the worker makes variants; the page polls counts until done
"""

import json
import os
import re
import uuid
from dataclasses import dataclass, field

from django.apps import apps
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.core import signing
from django.db import transaction
from django.db.models import Count, Max, Q
from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.urls import NoReverseMatch, path, reverse
from django.views.decorators.http import require_GET, require_POST

from spectrum.storages import private_storage

from .models import IMAGE_EXTENSIONS, ImageStatus, UploadBatch, UploadBatchFile, original_key
from .tasks import enqueue

TOKEN_SALT = "core.upload"
TOKEN_MAX_AGE = 12 * 3600


@dataclass(frozen=True)
class Target:
    model: str
    parent: str
    name_field: str | None
    label: str
    defaults: dict = field(default_factory=dict)
    # Fields the uploader lets the admin pick before uploading, as {field: allowed values}.
    choices: dict = field(default_factory=dict)
    # Fields that take the same value as a chosen option, as {option: field}.
    mirror: dict = field(default_factory=dict)
    # The file name is the lookup key: a row whose `source_name` matches an
    # incoming file gets its photo replaced in place — text and status kept —
    # instead of a new row being created. Non-matching files create rows as usual.
    upsert_by_name: bool = False
    # A routed target: the uploader page lives on `page_parent` (app.Model) and
    # each file's real `parent` FK value is derived from its file name by
    # `route(page_parent_id, filename)`, which may create the parent on the fly
    # and returns None when the name carries no destination.
    page_parent: str | None = None
    route: object = None
    # Lookup path from the model to the page's parent, for the thumbnail grid
    # under a routed uploader. Defaults to `parent`.
    grid_parent: str | None = None

    @property
    def model_class(self):
        return apps.get_model(self.model)

    def choice_fields(self) -> list[dict]:
        """What the template renders: one select per choice, defaulting to the target's default."""
        meta = self.model_class._meta
        return [
            {
                "key": key,
                "label": str(meta.get_field(key).verbose_name).capitalize(),
                "options": list(meta.get_field(key).choices or []),
                "default": self.defaults.get(key),
            }
            for key in self.choices
        ]


def _request_tags() -> list[str]:
    from apps.portal.models import REQUEST_CHOICES

    return [value for value, _ in REQUEST_CHOICES]


# The class token at the front of a student file name: one or two digits (the
# class) followed by up to three letters (the section), then a separator —
# "6C_amity_1" -> 6C, "12AB_front row.jpg" -> 12AB.
CLASS_TOKEN = re.compile(r"^\s*(\d{1,2})\s*([A-Za-z]{1,3})(?![A-Za-z0-9])")


def class_for_file(institution_id, filename):
    """
    The class a student photo belongs in, read from its file name and created
    on first sight — so the operations team uploads one massive batch onto the
    institution and the classes assemble themselves. None when the name does
    not start with a class token.
    """
    from django.utils.text import slugify

    from apps.portal.models import SchoolClass

    stem = os.path.splitext(os.path.basename(filename))[0]
    match = CLASS_TOKEN.match(stem)
    if not match:
        return None
    number, section = int(match.group(1)), match.group(2).upper()
    name = f"{number}{section}"
    group = "Primary" if number <= 5 else "Middle" if number <= 8 else "Senior"
    cls, _ = SchoolClass.objects.get_or_create(
        institution_id=institution_id, slug=slugify(name), defaults={"name": name, "group": group})
    return cls.pk


TARGETS = {
    "catalog.eventphoto": Target("catalog.EventPhoto", "event", "title", "Gallery photos"),
    # A fresh upload always starts by asking the institution for a title; the
    # uploader's "Requested" tag can switch a batch to approval or correction.
    # Re-uploading a file with a name the workspace has seen replaces that
    # row's photo and keeps its title and status.
    "portal.captionitem": Target(
        "portal.CaptionItem", "workspace", "moment_title", "Title workspace photos",
        {"status": "needs-caption", "requested": "needs-caption"},
        choices={"requested": _request_tags}, mirror={"requested": "status"},
        upsert_by_name=True,
    ),
    "portal.student": Target("portal.Student", "school_class", None, "Student photos"),
    # The institution-wide drop: thousands of files land on the institution and
    # each one is filed into its class (created as needed) from its file name.
    "portal.studentbatch": Target(
        "portal.Student", "school_class", None, "Student photos — filed into classes by file name",
        page_parent="catalog.Institution", route=class_for_file, grid_parent="school_class__institution",
    ),
    "content.heroslide": Target("content.HeroSlide", "page", "caption", "Hero carousel slides"),
    "content.tieup": Target("content.TieUp", "page", "name", "Tie-up photos"),
}

CAMERA_NAME = re.compile(r"^(img|dsc|dscn|dscf|pxl|mvimg|gopr|dji|photo|image|whatsapp image)[\s_-]*\d", re.I)


def humanize(filename: str) -> str:
    stem = os.path.splitext(os.path.basename(filename))[0]
    if CAMERA_NAME.match(stem):
        return stem[:200]
    words = re.sub(r"[_\-]+", " ", stem)
    words = re.sub(r"\s+", " ", words).strip()
    if words and (words.islower() or words.isupper()):
        words = words.title()
    return words[:200]


def _target(key: str, user, perm: str = "add") -> Target:
    target = TARGETS.get(key)
    if target is None:
        raise Http404("Unknown upload target")
    meta = target.model_class._meta
    if not user.has_perm(f"{meta.app_label}.{perm}_{meta.model_name}"):
        raise Http404("Not allowed")
    return target


def _is_s3(storage) -> bool:
    return hasattr(storage, "bucket_name")


def _body(request) -> dict:
    try:
        data = json.loads(request.body or b"{}")
    except ValueError:
        data = {}
    return data if isinstance(data, dict) else {}


def _error(message: str, status: int = 400) -> JsonResponse:
    return JsonResponse({"error": message}, status=status)


def _presign_put(storage, key: str, content_type: str) -> str:
    client = storage.connection.meta.client
    return client.generate_presigned_url(
        "put_object",
        Params={"Bucket": storage.bucket_name, "Key": storage._normalize_name(key), "ContentType": content_type},
        ExpiresIn=3600,
    )


@staff_member_required
@require_POST
def prepare(request):
    data = _body(request)
    target_key = str(data.get("target", ""))
    target = _target(target_key, request.user)
    model = target.model_class
    parent_field = model._meta.get_field(target.parent)
    page_model = apps.get_model(target.page_parent) if target.page_parent else parent_field.related_model
    try:
        parent_id = int(data.get("parentId"))
    except (TypeError, ValueError):
        return _error("Missing parent")
    if not page_model.objects.filter(pk=parent_id).exists():
        return _error("Parent not found", 404)

    batch = None
    try:
        batch_id = uuid.UUID(str(data.get("batchId"))) if data.get("batchId") else None
    except ValueError:
        batch_id = None
    if batch_id:
        # Batches used to record the model label; they now record the TARGETS
        # key, so two targets over one model stay apart. Accept both spellings.
        batch = UploadBatch.objects.filter(
            pk=batch_id, target__in=(target_key, target.model.lower()), parent_id=parent_id).first()
    if batch is None:
        if target.route:
            # Rows are routed to parents derived per file; there is no single
            # parent whose top sort_order could seed the batch.
            top = None
        else:
            top = model.objects.filter(**{parent_field.attname: parent_id}).aggregate(top=Max("sort_order"))["top"]
        batch = UploadBatch.objects.create(
            target=target_key,
            parent_id=parent_id,
            base_sort_order=0 if top is None else top + 1,
            created_by=request.user,
        )

    storage = private_storage()
    s3 = _is_s3(storage)
    direct_url = reverse("admin-upload-direct")
    files = data.get("files") if isinstance(data.get("files"), list) else []
    entries = []
    new_keys = []
    for item in files[:500]:
        if not isinstance(item, dict):
            continue
        client_id = str(item.get("clientId", ""))[:64]
        name = str(item.get("name", "image.jpg"))[:200]
        size = _int(item.get("size"))
        ext = os.path.splitext(name)[1].lower()
        if ext not in IMAGE_EXTENSIONS:
            entries.append({"clientId": client_id, "error": f"{ext or 'This file type'} is not an image"})
            continue
        if size <= 0 or size > settings.UPLOAD_MAX_BYTES:
            entries.append({"clientId": client_id, "error": "File is empty or too large"})
            continue
        key = original_key(model, name)
        new_keys.append(key)
        token = signing.dumps([str(batch.pk), client_id, key], salt=TOKEN_SALT, compress=True)
        entry = {"clientId": client_id, "token": token}
        if s3:
            content_type = str(item.get("type") or "application/octet-stream")[:100]
            entry.update(method="PUT", uploadUrl=_presign_put(storage, key, content_type),
                         headers={"Content-Type": content_type})
        else:
            entry.update(method="POST", uploadUrl=direct_url)
        entries.append(entry)
    if new_keys:
        # Remembered so housekeeping can delete files whose upload was never saved.
        batch.prepared_keys = [*batch.prepared_keys, *new_keys][-5000:]
        batch.save(update_fields=["prepared_keys"])
    return JsonResponse({"batchId": str(batch.pk), "mode": "s3" if s3 else "direct", "files": entries})


def _int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _unsign(token: str):
    try:
        batch_id, client_id, key = signing.loads(token, salt=TOKEN_SALT, max_age=TOKEN_MAX_AGE)
    except (signing.BadSignature, ValueError, TypeError):
        return None
    return batch_id, client_id, key


@staff_member_required
@require_POST
def direct(request):
    parsed = _unsign(request.POST.get("token", ""))
    upload = request.FILES.get("file")
    if not parsed or upload is None:
        return _error("Invalid upload")
    if upload.size > settings.UPLOAD_MAX_BYTES:
        return _error("File too large")
    key = parsed[2]
    storage = private_storage()
    if not storage.exists(key):
        storage.save(key, upload)
    return JsonResponse({"ok": True})


@staff_member_required
@require_POST
def commit(request, batch_id):
    batch = UploadBatch.objects.filter(pk=batch_id).first()
    if batch is None:
        return _error("Batch not found", 404)
    target = _target(_target_key(batch), request.user)
    model = target.model_class
    parent_attname = model._meta.get_field(target.parent).attname
    body = _body(request)
    files = body.get("files")
    options = body.get("options") if isinstance(body.get("options"), dict) else {}
    extra = dict(target.defaults)
    for key, allowed in target.choices.items():
        value = options.get(key)
        if value in (allowed() if callable(allowed) else allowed):
            extra[key] = value
            if key in target.mirror:
                extra[target.mirror[key]] = value
    parsed = []
    for item in (files if isinstance(files, list) else [])[:100]:
        if not isinstance(item, dict):
            continue
        token = _unsign(str(item.get("token", "")))
        if token and token[0] == str(batch.pk):
            index = max(0, _int(item.get("index")))
            parsed.append((token[1], token[2], index, str(item.get("name") or "")))
    done = set(
        UploadBatchFile.objects.filter(batch=batch, client_id__in=[p[0] for p in parsed]).values_list("client_id", flat=True)
    )
    storage = private_storage()
    created, skipped, errors = [], [], {}
    with transaction.atomic():
        for client_id, key, index, name in parsed:
            if client_id in done:
                created.append(client_id)
                continue
            if not storage.exists(key):
                skipped.append(client_id)
                continue
            if storage.size(key) > settings.UPLOAD_MAX_BYTES:
                storage.delete(key)
                skipped.append(client_id)
                continue
            parent_value = batch.parent_id
            if target.route:
                parent_value = target.route(batch.parent_id, name)
                if parent_value is None:
                    storage.delete(key)
                    skipped.append(client_id)
                    errors[client_id] = 'no class at the front of the file name (expected e.g. "6C_...")'
                    continue
            obj = _matching_row(target, model, parent_attname, parent_value, name)
            if obj is not None:
                # Same file name, same row: only the photo changes; the title,
                # status and everything the institution did stay as they are.
                obj.source_name = name[:200]
                obj.original = key
                obj.save()
            else:
                obj = model(**{parent_attname: parent_value}, **extra)
                obj.sort_order = batch.base_sort_order + index
                if target.name_field:
                    setattr(obj, target.name_field, humanize(name))
                if target.upsert_by_name:
                    obj.source_name = name[:200]
                obj.original = key
                obj.save()
            UploadBatchFile.objects.create(batch=batch, client_id=client_id, object_id=obj.pk)
            created.append(client_id)
    return JsonResponse({"created": created, "skipped": skipped, "errors": errors})


def _matching_row(target: Target, model, parent_attname: str, parent_id, name: str):
    """The row a re-upload lands in: same parent, same file name. Rows from
    before file names were stored fall back to matching on the humanised title."""
    if not target.upsert_by_name or not name.strip():
        return None
    lookup = Q(source_name__iexact=name[:200])
    title = humanize(name)
    if title:
        lookup |= Q(source_name="", **{f"{target.name_field}__iexact": title})
    return model.objects.filter(**{parent_attname: parent_id}).filter(lookup).order_by("pk").first()


def _target_key(batch) -> str:
    if batch.target in TARGETS:
        return batch.target
    # Batches from before targets were stored by key carry the model label.
    for key, target in TARGETS.items():
        if target.model.lower() == batch.target:
            return key
    raise Http404("Unknown upload target")


@staff_member_required
@require_GET
def status(request, batch_id):
    batch = UploadBatch.objects.filter(pk=batch_id).first()
    if batch is None:
        return _error("Batch not found", 404)
    target = _target(_target_key(batch), request.user, perm="view")
    ids = batch.files.values("object_id")
    counts = dict(
        target.model_class.objects.filter(pk__in=ids).values_list("image_status").annotate(n=Count("pk")).order_by()
    )
    return JsonResponse({
        "total": sum(counts.values()),
        "pending": counts.get(ImageStatus.PENDING, 0),
        "processing": counts.get(ImageStatus.PROCESSING, 0),
        "ready": counts.get(ImageStatus.READY, 0),
        "failed": counts.get(ImageStatus.FAILED, 0),
    })


@staff_member_required
@require_POST
def retry_failed(request, batch_id):
    batch = UploadBatch.objects.filter(pk=batch_id).first()
    if batch is None:
        return _error("Batch not found", 404)
    target = _target(_target_key(batch), request.user, perm="change")
    model = target.model_class
    ids = list(model.objects.filter(pk__in=batch.files.values("object_id"), image_status=ImageStatus.FAILED)
               .values_list("pk", flat=True))
    model.objects.filter(pk__in=ids).update(image_status=ImageStatus.PENDING)
    for pk in ids:
        enqueue("core.process_image", model._meta.label_lower, pk)
    return JsonResponse({"requeued": len(ids)})


GRID_LIMIT = 300


def grid_context(target_key: str, parent_id) -> dict:
    target = TARGETS[target_key]
    model = target.model_class
    meta = model._meta
    lookup = target.grid_parent or meta.get_field(target.parent).attname
    queryset = model.objects.filter(**{lookup: parent_id})
    fields = ["pk", "thumb", "image_status", "sort_order"] + ([target.name_field] if target.name_field else [])
    if meta.model_name == "student":
        fields.append("name")
    def admin_url(name, *args):
        try:
            return reverse(f"admin:{meta.app_label}_{meta.model_name}_{name}", args=args)
        except NoReverseMatch:  # edited inline on its parent page, no screen of its own
            return ""

    items = []
    for obj in queryset.only(*fields).order_by("sort_order", "pk")[:GRID_LIMIT]:
        label = getattr(obj, target.name_field) if target.name_field else (getattr(obj, "name", "") or "Unnamed")
        items.append({
            "thumb": obj.thumb_url,
            "label": label,
            "status": obj.image_status,
            "status_label": obj.get_image_status_display(),
            "url": admin_url("change", obj.pk),
        })
    total = queryset.count()
    changelist = admin_url("changelist")
    return {
        "items": items,
        "total": total,
        "hidden": max(0, total - GRID_LIMIT),
        "changelist_url": (
            f"{changelist}?{target.grid_parent or target.parent}__id__exact={parent_id}" if changelist else ""),
    }


@staff_member_required
@require_GET
def grid(request):
    key = request.GET.get("target", "")
    _target(key, request.user, perm="view")
    parent = _int(request.GET.get("parent"), -1)
    if parent < 0:
        return _error("Missing parent")
    return render(request, "admin/core/upload_grid.html", grid_context(key, parent))


urlpatterns = [
    path("prepare/", prepare, name="admin-upload-prepare"),
    path("direct/", direct, name="admin-upload-direct"),
    path("grid/", grid, name="admin-upload-grid"),
    path("<uuid:batch_id>/commit/", commit, name="admin-upload-commit"),
    path("<uuid:batch_id>/status/", status, name="admin-upload-status"),
    path("<uuid:batch_id>/retry/", retry_failed, name="admin-upload-retry"),
]
