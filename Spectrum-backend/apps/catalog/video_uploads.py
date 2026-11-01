"""
Event video uploads that start the moment a file is chosen.

The video field on the event page uploads on its own, with a progress bar:
  1. prepare -> a storage key, a signed token, and where to send the bytes
                (a presigned S3 PUT, or the local `direct` endpoint)
  2. upload  -> the browser sends the file there and shows its progress
  3. Save    -> the form carries only the token; the row takes the stored key

On S3, a video over MULTIPART_THRESHOLD goes up in parts instead: one S3 PUT
stops at 5 GB, and a dropped connection then costs one part, not the whole
file. `parts` presigns part URLs as the browser gets to them, and `complete`
asks S3 for the parts it holds and joins them, so the browser never needs to
read S3's ETag headers (no bucket CORS change).

Keys handed out are remembered on an UploadBatch, so housekeeping deletes
files whose form was never saved.
"""

import math
import os
from datetime import timedelta

from django import forms
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.core import signing
from django.http import JsonResponse
from django.urls import path, reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.models import UploadBatch
from apps.core.uploads import _body, _error, _int, _is_s3, _presign_put
from spectrum.storages import private_storage

from .models import VIDEO_EXTENSIONS, video_upload_to

TOKEN_SALT = "catalog.video-upload"
TOKEN_MAX_AGE = 24 * 3600
BATCH_TARGET = "catalog.eventvideo"
VIDEO_PREFIX = "catalog/eventvideo/videos/"
# Above this, an S3 upload goes in parts (a single S3 PUT stops at 5 GB anyway).
MULTIPART_THRESHOLD = 200 * 1024 ** 2
MIN_PART_BYTES = 64 * 1024 ** 2
MAX_PARTS = 10_000  # S3's limit per upload
PART_URLS_PER_CALL = 50
PART_URL_EXPIRES = 6 * 3600
# Parts of an upload nobody completed are abandoned after this; housekeeping aborts them.
STALE_MULTIPART = timedelta(days=2)


def max_bytes() -> int:
    return settings.VIDEO_UPLOAD_MAX_BYTES


def part_size(size: int) -> int:
    """At least 64 MB, and large enough to stay within S3's 10,000 parts."""
    mib = 1024 ** 2
    return max(MIN_PART_BYTES, math.ceil(size / MAX_PARTS / mib) * mib)


def _s3(storage):
    return storage.connection.meta.client, storage.bucket_name


def unsign(token: str) -> str | None:
    try:
        return signing.loads(token, salt=TOKEN_SALT, max_age=TOKEN_MAX_AGE)
    except (signing.BadSignature, TypeError):
        return None


def _allowed(user) -> bool:
    return user.has_perm("catalog.add_eventvideo") or user.has_perm("catalog.change_eventvideo")


@staff_member_required
@require_POST
def prepare(request):
    if not _allowed(request.user):
        return _error("Not allowed", 403)
    data = _body(request)
    name = str(data.get("name", ""))[:200]
    size = _int(data.get("size"))
    ext = os.path.splitext(name)[1].lower()
    if ext not in VIDEO_EXTENSIONS:
        return _error(f"{ext or 'This file type'} is not a video. Use MP4, MOV or WebM.")
    if size <= 0:
        return _error("The file is empty.")
    if size > max_bytes():
        return _error(f"The file is larger than {max_bytes() / 1024 ** 3:.0f} GB.")
    key = video_upload_to(None, name)
    UploadBatch.objects.create(target=BATCH_TARGET, prepared_keys=[key], created_by=request.user)
    entry = {"token": signing.dumps(key, salt=TOKEN_SALT)}
    storage = private_storage()
    if _is_s3(storage):
        content_type = str(data.get("type") or "application/octet-stream")[:100]
        if size > MULTIPART_THRESHOLD:
            client, bucket = _s3(storage)
            upload = client.create_multipart_upload(Bucket=bucket, Key=storage._normalize_name(key),
                                                    ContentType=content_type)
            entry.update(method="MULTIPART", uploadId=upload["UploadId"], partSize=part_size(size),
                         partsUrl=reverse("admin-video-upload-parts"),
                         completeUrl=reverse("admin-video-upload-complete"),
                         abortUrl=reverse("admin-video-upload-abort"))
        else:
            entry.update(method="PUT", uploadUrl=_presign_put(storage, key, content_type),
                         headers={"Content-Type": content_type})
    else:
        entry.update(method="POST", uploadUrl=reverse("admin-video-upload-direct"))
    return JsonResponse(entry)


@staff_member_required
@require_POST
def direct(request):
    if not _allowed(request.user):
        return _error("Not allowed", 403)
    key = unsign(request.POST.get("token", ""))
    upload = request.FILES.get("file")
    if not key or upload is None:
        return _error("Invalid upload")
    if upload.size > max_bytes():
        return _error("File too large")
    storage = private_storage()
    if not storage.exists(key):
        storage.save(key, upload)
    return JsonResponse({"ok": True})


def _multipart(request):
    """The upload a parts/complete/abort call is about: (storage, S3 key, upload id),
    or an error response. The key comes from the signed token, never the browser."""
    if not _allowed(request.user):
        return _error("Not allowed", 403)
    data = _body(request)
    key = unsign(str(data.get("token", "")))
    upload_id = str(data.get("uploadId", ""))[:1024]
    storage = private_storage()
    if not key or not upload_id or not _is_s3(storage):
        return _error("Invalid upload")
    return storage, storage._normalize_name(key), upload_id, data


@staff_member_required
@require_POST
def parts(request):
    """Presigned URLs for the next parts, a batch at a time, so a slow upload
    never holds a link past its expiry."""
    found = _multipart(request)
    if isinstance(found, JsonResponse):
        return found
    storage, key, upload_id, data = found
    numbers = data.get("numbers")
    numbers = [n for n in (numbers if isinstance(numbers, list) else []) if isinstance(n, int) and 1 <= n <= MAX_PARTS]
    client, bucket = _s3(storage)
    urls = {str(n): client.generate_presigned_url(
        "upload_part", Params={"Bucket": bucket, "Key": key, "UploadId": upload_id, "PartNumber": n},
        ExpiresIn=PART_URL_EXPIRES) for n in numbers[:PART_URLS_PER_CALL]}
    return JsonResponse({"urls": urls})


@staff_member_required
@require_POST
def complete(request):
    """Joins the parts S3 holds into the video."""
    found = _multipart(request)
    if isinstance(found, JsonResponse):
        return found
    storage, key, upload_id, data = found
    from botocore.exceptions import ClientError

    client, bucket = _s3(storage)
    held, marker = [], None
    try:
        while True:
            page = client.list_parts(Bucket=bucket, Key=key, UploadId=upload_id,
                                     **({"PartNumberMarker": marker} if marker else {}))
            held += [{"PartNumber": p["PartNumber"], "ETag": p["ETag"]} for p in page.get("Parts", [])]
            if not page.get("IsTruncated"):
                break
            marker = page["NextPartNumberMarker"]
        expected = _int(data.get("parts"))
        if not held or (expected and len(held) != expected):
            return _error(f"Only {len(held)} of {expected or '?'} parts arrived. Choose the file again.", 409)
        client.complete_multipart_upload(Bucket=bucket, Key=key, UploadId=upload_id,
                                         MultipartUpload={"Parts": sorted(held, key=lambda p: p["PartNumber"])})
    except ClientError as exc:
        return _error(f"Storage refused the upload ({exc.response.get('Error', {}).get('Code', 'error')}). "
                      "Choose the file again.", 502)
    return JsonResponse({"ok": True})


@staff_member_required
@require_POST
def abort(request):
    found = _multipart(request)
    if isinstance(found, JsonResponse):
        return found
    from botocore.exceptions import ClientError

    storage, key, upload_id, _ = found
    client, bucket = _s3(storage)
    try:
        client.abort_multipart_upload(Bucket=bucket, Key=key, UploadId=upload_id)
    except ClientError:
        pass  # already gone; housekeeping catches anything left
    return JsonResponse({"ok": True})


def abort_stale_multipart_uploads() -> int:
    """Parts of uploads left unfinished (a closed tab, a failure) still take
    up storage until aborted; housekeeping calls this."""
    storage = private_storage()
    if not _is_s3(storage):
        return 0
    client, bucket = _s3(storage)
    cutoff = timezone.now() - STALE_MULTIPART
    aborted = 0
    kwargs = {"Bucket": bucket, "Prefix": storage._normalize_name(VIDEO_PREFIX)}
    while True:
        page = client.list_multipart_uploads(**kwargs)
        for upload in page.get("Uploads", []):
            if upload["Initiated"] < cutoff:
                client.abort_multipart_upload(Bucket=bucket, Key=upload["Key"], UploadId=upload["UploadId"])
                aborted += 1
        if not page.get("IsTruncated"):
            return aborted
        kwargs.update(KeyMarker=page["NextKeyMarker"], UploadIdMarker=page["NextUploadIdMarker"])


class VideoUploadWidget(forms.Widget):
    """A file picker that uploads straight away; the hidden input it fills
    with the upload's token is what the form sends. A plain Widget, not a
    HiddenInput, so the inline still gives it a column."""

    template_name = "admin/catalog/video_upload_input.html"
    current = ""  # the row's stored video, set by the form

    class Media:
        js = ("catalog/video-upload.js",)
        css = {"all": ("catalog/video-upload.css",)}

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context.update(
            current=os.path.basename(self.current) if self.current else "",
            prepare_url=reverse("admin-video-upload-prepare"),
            max_bytes=max_bytes(),
            accept=",".join(sorted(VIDEO_EXTENSIONS)),
        )
        return context


class EventVideoForm(forms.ModelForm):
    video = forms.CharField(label="Video file", required=False, widget=VideoUploadWidget)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Starts empty, so a row whose video wasn't replaced counts as unchanged.
        self.initial["video"] = ""
        self.fields["video"].widget.current = self.instance.video.name if self.instance.video else ""

    def clean_video(self):
        token = self.cleaned_data.get("video") or ""
        if not token:
            if self.instance.video:
                return self.instance.video.name
            raise forms.ValidationError("Choose the video file and wait for its upload to finish.")
        key = unsign(token)
        if not key:
            raise forms.ValidationError("This upload has expired. Choose the video file again.")
        if not private_storage().exists(key):
            raise forms.ValidationError("The video didn't finish uploading. Choose the file again.")
        return key


urlpatterns = [
    path("prepare/", prepare, name="admin-video-upload-prepare"),
    path("direct/", direct, name="admin-video-upload-direct"),
    path("parts/", parts, name="admin-video-upload-parts"),
    path("complete/", complete, name="admin-video-upload-complete"),
    path("abort/", abort, name="admin-video-upload-abort"),
]
