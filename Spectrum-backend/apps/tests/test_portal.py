import json

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.portal.models import CaptionItem, CaptionWorkspace, Member, PortalAccessEmail, SchoolClass, Student

from .base import SpectrumTestCase, jpeg_bytes


class PortalTests(SpectrumTestCase):
    def setUp(self):
        super().setUp()
        self.make_catalog()
        user = get_user_model().objects.create_user("dps-newdelhi", password="demo")
        self.member = Member.objects.create(user=user, institution=self.institution)
        self.token = self.login("dps-newdelhi", "demo")["access"]

    def login(self, username, password):
        return self.client.post("/api/portal/login/", json.dumps({"username": username, "password": password}),
                                content_type="application/json").json()

    def api(self, method, url, data=None):
        auth = {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}
        if method == "get":
            return self.client.get(url, **auth)
        return getattr(self.client, method)(url, json.dumps(data or {}), content_type="application/json", **auth)

    def caption(self, event, status):
        item = CaptionItem(event=event, moment_title="Moment", caption="Draft", status=status, requested="needs-approval")
        item.original.save("c.jpg", ContentFile(jpeg_bytes()), save=False)
        with self.captureOnCommitCallbacks(execute=True):
            item.save()
        return item

    def test_bad_login_and_missing_token(self):
        self.assertIn("error", self.login("dps-newdelhi", "wrong"))
        self.assertEqual(self.client.get("/api/portal/me/").status_code, 401)

    def test_sign_out_everywhere_invalidates_tokens(self):
        self.assertEqual(self.api("get", "/api/portal/me/").status_code, 200)
        Member.objects.filter(pk=self.member.pk).update(token_version=2)
        self.assertEqual(self.api("get", "/api/portal/me/").status_code, 401)

    def test_captions_are_scoped_to_institution(self):
        mine = self.caption(self.event, "needs-approval")
        theirs = self.caption(self.other_event, "needs-approval")
        ids = [i["id"] for i in self.api("get", "/api/portal/captions/").json()["items"]]
        self.assertEqual(ids, [str(mine.pk)])
        response = self.api("post", f"/api/portal/captions/{theirs.pk}/resolve/", {"status": "approved", "actionBy": "A. K", "actionByPhone": "9876500000"})
        self.assertEqual(response.status_code, 404)

    def test_caption_state_machine(self):
        item = self.caption(self.event, "needs-caption")
        url = f"/api/portal/captions/{item.pk}/resolve/"
        self.assertEqual(self.api("post", url, {"text": "Hello"}).status_code, 400)  # name required
        data = self.api("post", url, {"text": "Lamp lighting", "actionBy": "R. Menon", "actionByPhone": "98765 43210"}).json()
        self.assertEqual((data["status"], data["caption"]), ("corrected", "Lamp lighting"))
        # Saving locks the item: no teacher can act on it again.
        self.assertEqual(self.api("post", url, {"text": "Again", "actionBy": "S. Rao", "actionByPhone": "9876500000"}).status_code, 409)

        approval = self.caption(self.event, "needs-approval")
        url = f"/api/portal/captions/{approval.pk}/resolve/"
        # The approval screen is the last chance to adjust the wording.
        data = self.api("post", url, {"status": "approved", "text": "Final wording", "actionBy": "A. Kapoor", "actionByPhone": "9876543210"}).json()
        self.assertEqual((data["status"], data["caption"]), ("approved", "Final wording"))
        self.assertEqual(self.api("post", url, {"status": "approved", "actionBy": "A. Kapoor", "actionByPhone": "9876543210"}).status_code, 409)

    def test_institution_cannot_add_photos(self):
        response = self.client.post("/api/portal/captions/", {"momentTitle": "x"}, HTTP_AUTHORIZATION=f"Bearer {self.token}")
        self.assertEqual(response.status_code, 403)

    def test_names_are_saved_in_bulk(self):
        cls = SchoolClass.objects.create(institution=self.institution, name="6C", group="Middle")
        students = Student.objects.bulk_create([Student(school_class=cls, sort_order=i) for i in range(3)])
        SchoolClass.objects.create(institution=self.other, name="6C")
        names = {str(students[0].pk): "Aarav Sharma", str(students[2].pk): "  Kabir Nair "}
        result = self.api("put", "/api/portal/classes/6c/names/", {"names": names}).json()
        self.assertEqual(result, {"updated": 2, "namedCount": 2})
        detail = self.api("get", "/api/portal/classes/6c/").json()
        self.assertEqual([s["name"] for s in detail["students"]], ["Aarav Sharma", "", "Kabir Nair"])
        listing = self.api("get", "/api/portal/classes/").json()
        self.assertEqual(listing["totals"], {"students": 3, "named": 2})


class PortalAccessTests(SpectrumTestCase):
    """The email step that unlocks the portal, and the institution check on login."""

    def setUp(self):
        super().setUp()
        self.make_catalog()
        user = get_user_model().objects.create_user("dps-newdelhi", password="demo")
        Member.objects.create(user=user, institution=self.institution)
        PortalAccessEmail.objects.create(institution=self.institution, email="Principal@DPS.edu ")
        PortalAccessEmail.objects.create(institution=self.other, email="head@doon.edu")

    def post(self, url, data):
        return self.client.post(url, json.dumps(data), content_type="application/json")

    def test_access_email_names_its_institution(self):
        response = self.post("/api/portal/access/", {"email": "principal@dps.edu"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"email": "principal@dps.edu",
                                           "institution": {"id": "dps", "name": "Delhi Public School", "city": "New Delhi"}})
        self.assertEqual(self.post("/api/portal/access/", {"email": "nobody@example.com"}).status_code, 403)
        self.assertEqual(self.post("/api/portal/access/", {"email": "not-an-email"}).status_code, 400)

    def test_login_must_match_the_unlocked_institution(self):
        mismatch = self.post("/api/portal/login/", {"username": "dps-newdelhi", "password": "demo", "email": "head@doon.edu"})
        self.assertEqual(mismatch.status_code, 403)
        ok = self.post("/api/portal/login/", {"username": "dps-newdelhi", "password": "demo", "email": "principal@dps.edu"})
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.json()["member"]["institution"]["id"], "dps")


class CaptionWorkspaceTests(SpectrumTestCase):
    """Bulk uploads land in the institution's workspace, tagged as chosen."""

    def setUp(self):
        super().setUp()
        self.make_catalog()
        self.client.force_login(self.make_staff())
        self.workspace = CaptionWorkspace.objects.create(institution=self.institution)

    def post(self, url, data):
        return self.client.post(url, json.dumps(data), content_type="application/json")

    def upload(self, options=None):
        prepared = self.post("/admin/uploads/prepare/", {
            "target": "portal.captionitem", "parentId": self.workspace.pk,
            "files": [{"clientId": "c1", "name": "lamp_lighting.jpg", "size": 1000, "type": "image/jpeg"}],
        }).json()
        entry = prepared["files"][0]
        self.client.post("/admin/uploads/direct/", {
            "token": entry["token"],
            "file": SimpleUploadedFile("lamp_lighting.jpg", jpeg_bytes(), content_type="image/jpeg"),
        })
        payload = {"files": [{"token": entry["token"], "index": 0, "name": "lamp_lighting.jpg"}]}
        if options:
            payload["options"] = options
        with self.captureOnCommitCallbacks(execute=True):
            result = self.post(f"/admin/uploads/{prepared['batchId']}/commit/", payload).json()
        self.assertEqual(len(result["created"]), 1)
        return CaptionItem.objects.get(workspace=self.workspace)

    def test_fresh_upload_needs_a_caption(self):
        item = self.upload()
        self.assertEqual((item.institution_id, item.event_id), (self.institution.pk, None))
        self.assertEqual((item.status, item.requested, item.moment_title), ("needs-caption", "needs-caption", "Lamp Lighting"))
        self.assertEqual(item.caption, "")

    def test_upload_tag_is_applied_and_bogus_tags_ignored(self):
        item = self.upload({"requested": "needs-approval"})
        self.assertEqual((item.status, item.requested), ("needs-approval", "needs-approval"))
        item.delete()
        item = self.upload({"requested": "approved"})  # never a request the institution can be sent
        self.assertEqual(item.status, "needs-caption")

    def test_workspace_items_reach_the_portal_without_an_event(self):
        item = self.upload()
        user = get_user_model().objects.create_user("dps-newdelhi", password="demo")
        Member.objects.create(user=user, institution=self.institution)
        token = self.post("/api/portal/login/", {"username": "dps-newdelhi", "password": "demo"}).json()["access"]
        items = self.client.get("/api/portal/captions/", HTTP_AUTHORIZATION=f"Bearer {token}").json()["items"]
        self.assertEqual([(i["id"], i["event"], i["status"]) for i in items], [(str(item.pk), "", "needs-caption")])

    def test_workspace_is_created_for_event_captions(self):
        item = CaptionItem(event=self.other_event, moment_title="Moment")
        item.save()
        self.assertEqual(item.workspace.institution_id, self.other.pk)
        self.assertEqual(CaptionWorkspace.objects.count(), 2)

    def test_retagging_in_admin_sends_it_back(self):
        item = self.upload()
        item.caption = "Chief guest lights the lamp."
        item.save()
        url = f"/admin/portal/captionworkspace/{self.workspace.pk}/change/"
        form = {
            "notes": "", "_save": "1",
            "items-TOTAL_FORMS": "1", "items-INITIAL_FORMS": "1", "items-MIN_NUM_FORMS": "0", "items-MAX_NUM_FORMS": "1000",
            "items-0-id": str(item.pk), "items-0-workspace": str(self.workspace.pk),
            "items-0-moment_title": item.moment_title, "items-0-caption": item.caption,
            "items-0-requested": "needs-approval",
        }
        response = self.client.post(url, form)
        self.assertEqual(response.status_code, 302, response.content[:500])
        item.refresh_from_db()
        self.assertEqual((item.status, item.requested), ("needs-approval", "needs-approval"))
