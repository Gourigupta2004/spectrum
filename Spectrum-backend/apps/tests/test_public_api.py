import json

from apps.content.models import Enquiry, HomePage, Stat

from .base import SpectrumTestCase


class PublicApiTests(SpectrumTestCase):
    def setUp(self):
        super().setUp()
        self.make_catalog()
        self.photo(self.event, "One", 0)
        self.photo(self.event, "Two", 1)

    def test_event_detail_shape(self):
        data = self.client.get("/api/events/annual-day/").json()
        self.assertEqual(data["event"]["photos"], 2)
        self.assertEqual(data["event"]["institutionId"], "dps")
        self.assertEqual(data["event"]["bundleSavings"], 0)
        self.assertEqual([p["title"] for p in data["photos"]], ["One", "Two"])
        self.assertIn("preview.webp", data["photos"][0]["image"])
        self.assertIn("Annual Day", data["seo"]["title"])

    def test_cache_is_invalidated_on_save(self):
        self.assertEqual(self.client.get("/api/pages/home/").json()["stats"], [])
        Stat.objects.create(value=5, label="Events")
        self.assertEqual(len(self.client.get("/api/pages/home/").json()["stats"]), 1)
        page = HomePage.load()
        page.hero_title = "New [title]"
        page.save()
        self.assertEqual(self.client.get("/api/pages/home/").json()["copy"]["heroTitle"], "New [title]")

    def test_institution_routing_fields(self):
        institutions = {i["id"]: i for i in self.client.get("/api/events/").json()["institutions"]}
        self.assertEqual(institutions["dps"]["eventCount"], 1)
        self.assertEqual(institutions["dps"]["firstEventSlug"], "annual-day")

    def test_footer_comes_from_site_settings(self):
        from apps.content.models import SiteSettings

        copy = self.client.get("/api/site/").json()["copy"]
        self.assertEqual(copy["footerTagline"], "Imagination That Works")
        self.assertEqual(copy["footerEmail"], "spectrum.support2026@gmail.com")
        self.assertEqual(copy["footerCopyright"], "© {year} Spectrum. All rights reserved.")
        self.assertEqual(copy["footerInstagramUrl"], "")
        site = SiteSettings.load()
        site.footer_instagram_url = "https://instagram.com/spectrum"
        site.footer_phone = "+91 98765 43210"
        site.save()
        copy = self.client.get("/api/site/").json()["copy"]
        self.assertEqual(copy["footerInstagramUrl"], "https://instagram.com/spectrum")
        self.assertEqual(copy["footerPhone"], "+91 98765 43210")

    def test_cors_header(self):
        response = self.client.get("/api/site/", HTTP_ORIGIN="http://localhost:8080")
        self.assertEqual(response["Access-Control-Allow-Origin"], "http://localhost:8080")
        response = self.client.get("/api/site/", HTTP_ORIGIN="https://evil.example")
        self.assertFalse(response.has_header("Access-Control-Allow-Origin"))

    def test_contact_validation_and_create(self):
        bad = self.client.post("/api/contact/", json.dumps({"name": "A"}), content_type="application/json")
        self.assertEqual(bad.status_code, 400)
        good = self.client.post("/api/contact/", json.dumps({
            "name": "Asha", "email": "asha@example.com", "service": "Other", "serviceOther": "Drone"}),
            content_type="application/json")
        self.assertEqual(good.status_code, 201)
        self.assertEqual(Enquiry.objects.get().service, "Other: Drone")


class EventOrderAndRecentTests(SpectrumTestCase):
    """The All Events page: newest first, and Recent on its own for the last two months."""

    def setUp(self):
        super().setUp()
        self.make_catalog()

    def test_newest_first_and_recent_by_date(self):
        import datetime

        from django.utils import timezone

        from apps.catalog.models import Event

        today = timezone.localdate()
        Event.objects.filter(pk=self.event.pk).update(date=today - datetime.timedelta(days=200), sort_order=0,
                                                      is_recent=False)
        Event.objects.filter(pk=self.other_event.pk).update(date=today - datetime.timedelta(days=10), sort_order=9)
        Event.objects.create(slug="undated", name="Undated", institution=self.institution)
        Event.objects.create(slug="flagged", name="Flagged", institution=self.other, sort_order=0,
                             date=today - datetime.timedelta(days=400), is_recent=True)
        events = self.client.get("/api/events/").json()["events"]
        self.assertEqual([e["slug"] for e in events], ["founders", "annual-day", "flagged", "undated"],
                         "newest date first, whatever the admin order; undated last")
        tags = {e["slug"]: e["tags"] for e in events}
        self.assertIn("recent", tags["founders"], "dated within two months: Recent on its own")
        self.assertNotIn("recent", tags["annual-day"])
        self.assertIn("recent", tags["flagged"], "the tick box still tags older events")

    def test_months_before(self):
        import datetime

        from apps.catalog.models import months_before

        self.assertEqual(months_before(datetime.date(2026, 10, 13), 2), datetime.date(2026, 8, 13))
        self.assertEqual(months_before(datetime.date(2026, 12, 31), 2), datetime.date(2026, 10, 31))
        self.assertEqual(months_before(datetime.date(2026, 4, 30), 2), datetime.date(2026, 2, 28))
        self.assertEqual(months_before(datetime.date(2026, 1, 15), 2), datetime.date(2025, 11, 15))
