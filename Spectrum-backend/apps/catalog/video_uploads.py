"""
Event video uploads that start the moment a file is chosen.

The video field on the event page uploads on its own, with a progress bar:
  1. prepare -> a storage key, a signed token, and where to send the bytes
                (a presigned S3 PUT, or the local `direct` endpoint)
  2. upload  -> the browser sends the file there and shows its progress
  3. Save    -> the form carries only the token; the row takes the stored key

Keys handed out are remembered on an UploadBatch, so housekeeping deletes
files whose form was never saved.
"""

import os

from django import forms
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.core import signing
from django.http import JsonResponse
from django.urls import path, reverse
from django.views.decorators.http import require_POST

from apps.core.models import UploadBatch
from apps.core.uploads import _body, _error, _int, _is_s3, _presign_put
from spectrum.storages import private_storage

from .models import VIDEO_EXTENSIONS, video_upload_to

TOKEN_SALT = "catalog.video-upload"
TOKEN_MAX_AGE = 24 * 3600
BATCH_TARGET = "catalog.eventvideo"
# A single S3 PUT stops at 5 GB.
S3_PUT_MAX_BYTES = 5 * 1024 ** 3


def max_bytes() -> int:
    limit = settings.VIDEO_UPLOAD_MAX_BYTES
    return min(limit, S3_PUT_MAX_BYTES) if _is_s3(private_storage()) else limit


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
]
