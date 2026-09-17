"""
Cut the photos already on the site to the frames the site used to force on them.

The galleries now show every photo at the proportions it was uploaded in. Until
this change they cropped everything into a fixed frame (gallery 4:5, caption
cards 4:3, student photos 3:4), and the existing photos were chosen to look
right that way. Cutting those files to the same frame keeps every current
page looking exactly as it did, while anything uploaded from now on is shown
whole.

Non-destructive: the cropped file is saved under a new key and the row is
pointed at it. The uncropped original stays where it was and is printed, so
it can be put back by hand if ever needed.
"""

import io
import os
from fractions import Fraction

from django.apps import apps
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError

from apps.core.models import ImageStatus, original_key
from apps.core.tasks import enqueue
from spectrum.storages import private_storage

FRAMES = {
    "catalog.eventphoto": (4, 5),
    "portal.captionitem": (4, 3),
    "portal.student": (3, 4),
}
FORMATS = {"JPEG": ("JPEG", {"quality": 95, "optimize": True}), "PNG": ("PNG", {}), "WEBP": ("WEBP", {"quality": 95})}


class Command(BaseCommand):
    help = "Centre-crop existing photos to the frame each gallery used to display them in."

    def add_arguments(self, parser):
        parser.add_argument("--model", action="append", choices=sorted(FRAMES), metavar="LABEL",
                            help="Only these (repeatable). Default: all of " + ", ".join(sorted(FRAMES)))
        parser.add_argument("--tolerance", type=float, default=0.02,
                            help="Skip photos already within this fraction of the target ratio (default 0.02).")
        parser.add_argument("--dry-run", action="store_true", help="Report what would change; write nothing.")

    def handle(self, *args, model, tolerance, dry_run, **options):
        from PIL import Image, ImageOps

        from apps.core.jobs import _register_heif

        _register_heif()
        storage = private_storage()
        labels = model or sorted(FRAMES)
        for label in labels:
            frame_w, frame_h = FRAMES[label]
            target = frame_w / frame_h
            cls = apps.get_model(label)
            rows = cls.objects.exclude(image_status=ImageStatus.EMPTY).exclude(original="").order_by("pk")
            cropped = skipped = failed = 0
            for obj in rows.only("pk", "original"):
                key = obj.original.name
                try:
                    with obj.original.open("rb") as handle:
                        image = ImageOps.exif_transpose(Image.open(handle))
                        image.load()
                        fmt = image.format or Image.open(handle).format
                except Exception as exc:  # unreadable file: leave it, say so
                    failed += 1
                    self.stderr.write(f"  {label} #{obj.pk}: could not read {key}: {exc}")
                    continue
                width, height = image.size
                if abs(width / height - target) <= tolerance:
                    skipped += 1
                    image.close()
                    continue
                box = _centre_box(width, height, frame_w, frame_h)
                self.stdout.write(f"  {label} #{obj.pk}: {width}x{height} -> {box[2] - box[0]}x{box[3] - box[1]}"
                                  f"{'' if dry_run else '  (uncropped file kept at ' + key + ')'}")
                if dry_run:
                    cropped += 1
                    image.close()
                    continue
                fmt_name, params = FORMATS.get(fmt or "", FORMATS["JPEG"])
                if fmt_name == "JPEG" and image.mode not in ("RGB", "L"):
                    image = image.convert("RGB")
                buffer = io.BytesIO()
                image.crop(box).save(buffer, fmt_name, **params)
                image.close()
                ext = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}[fmt_name]
                new_key = storage.save(original_key(cls, os.path.basename(key) or f"photo{ext}"), ContentFile(buffer.getvalue()))
                buffer.close()
                # Point the row at the cut file without going through save(), which
                # would delete the uncropped original — that file is the backup.
                cls.objects.filter(pk=obj.pk).update(original=new_key, image_status=ImageStatus.PENDING, image_error="")
                enqueue("core.process_image", label, obj.pk)
                cropped += 1
            verb = "would crop" if dry_run else "cropped"
            self.stdout.write(self.style.SUCCESS(
                f"{label}: {verb} {cropped}, already {frame_w}:{frame_h} {skipped}, unreadable {failed}"))
        if not dry_run:
            self.stdout.write("Web copies are being re-made; run the worker if it is not already running.")


def _centre_box(width: int, height: int, frame_w: int, frame_h: int) -> tuple[int, int, int, int]:
    """The largest frame_w:frame_h rectangle that fits, centred on the photo."""
    ratio = Fraction(frame_w, frame_h)
    if Fraction(width, height) > ratio:  # too wide: trim the sides
        new_w = int(height * ratio)
        left = (width - new_w) // 2
        return left, 0, left + new_w, height
    new_h = int(width / ratio)  # too tall: trim top and bottom
    top = (height - new_h) // 2
    return 0, top, width, top + new_h
