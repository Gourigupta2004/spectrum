"""
Loads the website's hardcoded demo data into the database, downloading every image
into storage, so nothing has to be uploaded by hand.

    bun scripts/export-fixtures.ts            # in Spectrum-website, refreshes seed/fixtures.json
    python manage.py seed_fixtures             # safe to re-run: only creates what is missing

Existing rows are never overwritten, so admin edits survive a re-run.
"""

import colorsys
import hashlib
import io
import json
import secrets
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, time
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.catalog.models import Event, EventPhoto, Institution
from apps.content.models import (
    Capability, ContactDetail, Faq, HeroSlide, Service, SiteSettings, Stat, StoryBlock, TieUp,
)
from apps.portal.models import CaptionItem, Member, SchoolClass, Student

SEED_DIR = settings.BASE_DIR / "seed"


class Command(BaseCommand):
    help = "Seed the database from seed/fixtures.json (images are downloaded once and cached in seed/cache)."

    def add_arguments(self, parser):
        parser.add_argument("--fixtures", default=str(SEED_DIR / "fixtures.json"))
        parser.add_argument("--website", default=str(settings.BASE_DIR.parent / "Spectrum-website" / "public"),
                            help="Folder holding the logo, favicon and intro video.")
        parser.add_argument("--skip-images", action="store_true", help="Create rows without downloading images.")
        parser.add_argument("--sync", action="store_true",
                            help="Make image variants now instead of leaving them for the worker.")
        parser.add_argument("--demo-logins", action="store_true",
                            help="Also create the demo portal logins when DEBUG is off (they have known passwords).")

    def handle(self, *args, fixtures, website, skip_images, sync, demo_logins, **options):
        path = Path(fixtures)
        if not path.is_file():
            raise CommandError(f"{path} not found. Run `bun scripts/export-fixtures.ts` in Spectrum-website first.")
        if sync:
            settings.TASKS_EAGER = True
        self.data = json.loads(path.read_text())
        self.skip_images = skip_images
        self.demo_logins = demo_logins or settings.DEBUG
        self.cache_dir = SEED_DIR / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        if not skip_images:
            self.prefetch()

        self.site_files(Path(website))
        self.home()
        self.about()
        self.contact()
        institutions = self.institutions()
        events = self.events(institutions)
        self.gallery(events)
        self.portal(institutions, events)
        self.stdout.write(self.style.SUCCESS("Seed complete."))
        if not sync and not settings.TASKS_EAGER:
            self.stdout.write("Images are queued. Run `python manage.py runworker` to make the web versions.")

    # ------------------------------------------------------------------ images

    def image_urls(self) -> set[str]:
        d = self.data
        urls = {i["image"] for i in d["institutions"]} | {e["image"] for e in d["events"]}
        urls |= {p["image"] for p in d["gallery"]} | {s["image"] for s in d["heroSlides"]}
        urls |= {s["image"] for s in d["story"]} | {t["image"] for t in d["tieUps"]}
        urls |= {c["image"] for c in d["portal"]["captions"]}
        return {u for u in urls if u and u.startswith("http")}

    def cache_path(self, url: str) -> Path:
        return self.cache_dir / (hashlib.sha1(url.encode()).hexdigest() + ".jpg")

    def prefetch(self):
        urls = [u for u in self.image_urls() if not self.cache_path(u).exists()]
        if not urls:
            return
        self.stdout.write(f"Downloading {len(urls)} images…")

        def fetch(url):
            request = urllib.request.Request(url, headers={"User-Agent": "Spectrum-seed/1.0"})
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    self.cache_path(url).write_bytes(response.read())
                return None
            except Exception as exc:
                return f"{url}: {exc}"

        with ThreadPoolExecutor(max_workers=6) as pool:
            for error in pool.map(fetch, urls):
                if error:
                    self.stderr.write(f"  could not download {error}")

    def attach(self, obj, url: str, name: str):
        """Put a downloaded image into obj.original; saving obj queues the variants."""
        if self.skip_images or obj.original:
            return
        cached = self.cache_path(url)
        if cached.exists():
            obj.original.save(name, ContentFile(cached.read_bytes()), save=False)

    # ------------------------------------------------------------------ pages

    def site_files(self, folder: Path):
        site = SiteSettings.load()
        files = {
            "logo_light": "spectrum-logo-light.png",
            "logo_mark": "spectrum-mark.png",
            "favicon": "favicon.png",
            "intro_video_webm": "spr-intro.webm",
            "intro_video_mp4": "spr-intro.mp4",
        }
        changed = False
        for field, filename in files.items():
            source = folder / filename
            if not getattr(site, field) and source.is_file():
                getattr(site, field).save(filename, ContentFile(source.read_bytes()), save=False)
                changed = True
        if changed:
            site.save()
            self.stdout.write("Site logos and intro video stored.")

    def home(self):
        if not Stat.objects.exists():
            Stat.objects.bulk_create(
                [Stat(value=s["to"], suffix=s["suffix"], label=s["label"], sort_order=i)
                 for i, s in enumerate(self.data["stats"])])
        if not Service.objects.exists():
            Service.objects.bulk_create([Service(label=label, sort_order=i)
                                         for i, label in enumerate(self.data["services"])])
        existing = set(HeroSlide.objects.values_list("sort_order", flat=True))
        for i, slide in enumerate(self.data["heroSlides"]):
            if i in existing:
                continue
            obj = HeroSlide(caption=slide["caption"], sort_order=i)
            self.attach(obj, slide["image"], f"hero-{i}.jpg")
            obj.save()
        self.stdout.write("Home page seeded.")

    def about(self):
        if not Capability.objects.exists():
            Capability.objects.bulk_create([Capability(label=label, sort_order=i)
                                            for i, label in enumerate(self.data["capabilities"])])
        if not Faq.objects.exists():
            Faq.objects.bulk_create([Faq(question=f["q"], answer=f["a"], sort_order=i)
                                     for i, f in enumerate(self.data["faqs"])])
        titles = set(StoryBlock.objects.values_list("title", flat=True))
        for i, block in enumerate(self.data["story"]):
            if block["title"] in titles:
                continue
            obj = StoryBlock(title=block["title"], body=block["body"], alt=block["alt"], sort_order=i)
            self.attach(obj, block["image"], f"story-{i}.jpg")
            obj.save()
        names = set(TieUp.objects.values_list("name", flat=True))
        for i, tie in enumerate(self.data["tieUps"]):
            if tie["name"] in names:
                continue
            obj = TieUp(name=tie["name"], years=tie["years"], sort_order=i)
            self.attach(obj, tie["image"], f"tieup-{i}.jpg")
            obj.save()
        self.stdout.write("About page seeded.")

    def contact(self):
        if not ContactDetail.objects.exists():
            ContactDetail.objects.bulk_create(
                [ContactDetail(icon=d["icon"], label=d["label"], value=d["value"], sort_order=i)
                 for i, d in enumerate(self.data["contactDetails"])])
        self.stdout.write("Contact page seeded.")

    # ------------------------------------------------------------------ catalog

    def institutions(self) -> dict:
        found = {i.slug: i for i in Institution.objects.all()}
        for index, data in enumerate(self.data["institutions"]):
            if data["id"] in found:
                continue
            obj = Institution(slug=data["id"], name=data["name"], short=data["short"], city=data["city"],
                              kind=data["type"], sort_order=index)
            self.attach(obj, data["image"], f"{data['id']}.jpg")
            obj.save()
            found[obj.slug] = obj
        self.stdout.write(f"{len(found)} institutions.")
        return found

    def events(self, institutions) -> dict:
        found = {e.slug: e for e in Event.objects.all()}
        for data in self.data["events"]:
            if data["slug"] in found:
                continue
            obj = Event(
                slug=data["slug"], name=data["name"], institution=institutions[data["institutionId"]],
                date=parse_date(data["date"]), price_per_photo=data["pricePerPhoto"], bundle_price=299,
                is_recent="recent" in data["tags"], is_popular="popular" in data["tags"],
                sort_order=data.get("sortOrder", 0),
            )
            self.attach(obj, data["image"], f"{data['slug']}.jpg")
            obj.save()
            found[obj.slug] = obj
        self.stdout.write(f"{len(found)} events.")
        return found

    def gallery(self, events):
        for event in events.values():
            existing = set(EventPhoto.objects.filter(event=event).values_list("sort_order", flat=True))
            with transaction.atomic():
                for i, photo in enumerate(self.data["gallery"]):
                    if i in existing:
                        continue
                    obj = EventPhoto(event=event, title=photo["title"], sort_order=i)
                    self.attach(obj, photo["image"], f"{event.slug}-{i}.jpg")
                    obj.save()
        self.stdout.write("Event galleries seeded.")

    # ------------------------------------------------------------------ portal

    def portal(self, institutions, events):
        portal = self.data["portal"]
        institution = institutions[portal["institutionId"]]
        event = events.get(portal.get("event") or "")

        User = get_user_model()
        login = portal["login"]
        if not self.demo_logins:
            self.stdout.write("Skipped demo portal logins (DEBUG is off). Create logins in the admin, or pass --demo-logins.")
        elif not User.objects.filter(username=login["username"]).exists():
            user = User.objects.create_user(login["username"], password=login["password"])
            Member.objects.create(user=user, institution=institution, role=Member.INSTITUTION,
                                  display_name=institution.name)
            self.stdout.write(f"Portal login {login['username']} / {login['password']} created.")
        if self.demo_logins and not User.objects.filter(username="spectrum-team").exists():
            password = secrets.token_urlsafe(9)
            user = User.objects.create_user("spectrum-team", password=password)
            Member.objects.create(user=user, role=Member.SPECTRUM, display_name="Spectrum team")
            self.stdout.write(self.style.WARNING(f"Portal login spectrum-team / {password} created (note it down)."))

        if event is not None:
            existing = set(CaptionItem.objects.filter(event=event).values_list("sort_order", flat=True))
            with transaction.atomic():
                for item in portal["captions"]:
                    if item["sortOrder"] in existing:
                        continue
                    obj = CaptionItem(
                        event=event, institution=institution, moment_title=item["momentTitle"],
                        caption=item["caption"], correction=item["correction"], requested=item["requested"],
                        status=item["status"], action_by=item["actionBy"],
                        updated_at=parse_datetime(item["updatedAt"]), sort_order=item["sortOrder"],
                    )
                    self.attach(obj, item["image"], f"caption-{item['key']}.jpg")
                    obj.save()

        for data in portal["classes"]:
            cls, _ = SchoolClass.objects.get_or_create(
                institution=institution, slug=data["id"],
                defaults={"name": data["name"], "group": data["group"], "sort_order": data["sortOrder"]},
            )
            existing = set(Student.objects.filter(school_class=cls).values_list("sort_order", flat=True))
            with transaction.atomic():
                for index, student in enumerate(data["students"]):
                    if index in existing:
                        continue
                    obj = Student(school_class=cls, name=student["name"], sort_order=index)
                    if not self.skip_images:
                        obj.original.save(f"{student['key']}.png", ContentFile(avatar_png(student["hue"])), save=False)
                    obj.save()
        self.stdout.write(f"{len(portal['classes'])} classes with students seeded.")


def parse_date(label: str):
    try:
        return datetime.strptime(label, "%B %d, %Y").date()
    except (TypeError, ValueError):
        return None


def parse_datetime(label: str):
    day = parse_date(label)
    if day is None:
        return timezone.now()
    return timezone.make_aware(datetime.combine(day, time(12, 0)))


def _hsl(h: float, s: float, l: float) -> tuple[int, int, int]:
    r, g, b = colorsys.hls_to_rgb(h / 360, l, s)
    return round(r * 255), round(g * 255), round(b * 255)


def avatar_png(hue: int) -> bytes:
    """The same passport-style placeholder the site draws as SVG, as a real PNG."""
    from PIL import Image, ImageDraw

    width, height = 300, 400
    top, bottom = _hsl(hue, 0.32, 0.74), _hsl((hue + 40) % 360, 0.28, 0.56)
    image = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(image)
    for y in range(height):
        t = y / (height - 1)
        draw.line([(0, y), (width, y)], fill=tuple(round(a + (b - a) * t) for a, b in zip(top, bottom)))
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    shape = ImageDraw.Draw(overlay)
    white = (255, 255, 255, 235)
    shape.ellipse((150 - 66, 152 - 66, 150 + 66, 152 + 66), fill=white)
    shape.chord((38, 236, 262, 428), 180, 360, fill=white)
    shape.rectangle((38, 332, 262, 400), fill=white)
    image = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
    buffer = io.BytesIO()
    image.save(buffer, "PNG", optimize=True)
    return buffer.getvalue()
