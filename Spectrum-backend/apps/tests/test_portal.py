import json

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.core.models import UploadBatch
from apps.portal.models import CaptionItem, CaptionWorkspace, PortalAccessEmail, SchoolClass, Student

from .base import SpectrumTestCase, jpeg_bytes


def give_portal_login(institution, username, password, email=None):
    """An access email with its own username and password."""
    row, _ = PortalAccessEmail.objects.get_or_create(institution=institution,
                                                     email=email or f"{username}@school.test")
    row.username = username
    row.set_password(password)
    row.save()
    return row


def make_spectrum_user(username="ops", password="team-pass-123", **extra):
    from django.contrib.auth.models import Permission

    user = get_user_model().objects.create_user(username, password=password, **extra)
    user.user_permissions.add(Permission.objects.get(codename="spectrum_portal_access"))
    return user


class PortalTests(SpectrumTestCase):
    def setUp(self):
        super().setUp()
        self.make_catalog()
        self.sign_in = give_portal_login(self.institution, "dps-newdelhi", "demo")
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
        PortalAccessEmail.objects.filter(pk=self.sign_in.pk).update(token_version=99)
        self.assertEqual(self.api("get", "/api/portal/me/").status_code, 401)

    def test_institution_sign_in_lives_on_its_access_email(self):
        self.sign_in.refresh_from_db()
        self.assertTrue(self.sign_in.password.startswith("pbkdf2_"), "stored hashed, never plain")
        me = self.api("get", "/api/portal/me/").json()
        self.assertEqual((me["loginId"], me["role"], me["displayName"], me["institution"]["id"]),
                         ("dps-newdelhi", "institution", "Delhi Public School", "dps"))
        self.assertEqual(self.login("DPS-NewDelhi", "demo")["member"]["loginId"], "dps-newdelhi",
                         "usernames ignore letter case")
        # A new password ends every session from this sign-in.
        self.sign_in.set_password("brand-new-pass")
        self.sign_in.save()
        self.assertEqual(self.api("get", "/api/portal/me/").status_code, 401)
        self.assertIn("error", self.login("dps-newdelhi", "demo"))
        self.assertIn("access", self.login("dps-newdelhi", "brand-new-pass"))
        # Clearing the username closes the portal for that sign-in.
        token = self.login("dps-newdelhi", "brand-new-pass")["access"]
        PortalAccessEmail.objects.filter(pk=self.sign_in.pk).update(username="")
        self.assertEqual(self.client.get("/api/portal/me/", HTTP_AUTHORIZATION=f"Bearer {token}").status_code, 401)

    def test_each_email_signs_in_with_its_own_username_and_password(self):
        give_portal_login(self.institution, "dps-principal", "principal-pass", email="principal@dps.edu")
        login = lambda **data: self.client.post("/api/portal/login/", json.dumps(data),
                                                 content_type="application/json")
        ok = login(username="dps-principal", password="principal-pass", email="principal@dps.edu")
        self.assertEqual(ok.json()["member"]["loginId"], "dps-principal")
        # Another email's credentials don't sign in through this email, even within the school.
        self.assertEqual(login(username="dps-newdelhi", password="demo", email="principal@dps.edu").status_code, 401)
        # A session belongs to its own sign-in: signing one out leaves the other.
        other = ok.json()["access"]
        PortalAccessEmail.objects.filter(email="principal@dps.edu").update(token_version=50)
        self.assertEqual(self.client.get("/api/portal/me/", HTTP_AUTHORIZATION=f"Bearer {other}").status_code, 401)
        self.assertEqual(self.api("get", "/api/portal/me/").status_code, 200)
        # An email with no username yet says so.
        PortalAccessEmail.objects.create(institution=self.institution, email="office@dps.edu")
        response = login(username="x", password="y", email="office@dps.edu")
        self.assertIn("No username and password have been set up", response.json()["error"])

    def test_tokens_from_the_institution_sign_in_are_refused(self):
        from django.core import signing

        # Then the marker was "institution" with an institution id; it must
        # never be read as an access-email id.
        old = signing.dumps({"r": "institution", "id": self.sign_in.pk, "v": "1", "t": 2_000_000_000},
                            salt="portal.access")
        self.assertEqual(self.client.get("/api/portal/me/", HTTP_AUTHORIZATION=f"Bearer {old}").status_code, 401)

    def test_tokens_from_before_the_move_are_refused(self):
        from django.core import signing

        old = signing.dumps({"u": 1, "v": 1, "t": 2_000_000_000}, salt="portal.access")
        self.assertEqual(self.client.get("/api/portal/me/", HTTP_AUTHORIZATION=f"Bearer {old}").status_code, 401)

    def test_spectrum_team_signs_in_with_the_user_permission(self):
        from django.contrib.auth.models import Permission

        user = make_spectrum_user(first_name="Riya", last_name="Ops")
        result = self.login("ops", "team-pass-123")
        self.assertEqual((result["member"]["role"], result["member"]["displayName"]), ("spectrum", "Riya Ops"))
        token = result["access"]
        auth = {"HTTP_AUTHORIZATION": f"Bearer {token}"}
        other = self.client.get("/api/portal/me/?institution=doon", **auth).json()
        self.assertEqual(other["institution"]["id"], "doon", "the Spectrum team may open any institution")
        # Taking the permission away ends the session; a plain staff user never gets in.
        user.user_permissions.remove(Permission.objects.get(codename="spectrum_portal_access"))
        self.assertEqual(self.client.get("/api/portal/me/", **auth).status_code, 401)
        get_user_model().objects.create_user("clerk", password="clerk-pass-123", is_staff=True)
        self.assertIn("error", self.login("clerk", "clerk-pass-123"))
        get_user_model().objects.create_superuser("boss", password="boss-pass-123")
        self.assertEqual(self.login("boss", "boss-pass-123")["member"]["role"], "spectrum")

    def test_spectrum_session_ends_when_the_password_changes(self):
        user = make_spectrum_user()
        token = self.login("ops", "team-pass-123")["access"]
        auth = {"HTTP_AUTHORIZATION": f"Bearer {token}"}
        self.assertEqual(self.client.get("/api/portal/me/", **auth).status_code, 200)
        user.set_password("another-pass-456")
        user.save()
        self.assertEqual(self.client.get("/api/portal/me/", **auth).status_code, 401)

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

    def test_for_correction_is_no_longer_a_tag(self):
        from apps.portal.models import REQUEST_CHOICES

        self.assertEqual([value for value, _ in REQUEST_CHOICES], ["needs-caption", "needs-approval"])
        item = self.caption(self.event, "needs-approval")
        # An approval may carry adjusted wording; the photo is then Approved and locked.
        data = self.api("post", f"/api/portal/captions/{item.pk}/resolve/",
                        {"status": "approved", "text": "Adjusted wording", "actionBy": "A. Kapoor",
                         "actionByPhone": "9876543210"}).json()
        self.assertEqual((data["status"], data["caption"]), ("approved", "Adjusted wording"))

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


class AbsenteesAndCommentsTests(SpectrumTestCase):
    """Absent students' photos and a comment per class, added by the institution."""

    login = PortalTests.login
    api = PortalTests.api

    def setUp(self):
        super().setUp()
        self.make_catalog()
        give_portal_login(self.institution, "dps-newdelhi", "demo")
        self.token = self.login("dps-newdelhi", "demo")["access"]
        self.cls = SchoolClass.objects.create(institution=self.institution, name="6C", group="Middle")
        regular = Student(school_class=self.cls, source_name="IMG_2.jpg")
        regular.original.save("r.jpg", ContentFile(jpeg_bytes()), save=False)
        with self.captureOnCommitCallbacks(execute=True):
            regular.save()
        self.regular = regular

    def upload(self, *names, slug="6c"):
        files = [SimpleUploadedFile(name, jpeg_bytes(), content_type="image/jpeg") for name in names]
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(f"/api/portal/classes/{slug}/absentees/", {"images": files},
                                    HTTP_AUTHORIZATION=f"Bearer {self.token}")

    def test_absentees_are_added_named_and_listed_last(self):
        response = self.upload("aarav.jpg", "0001.jpg")
        self.assertEqual(response.status_code, 200, response.content)
        added = response.json()["students"]
        self.assertEqual([s["absentee"] for s in added], [True, True])
        detail = self.api("get", "/api/portal/classes/6c/").json()
        self.assertEqual([s["absentee"] for s in detail["students"]], [False, True, True], "absentees come last")
        # They are named like everyone else.
        self.api("put", "/api/portal/classes/6c/names/", {"names": {added[0]["id"]: "Kabir Nair"}})
        self.assertEqual(Student.objects.get(pk=added[0]["id"]).name, "Kabir Nair")
        # A mistake can be removed; the class's own photos can't be.
        self.assertEqual(self.api("delete", f"/api/portal/classes/6c/absentees/{added[1]['id']}/").status_code, 200)
        self.assertEqual(self.api("delete", f"/api/portal/classes/6c/absentees/{self.regular.pk}/").status_code, 404)
        self.assertEqual(Student.objects.filter(school_class=self.cls).count(), 2)

    def test_absentee_uploads_are_checked_and_scoped(self):
        bad = self.client.post("/api/portal/classes/6c/absentees/",
                               {"images": [SimpleUploadedFile("notes.txt", b"hello", content_type="text/plain")]},
                               HTTP_AUTHORIZATION=f"Bearer {self.token}")
        self.assertEqual(bad.status_code, 400)
        SchoolClass.objects.create(institution=self.other, name="7A")
        self.assertEqual(self.upload("x.jpg", slug="7a").status_code, 404, "another school's class")
        self.assertFalse(Student.objects.filter(is_absentee=True).exists())

    def test_comment_is_saved_and_downloaded_with_the_photos(self):
        import zipfile
        from io import BytesIO

        result = self.api("put", "/api/portal/classes/6c/comment/",
                          {"comment": "  Two students were on a school trip.  "}).json()
        self.assertEqual(result["comment"], "Two students were on a school trip.")
        self.assertEqual(self.api("get", "/api/portal/classes/6c/").json()["class"]["comment"],
                         "Two students were on a school trip.")

        self.client.force_login(self.make_staff())
        response = self.client.post("/admin/portal/schoolclass/", {"action": "download_photos",
                                                                    "_selected_action": [self.cls.pk]})
        with zipfile.ZipFile(BytesIO(b"".join(response.streaming_content))) as archive:
            names = archive.namelist()
            self.assertIn("DPS-6C-Photos/comment.txt", names)
            self.assertEqual(archive.read("DPS-6C-Photos/comment.txt").decode(), "Two students were on a school trip.\n")


class PortalAccessTests(SpectrumTestCase):
    """The email step that unlocks the portal, and the institution check on login."""

    def setUp(self):
        super().setUp()
        self.make_catalog()
        give_portal_login(self.institution, "dps-newdelhi", "demo", email="Principal@DPS.edu ")
        give_portal_login(self.other, "doon", "doon-pass-123", email="head@doon.edu")

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
        self.assertEqual(mismatch.status_code, 401)
        ok = self.post("/api/portal/login/", {"username": "dps-newdelhi", "password": "demo", "email": "principal@dps.edu"})
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.json()["member"]["institution"]["id"], "dps")
        # The Spectrum team isn't tied to the email's institution.
        make_spectrum_user()
        team = self.post("/api/portal/login/", {"username": "ops", "password": "team-pass-123", "email": "head@doon.edu"})
        self.assertEqual(team.status_code, 200)


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
        give_portal_login(self.institution, "dps-newdelhi", "demo")
        token = self.post("/api/portal/login/", {"username": "dps-newdelhi", "password": "demo"}).json()["access"]
        items = self.client.get("/api/portal/captions/", HTTP_AUTHORIZATION=f"Bearer {token}").json()["items"]
        self.assertEqual([(i["id"], i["event"], i["status"]) for i in items], [(str(item.pk), "", "needs-caption")])

    def test_tag_picked_after_uploading_applies_to_the_batch(self):
        item = self.upload()  # uploaded with the default tag
        batch = UploadBatch.objects.get()
        self.assertEqual(item.status, "needs-caption")
        url = f"/admin/uploads/{batch.pk}/options/"
        self.assertEqual(self.post(url, {"options": {"requested": "needs-approval"}}).json(), {"updated": 1})
        item.refresh_from_db()
        self.assertEqual((item.status, item.requested), ("needs-approval", "needs-approval"))
        # Never a tag the institution can't be sent.
        self.assertEqual(self.post(url, {"options": {"requested": "approved"}}).json(), {"updated": 0})
        # A photo the institution has already acted on keeps its state.
        CaptionItem.objects.filter(pk=item.pk).update(status="approved")
        self.assertEqual(self.post(url, {"options": {"requested": "needs-caption"}}).json(), {"updated": 0})
        item.refresh_from_db()
        self.assertEqual(item.status, "approved")

    def test_reupload_in_a_batch_keeps_its_own_tag_when_retagged(self):
        item = self.upload()
        CaptionItem.objects.filter(pk=item.pk).update(status="needs-approval", requested="needs-approval")
        UploadBatch.objects.all().delete()
        self.upload()  # the same file name again: replaces the photo in place
        batch = UploadBatch.objects.get()
        self.assertFalse(batch.files.get().created)
        self.post(f"/admin/uploads/{batch.pk}/options/", {"options": {"requested": "needs-caption"}})
        item.refresh_from_db()
        self.assertEqual(item.status, "needs-approval", "a replaced photo keeps its tag, as at upload")

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


class PortalAdminTests(SpectrumTestCase):
    """Where the Spectrum team manages portal sign-ins in the admin."""

    def setUp(self):
        super().setUp()
        self.make_catalog()
        self.client.force_login(self.make_staff())

    def institution_form(self, rows=(), **extra):
        """The institution page's POST, with its sign-in rows (dicts of email/username/new_password/id)."""
        data = {
            "name": self.institution.name, "short": "", "slug": self.institution.slug, "city": "New Delhi",
            "kind": self.institution.kind_id, "is_published": "on", "sort_order": "0",
            "portal_emails-TOTAL_FORMS": str(len(rows)),
            "portal_emails-INITIAL_FORMS": str(sum(1 for r in rows if r.get("id"))),
            "portal_emails-MIN_NUM_FORMS": "0", "portal_emails-MAX_NUM_FORMS": "1000", "_save": "1",
        }
        for i, row in enumerate(rows):
            for key in ("id", "email", "username", "new_password", "note"):
                data[f"portal_emails-{i}-{key}"] = row.get(key, "")
            data[f"portal_emails-{i}-institution"] = str(self.institution.pk)
        data.update(extra)
        return data

    def test_institution_page_has_one_section_of_email_username_password(self):
        url = f"/admin/catalog/institution/{self.institution.pk}/change/"
        html = self.client.get(url).content.decode()
        self.assertNotIn("Institution portal sign-in", html, "no separate username/password section")
        for name in ("portal_emails-0-email", "portal_emails-0-username", "portal_emails-0-new_password"):
            self.assertIn(f'name="{name}"', html)
        # "Add another" clones the empty row: the same three boxes.
        self.assertIn('name="portal_emails-__prefix__-username"', html)
        self.assertIn('name="portal_emails-__prefix__-new_password"', html)

        # Username and password are optional...
        response = self.client.post(url, self.institution_form([{"email": "office@dps.edu"}]))
        self.assertEqual(response.status_code, 302, response.content[:800])
        office = PortalAccessEmail.objects.get(email="office@dps.edu")
        self.assertEqual((office.username, office.password), ("", ""))
        # ...but go together.
        response = self.client.post(url, self.institution_form([{"id": str(office.pk), "email": "office@dps.edu",
                                                                 "username": "dps-office"}]))
        self.assertIn("Set a password for this username", response.content.decode())

        response = self.client.post(url, self.institution_form([
            {"id": str(office.pk), "email": "office@dps.edu", "username": "dps-office", "new_password": "Lotus-Garden-42"},
            {"email": "principal@dps.edu", "username": "dps-principal", "new_password": "Banyan-Tree-77"},
        ]))
        self.assertEqual(response.status_code, 302, response.content[:800])
        office.refresh_from_db()
        principal = PortalAccessEmail.objects.get(email="principal@dps.edu")
        self.assertEqual((office.username, principal.username), ("dps-office", "dps-principal"))
        self.assertNotIn("Lotus-Garden-42", office.password)
        self.assertTrue(office.check_password("Lotus-Garden-42"))
        self.assertTrue(principal.check_password("Banyan-Tree-77"))
        version = office.token_version

        # Saving again with the password left blank keeps it.
        self.client.post(url, self.institution_form([{"id": str(office.pk), "email": "office@dps.edu",
                                                      "username": "dps-office"},
                                                     {"id": str(principal.pk), "email": "principal@dps.edu",
                                                      "username": "dps-principal"}]))
        office.refresh_from_db()
        self.assertTrue(office.check_password("Lotus-Garden-42"))
        self.assertEqual(office.token_version, version)

        # Another institution can't take the same username, in any letter case.
        response = self.client.post(f"/admin/catalog/institution/{self.other.pk}/change/", {
            **self.institution_form([{"email": "head@doon.edu", "username": "DPS-OFFICE",
                                      "new_password": "Another-Pass-77"}]),
            "name": self.other.name, "slug": self.other.slug,
            "portal_emails-0-institution": str(self.other.pk)})
        self.assertIn("Another institution already signs in with that username", response.content.decode())

    def test_sign_out_action_bumps_every_sign_in_of_the_institution(self):
        row = give_portal_login(self.institution, "dps-newdelhi", "demo")
        before = row.token_version
        self.client.post("/admin/catalog/institution/", {"action": "sign_out_of_portal",
                                                         "_selected_action": [self.institution.pk]})
        row.refresh_from_db()
        self.assertEqual(row.token_version, before + 1)

    def test_users_table_grants_portal_access(self):
        user = get_user_model().objects.create_user("riya", password="riya-pass-123")
        url = f"/admin/auth/user/{user.pk}/change/"
        html = self.client.get(url).content.decode()
        self.assertIn("Institution portal access", html)
        form = {"username": "riya", "first_name": "", "last_name": "", "email": "", "is_active": "on",
                "date_joined_0": "2026-10-09", "date_joined_1": "10:00:00", "initial-date_joined_0": "2026-10-09",
                "initial-date_joined_1": "10:00:00", "portal_access": "on", "_save": "1"}
        response = self.client.post(url, form)
        self.assertEqual(response.status_code, 302, response.content[:800])
        user = get_user_model().objects.get(pk=user.pk)
        self.assertTrue(user.has_perm("portal.spectrum_portal_access"))
        self.assertIn("Portal access", self.client.get("/admin/auth/user/").content.decode())
        form.pop("portal_access")
        self.client.post(url, form)
        user = get_user_model().objects.get(pk=user.pk)
        self.assertFalse(user.has_perm("portal.spectrum_portal_access"))

    def test_admin_index_shows_the_renamed_tables(self):
        index = self.client.get("/admin/").content.decode()
        for label in ("Institution workspaces", "All classes", "Institution credentials"):
            self.assertIn(label, index)
        for gone in ("Portal logins", "Class photograph items", "Title workspaces"):
            self.assertNotIn(gone, index)

    def test_credentials_table_shows_each_emails_username_and_password(self):
        row = give_portal_login(self.institution, "dps-newdelhi", "demo", email="principal@dps.edu")
        PortalAccessEmail.objects.create(institution=self.other, email="head@doon.edu")
        listing = self.client.get("/admin/portal/portalaccessemail/").content.decode()
        self.assertIn("dps-newdelhi", listing)
        self.assertIn("Not set", listing)  # Doon's email has no password yet
        self.assertNotIn(row.password, listing, "the hash is never shown")
        page = self.client.get(f"/admin/portal/portalaccessemail/{row.pk}/change/").content.decode()
        self.assertIn('value="dps-newdelhi"', page)
        self.assertIn('name="new_password"', page)
        self.assertNotIn(row.password, page)

    def test_event_videos_and_types_in_the_admin(self):
        index = self.client.get("/admin/").content.decode()
        self.assertNotIn("Event videos", index, "videos are edited on their event")
        self.assertNotIn(">Other<", index)
        system = index[index.index(">System<"):]
        self.assertIn(">Types<", system)
        self.assertNotIn("Institution types", index)
        self.assertIn("Poster image", self.client.get(f"/admin/catalog/event/{self.event.pk}/change/").content.decode())
