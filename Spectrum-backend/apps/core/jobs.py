"""Image processing and housekeeping jobs. Pillow is imported inside the jobs only."""

import io
import logging
import uuid
from datetime import timedelta

from django.apps import apps
from django.core.files.base import ContentFile
from django.utils import timezone

from spectrum.storages import public_storage

from .cache import bump_for
from .models import ImageStatus, delete_files
from .tasks import job

log = logging.getLogger(__name__)
_heif_registered = False

WEBP_QUALITY = 80


def _register_heif():
    global _heif_registered
    if _heif_registered:
        return
    try:
        from pillow_heif import register_heif_opener

        register_heif_opener()
    except ImportError:  # HEIC support is optional
        pass
    _heif_registered = True


@job("core.process_image")
def process_image(label: str, pk: int) -> None:
    model = apps.get_model(label)
    claimed = (
        model.objects.filter(pk=pk)
        .exclude(image_status=ImageStatus.EMPTY)
        .update(image_status=ImageStatus.PROCESSING, image_error="")
    )
    if not claimed:
        return
    obj = model.objects.get(pk=pk)
    from PIL import Image, UnidentifiedImageError

    try:
        updates = render_variants(obj)
    except (UnidentifiedImageError, Image.DecompressionBombError, SyntaxError, ValueError) as exc:
        # Not a usable image: retrying will not help.
        model.objects.filter(pk=pk).update(image_status=ImageStatus.FAILED, image_error=f"Not a readable image: {exc}"[:1000])
        bump_for(model)
        return
    except Exception as exc:
        model.objects.filter(pk=pk).update(image_status=ImageStatus.PENDING, image_error=str(exc)[:1000])
        raise
    old_files = updates.pop("_old_files")
    model.objects.filter(pk=pk).update(**updates, image_status=ImageStatus.READY, image_error="")
    bump_for(model)
    # Only now that the row points at the new files is it safe to remove the old ones.
    delete_files(public_storage(), old_files)


def render_variants(obj) -> dict:
    from PIL import Image, ImageOps

    _register_heif()
    # About 60 MP. Anything larger is rejected (DecompressionBombError -> failed)
    # instead of decoding into more memory than the worker is allowed.
    Image.MAX_IMAGE_PIXELS = 60_000_000
    sizes = sorted(obj.VARIANTS.items(), key=lambda item: item[1], reverse=True)
    largest = sizes[0][1]

    with obj.original.open("rb") as handle:
        image = Image.open(handle)
        orientation = image.getexif().get(0x0112, 1)
        width, height = image.size
        if orientation in (5, 6, 7, 8):
            width, height = height, width
        if image.format == "JPEG":
            # Decode at a reduced scale straight from the JPEG: a large memory saving.
            image.draft("RGB", (largest, largest))
        image.load()
    image = ImageOps.exif_transpose(image)
    has_alpha = image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info)
    image = image.convert("RGBA" if has_alpha else "RGB")

    storage = public_storage()
    folder = f"{obj._meta.app_label}/{obj._meta.model_name}"
    stem = uuid.uuid4().hex
    old_files = []
    updates = {"width": width, "height": height}
    # Largest first, shrinking the same image in place, so only one bitmap is alive.
    for name, size in sizes:
        image.thumbnail((size, size), Image.Resampling.LANCZOS, reducing_gap=3.0)
        output = watermark(image) if name in obj.WATERMARKED else image
        buffer = io.BytesIO()
        output.save(buffer, "WEBP", quality=WEBP_QUALITY, method=4)
        if output is not image:
            output.close()
        saved = storage.save(f"{folder}/{stem}-{name}.webp", ContentFile(buffer.getvalue()))
        buffer.close()
        old_files.append(str(getattr(obj, name) or ""))
        updates[name] = saved
    image.close()
    updates["_old_files"] = [name for name in old_files if name not in updates.values()]
    return updates


# Watermark opacity, out of 255: the white letterforms and the dark fringe that
# keeps them legible on a light photo. A third is where a watermark normally
# sits — present on every crop, never competing with the picture.
FILL_ALPHA = 84
FRINGE_ALPHA = 96


def watermark(image, text: str = "Preview Only"):
    """
    One big "Preview Only" running diagonally across the middle of the photo.
    Large enough that cropping it out leaves nothing usable, and translucent at
    the level a watermark normally sits at — around a third — so the photo
    underneath still reads properly.
    """
    from PIL import Image, ImageChops, ImageDraw, ImageFont

    base = image.convert("RGBA")
    width, height = base.size
    try:
        probe = ImageFont.load_default(size=100)
        # Size the type so the mark spans ~80% of the photo's width.
        span = ImageDraw.Draw(base).textlength(text, font=probe)
        font_size = max(18, int(100 * (width * 0.8) / max(span, 1)))
        font = ImageFont.load_default(size=font_size)
    except TypeError:  # Pillow built without FreeType: the bitmap font has one size
        font = ImageFont.load_default()
        font_size = 12
    scratch = ImageDraw.Draw(base)
    left, top, right, bottom = scratch.textbbox((0, 0), text, font=font)
    # The default face has no bold cut, so a stroke in the same colour thickens
    # the letters. `halo` is a second, slightly wider stroke used only as a dark
    # fringe outside them.
    stroke = max(1, font_size // 28)
    halo_width = max(1, font_size // 40)
    pad = font_size // 4 + stroke + halo_width + 4
    size = (right - left + pad * 2, bottom - top + pad * 2)
    origin = (pad - left, pad - top)

    def glyphs(extra: int = 0):
        """The letterforms as a coverage mask, so alpha is applied once, evenly."""
        mask = Image.new("L", size, 0)
        ImageDraw.Draw(mask).text(origin, text, font=font, fill=255, stroke_width=stroke + extra,
                                  stroke_fill=255)
        return mask

    body = glyphs()
    # Drawing the fill and its outline as two translucent passes compounds where
    # they overlap, which is what made the mark read as opaque with a lighter
    # edge. Painting through disjoint masks instead keeps one flat opacity: the
    # white sits at FILL everywhere, and the dark fringe lives strictly outside
    # it, only to hold the mark legible against a white sky or shirt.
    fringe = ImageChops.subtract(glyphs(halo_width), body)
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    layer.paste((0, 0, 0, 255), (0, 0), fringe.point(lambda v: v * FRINGE_ALPHA // 255))
    layer.paste((255, 255, 255, 255), (0, 0), body.point(lambda v: v * FILL_ALPHA // 255))
    body.close()
    fringe.close()

    rotated = layer.rotate(28, resample=Image.Resampling.BICUBIC, expand=True)
    layer.close()
    offset = ((width - rotated.width) // 2, (height - rotated.height) // 2)
    # Paste through a crop when the rotated mark is wider than a narrow photo.
    x0, y0 = max(0, -offset[0]), max(0, -offset[1])
    region = rotated.crop((x0, y0, min(rotated.width, x0 + width), min(rotated.height, y0 + height)))
    rotated.close()
    base.alpha_composite(region, (max(0, offset[0]), max(0, offset[1])))
    region.close()
    result = base.convert("RGB")
    base.close()
    return result


@job("core.delete_files")
def delete_files_job(alias: str, names: list[str]) -> None:
    from django.core.files.storage import storages

    delete_files(storages[alias], names)


@job("core.housekeeping")
def housekeeping() -> None:
    from .models import Task, UploadBatch

    now = timezone.now()
    from django.conf import settings

    from apps.orders.models import Order
    from spectrum.storages import private_storage

    for batch in UploadBatch.objects.filter(created_at__lt=now - timedelta(days=7)).iterator():
        remove_uncommitted_uploads(batch)
        batch.delete()
    Task.objects.filter(status=Task.FAILED, created_at__lt=now - timedelta(days=30)).delete()

    # A zip is a full copy of an album; after a while buyers use the per-photo links.
    old = Order.objects.exclude(zip_file="").filter(paid_at__lt=now - timedelta(days=settings.ORDER_ZIP_KEEP_DAYS))
    for pk, name in old.values_list("pk", "zip_file")[:200]:
        delete_files(private_storage(), [name])
        Order.objects.filter(pk=pk).update(zip_file="")


def remove_uncommitted_uploads(batch) -> None:
    """Files uploaded from a tab that closed before saving are deleted with their batch."""
    from spectrum.storages import private_storage

    from .uploads import TARGETS

    target = TARGETS.get(batch.target)
    if target is None or not batch.prepared_keys:
        return
    used = set(target.model_class.objects.filter(original__in=batch.prepared_keys).values_list("original", flat=True))
    delete_files(private_storage(), [key for key in batch.prepared_keys if key not in used])
