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
