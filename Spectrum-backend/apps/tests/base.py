import io
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings

_cache = tempfile.mkdtemp(prefix="spectrum-test-cache-")

TEST_SETTINGS = dict(
    ALLOWED_HOSTS=["testserver"],
    TASKS_EAGER=True,
    PAYMENTS_MOCK=False,
    RAZORPAY_KEY_ID="rzp_test_key",
    RAZORPAY_KEY_SECRET="secret",
    RAZORPAY_WEBHOOK_SECRET="hooksecret",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    CACHES={"default": {"BACKEND": "django.core.cache.backends.filebased.FileBasedCache", "LOCATION": _cache}},
)


def jpeg_bytes(width=64, height=48, orientation=None, colour=(200, 40, 40)) -> bytes:
    from PIL import Image

    image = Image.new("RGB", (width, height), colour)
    buffer = io.BytesIO()
    kwargs = {}
    if orientation:
        exif = Image.Exif()
        exif[0x0112] = orientation
        kwargs["exif"] = exif
    image.save(buffer, "JPEG", **kwargs)
    return buffer.getvalue()


@override_settings(**TEST_SETTINGS)
class SpectrumTestCase(TestCase):
    def setUp(self):
        cache.clear()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        from django.conf import settings

        shutil.rmtree(settings.MEDIA_ROOT, ignore_errors=True)

    def make_catalog(self):
        from apps.catalog.models import Event, Institution, InstitutionKind

        school, _ = InstitutionKind.objects.get_or_create(slug="school",
                                                          defaults={"name": "School", "plural": "Schools"})
        self.institution = Institution.objects.create(slug="dps", name="Delhi Public School", city="New Delhi",
                                                      kind=school)
        self.other = Institution.objects.create(slug="doon", name="The Doon School", kind=school)
        self.event = Event.objects.create(slug="annual-day", name="Annual Day", institution=self.institution,
                                          price_per_photo=29, bundle_price=299)
        self.other_event = Event.objects.create(slug="founders", name="Founder's Day", institution=self.other)

    def make_staff(self):
        return get_user_model().objects.create_superuser("admin", "admin@example.com", "pass")

    def photo(self, event, title="Photo", sort_order=0):
        from django.core.files.base import ContentFile

        from apps.catalog.models import EventPhoto

        obj = EventPhoto(event=event, title=title, sort_order=sort_order)
        obj.original.save("p.jpg", ContentFile(jpeg_bytes()), save=False)
        with self.captureOnCommitCallbacks(execute=True):
            obj.save()
        obj.refresh_from_db()
        return obj
