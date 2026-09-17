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
from django.db.models import Count, Max
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


TARGETS = {
    "catalog.eventphoto": Target("catalog.EventPhoto", "event", "title", "Gallery photos"),
    # A fresh upload always starts by asking the institution for a caption; the
    # uploader's "Requested" tag can switch a batch to approval or correction.
    "portal.captionitem": Target(
        "portal.CaptionItem", "workspace", "moment_title", "Caption workspace photos",
        {"status": "needs-caption", "requested": "needs-caption"},
        choices={"requested": _request_tags}, mirror={"requested": "status"},
    ),
    "portal.student": Target("portal.Student", "school_class", None, "Student photos"),
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
    target = _target(str(data.get("target", "")), request.user)
    model = target.model_class
    parent_field = model._meta.get_field(target.parent)
    try:
        parent_id = int(data.get("parentId"))
    except (TypeError, ValueError):
        return _error("Missing parent")
    if not parent_field.related_model.objects.filter(pk=parent_id).exists():
        return _error("Parent not found", 404)

    batch = None
    try:
        batch_id = uuid.UUID(str(data.get("batchId"))) if data.get("batchId") else None
    except ValueError:
        batch_id = None
    if batch_id:
        batch = UploadBatch.objects.filter(pk=batch_id, target=target.model.lower(), parent_id=parent_id).first()
    if batch is None:
        top = model.objects.filter(**{parent_field.attname: parent_id}).aggregate(top=Max("sort_order"))["top"]
        batch = UploadBatch.objects.create(
            target=target.model.lower(),
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
    created, skipped = [], []
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
            obj = model(**{parent_attname: batch.parent_id}, **extra)
            obj.sort_order = batch.base_sort_order + index
            if target.name_field:
                setattr(obj, target.name_field, humanize(name))
            obj.original = key
            obj.save()
            UploadBatchFile.objects.create(batch=batch, client_id=client_id, object_id=obj.pk)
            created.append(client_id)
    return JsonResponse({"created": created, "skipped": skipped})


def _target_key(batch) -> str:
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
    parent_attname = meta.get_field(target.parent).attname
    queryset = model.objects.filter(**{parent_attname: parent_id})
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
        "changelist_url": f"{changelist}?{target.parent}__id__exact={parent_id}" if changelist else "",
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
