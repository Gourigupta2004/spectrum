import json

from django.core.files.base import ContentFile
from django.core.files.storage import storages
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.catalog.models import EventPhoto
from apps.core.models import ImageStatus, UploadBatchFile
from apps.core.uploads import humanize

from .base import SpectrumTestCase, jpeg_bytes


class ImageProcessingTests(SpectrumTestCase):
    def setUp(self):
        super().setUp()
        self.make_catalog()

    def test_variants_made_and_exif_rotation_applied(self):
        from PIL import Image

        obj = EventPhoto(event=self.event, title="Rotated")
        obj.original.save("r.jpg", ContentFile(jpeg_bytes(80, 40, orientation=6)), save=False)
        with self.captureOnCommitCallbacks(execute=True):
            obj.save()
        obj.refresh_from_db()
        self.assertEqual(obj.image_status, ImageStatus.READY)
        self.assertEqual((obj.width, obj.height), (40, 80))
        with storages["default"].open(obj.preview.name) as handle:
            preview = Image.open(handle)
            self.assertEqual(preview.format, "WEBP")
            self.assertEqual(preview.size, (40, 80))
        self.assertTrue(obj.thumb.name)
        self.assertFalse(obj.web.name, "gallery photos must not publish an unwatermarked web copy")

    def test_unreadable_file_marks_failed_without_retry(self):
        obj = EventPhoto(event=self.event, title="Broken")
        obj.original.save("b.jpg", ContentFile(b"not an image"), save=False)
        with self.captureOnCommitCallbacks(execute=True):
            obj.save()
        obj.refresh_from_db()
        self.assertEqual(obj.image_status, ImageStatus.FAILED)

    def test_delete_removes_files(self):
        obj = self.photo(self.event)
        names = [(storages["private"], obj.original.name), (storages["default"], obj.preview.name)]
        with self.captureOnCommitCallbacks(execute=True):
            obj.delete()
        for storage, name in names:
            self.assertFalse(storage.exists(name))

    def test_humanize(self):
        self.assertEqual(humanize("award_distribution-night.JPG"), "Award Distribution Night")
        self.assertEqual(humanize("DSC01234.jpg"), "DSC01234")
        self.assertEqual(humanize("Chief Guest Speech.png"), "Chief Guest Speech")


class BulkUploadTests(SpectrumTestCase):
    def setUp(self):
        super().setUp()
        self.make_catalog()
        self.client.force_login(self.make_staff())
        self.photo(self.event, sort_order=4)  # existing photo: new batch must start after it

    def post(self, url, data):
        return self.client.post(url, json.dumps(data), content_type="application/json")

    def test_prepare_upload_commit_is_ordered_and_idempotent(self):
        files = [{"clientId": f"c{i}", "name": f"moment_{i}.jpg", "size": 1000, "type": "image/jpeg"} for i in range(3)]
        files.append({"clientId": "bad", "name": "notes.txt", "size": 10, "type": "text/plain"})
        prepared = self.post("/admin/uploads/prepare/", {"target": "catalog.eventphoto", "parentId": self.event.pk,
                                                         "files": files}).json()
        self.assertEqual(prepared["mode"], "direct")
        entries = {e["clientId"]: e for e in prepared["files"]}
        self.assertIn("error", entries["bad"])

        for i in (2, 0, 1):  # upload out of order
            response = self.client.post("/admin/uploads/direct/", {
                "token": entries[f"c{i}"]["token"],
                "file": SimpleUploadedFile(f"moment_{i}.jpg", jpeg_bytes(), content_type="image/jpeg"),
            })
            self.assertEqual(response.status_code, 200)

        commit_url = f"/admin/uploads/{prepared['batchId']}/commit/"
        payload = {"files": [{"token": entries[f"c{i}"]["token"], "index": i, "name": f"moment_{i}.jpg"}
                             for i in (1, 2, 0)]}
        with self.captureOnCommitCallbacks(execute=True):
            first = self.post(commit_url, payload).json()
        second = self.post(commit_url, payload).json()
        self.assertEqual(len(first["created"]), 3)
        self.assertEqual(len(second["created"]), 3)
        self.assertEqual(UploadBatchFile.objects.count(), 3)

        new = list(EventPhoto.objects.filter(event=self.event).exclude(sort_order=4).order_by("sort_order"))
        self.assertEqual([p.title for p in new], ["Moment 0", "Moment 1", "Moment 2"])
        self.assertEqual([p.sort_order for p in new], [5, 6, 7])
        status = self.client.get(f"/admin/uploads/{prepared['batchId']}/status/").json()
        self.assertEqual(status["ready"], 3)

    def test_tampered_token_is_ignored(self):
        prepared = self.post("/admin/uploads/prepare/", {"target": "catalog.eventphoto", "parentId": self.event.pk,
                                                         "files": [{"clientId": "a", "name": "a.jpg", "size": 5}]}).json()
        result = self.post(f"/admin/uploads/{prepared['batchId']}/commit/",
                           {"files": [{"token": "forged", "index": 0, "name": "a.jpg"}]}).json()
        self.assertEqual(result["created"], [])

    def test_non_staff_cannot_upload(self):
        self.client.logout()
        response = self.post("/admin/uploads/prepare/", {"target": "catalog.eventphoto", "parentId": self.event.pk})
        self.assertIn(response.status_code, (302, 403))

    def upload_batch(self, target, parent_id, filenames, options=None):
        files = [{"clientId": f"c{i}", "name": name, "size": 1000, "type": "image/jpeg"}
                 for i, name in enumerate(filenames)]
        prepared = self.post("/admin/uploads/prepare/", {
            "target": target, "parentId": parent_id, "files": files,
        }).json()
        entries = {e["clientId"]: e for e in prepared["files"]}
        for i, name in enumerate(filenames):
            self.client.post("/admin/uploads/direct/", {
                "token": entries[f"c{i}"]["token"],
                "file": SimpleUploadedFile(name, jpeg_bytes(), content_type="image/jpeg"),
            })
        with self.captureOnCommitCallbacks(execute=True):
            return self.post(f"/admin/uploads/{prepared['batchId']}/commit/", {
                "files": [{"token": entries[f"c{i}"]["token"], "index": i, "name": name}
                          for i, name in enumerate(filenames)],
                "options": options or {},
            }).json()

    def upload_to_workspace(self, workspace, filename, requested="needs-caption"):
        result = self.upload_batch("portal.captionitem", workspace.pk, [filename],
                                   {"requested": requested})
        self.assertEqual(len(result["created"]), 1)

    def test_institution_batch_files_students_into_classes_from_file_names(self):
        from apps.portal.models import SchoolClass, Student

        result = self.upload_batch("portal.studentbatch", self.institution.pk, [
            "6C_amity_1.jpg", "6C_amity_2.jpg", "12AB_x_42.jpg", "2bb_front.jpg", "notes.jpg",
        ])
        self.assertEqual(len(result["created"]), 4)
        self.assertEqual(len(result["skipped"]), 1)
        self.assertIn("no class at the front of the file name", result["errors"]["c4"])

        classes = {c.name: c for c in SchoolClass.objects.filter(institution=self.institution)}
        self.assertEqual(set(classes), {"6C", "12AB", "2BB"})
        self.assertEqual(classes["2BB"].group, "Primary")
        self.assertEqual(classes["6C"].group, "Middle")
        self.assertEqual(classes["12AB"].group, "Senior")
        self.assertEqual(Student.objects.filter(school_class=classes["6C"]).count(), 2)
        self.assertEqual(Student.objects.filter(school_class=classes["12AB"]).count(), 1)
        # A second batch reuses the classes instead of duplicating them.
        self.upload_batch("portal.studentbatch", self.institution.pk, ["6C_amity_3.jpg"])
        self.assertEqual(SchoolClass.objects.filter(institution=self.institution).count(), 3)
        self.assertEqual(Student.objects.filter(school_class=classes["6C"]).count(), 3)

    def test_class_photos_download_zips_originals_named_after_students(self):
        import zipfile
        from io import BytesIO

        from apps.portal.models import SchoolClass, Student

        self.upload_batch("portal.studentbatch", self.institution.pk, ["6C_amity_1.jpg", "6C_amity_2.jpg"])
        cls = SchoolClass.objects.get(institution=self.institution, name="6C")
        students = list(Student.objects.filter(school_class=cls).order_by("pk"))
        Student.objects.filter(pk=students[0].pk).update(name="Aarav Sharma")  # the other stays unnamed

        response = self.client.post("/admin/portal/schoolclass/", {
            "action": "download_photos", "_selected_action": [cls.pk],
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/zip")
        with zipfile.ZipFile(BytesIO(b"".join(response.streaming_content))) as archive:
            names = archive.namelist()
        folder = names[0].split("/")[0]
        self.assertTrue(folder.endswith("-6C-Photos"), folder)
        self.assertEqual(len(names), 1, "unnamed students are left out")
        self.assertIn("Aarav Sharma.jpg", names[0])
        students[0].refresh_from_db()
        with zipfile.ZipFile(BytesIO(b"".join(self.client.post("/admin/portal/schoolclass/", {
            "action": "download_photos", "_selected_action": [cls.pk],
        }).streaming_content))) as archive:
            data = archive.read(names[0])
        with students[0].original.open("rb") as handle:
            self.assertEqual(data, handle.read(), "the zip must carry the uploaded original, byte for byte")

    def test_reupload_same_filename_replaces_photo_and_keeps_title(self):
        from apps.portal.models import CaptionItem, CaptionWorkspace

        workspace = CaptionWorkspace.objects.create(institution=self.institution)
        self.upload_to_workspace(workspace, "6A KRM 2683 M.jpg")
        item = CaptionItem.objects.get(workspace=workspace)
        self.assertEqual(item.source_name, "6A KRM 2683 M.jpg")

        # The teacher titles it; the edited photo then comes back under the same name.
        CaptionItem.objects.filter(pk=item.pk).update(caption="Class 6A with Mrs. Mehta", status="corrected")
        before_original, before_web = item.original.name, item.web.name
        self.upload_to_workspace(workspace, "6A KRM 2683 M.jpg")

        items = list(CaptionItem.objects.filter(workspace=workspace))
        self.assertEqual(len(items), 1, "same file name must land in the same row")
        self.assertNotEqual(items[0].original.name, before_original, "the photo itself must be replaced")
        self.assertEqual(items[0].image_status, ImageStatus.READY, "the new photo must be processed")
        self.assertNotEqual(items[0].web.name, before_web, "the public web copy must be regenerated")
        self.assertEqual(items[0].caption, "Class 6A with Mrs. Mehta")
        self.assertEqual(items[0].status, "corrected")

        # A new name is a new photo.
        self.upload_to_workspace(workspace, "6B KRM 2697 M.jpg")
        self.assertEqual(CaptionItem.objects.filter(workspace=workspace).count(), 2)

    def test_export_titles_as_excel(self):
        import zipfile
        from io import BytesIO

        from apps.portal.models import CaptionItem, CaptionWorkspace

        workspace = CaptionWorkspace.objects.create(institution=self.institution)
        self.upload_to_workspace(workspace, "6A KRM 2683 M.jpg")
        item = CaptionItem.objects.get(workspace=workspace)
        CaptionItem.objects.filter(pk=item.pk).update(caption="Class 6A with Mrs. Mehta", status="approved",
                                                      action_by="R. Menon", action_by_phone="9876543210")

        html = self.client.get(f"/admin/portal/captionworkspace/{workspace.pk}/change/").content.decode()
        self.assertIn("Export titles (Excel)", html)
        response = self.client.get(f"/admin/portal/captionworkspace/{workspace.pk}/export-titles/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("spreadsheetml.sheet", response["Content-Type"])
        self.assertIn(".xlsx", response["Content-Disposition"])
        with zipfile.ZipFile(BytesIO(response.content)) as archive:
            sheet = archive.read("xl/worksheets/sheet1.xml").decode()
        item.refresh_from_db()
        self.assertIn("6A KRM 2683 M.jpg", sheet)
        self.assertIn("Class 6A with Mrs. Mehta", sheet)
        self.assertIn(item.web.name, sheet, "the photo's S3 link must sit beside its title")
        self.assertIn("R. Menon", sheet)

    def test_delete_all_photos_clears_the_workspace(self):
        from apps.portal.models import CaptionItem, CaptionWorkspace

        workspace = CaptionWorkspace.objects.create(institution=self.institution)
        self.upload_to_workspace(workspace, "6A KRM 2683 M.jpg")
        self.upload_to_workspace(workspace, "6B KRM 2697 M.jpg")
        html = self.client.get(f"/admin/portal/captionworkspace/{workspace.pk}/change/").content.decode()
        self.assertIn('id="bulk-delete-all"', html)
        self.assertIn("Tick every row for deletion", html)  # the Delete? header's select-all
        self.assertNotIn("<form", html.split('id="bulk-delete-all"')[1][:400],
                         "the delete button must not render a nested form — browsers drop it")
        url = f"/admin/portal/captionworkspace/{workspace.pk}/delete-photos/"
        self.assertEqual(self.client.get(url).status_code, 405)  # POST only
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(CaptionItem.objects.filter(workspace=workspace).count(), 0)

    def test_uploaders_live_on_event_and_workspace_pages(self):
        from apps.portal.models import CaptionWorkspace

        html = self.client.get(f"/admin/catalog/event/{self.event.pk}/change/").content.decode()
        self.assertIn('data-target="catalog.eventphoto"', html)
        self.assertNotIn('data-target="portal.captionitem"', html)
        workspace = CaptionWorkspace.objects.create(institution=self.institution)
        html = self.client.get(f"/admin/portal/captionworkspace/{workspace.pk}/change/").content.decode()
        self.assertIn('data-target="portal.captionitem"', html)
        self.assertIn('class="bulk-option" data-key="requested"', html)
        self.assertIn('<option value="needs-caption" selected>', html)


class PhotoProportionTests(SpectrumTestCase):
    """Every photo travels with its pixel size, and the one-off crop command cuts to a frame."""

    def setUp(self):
        super().setUp()
        self.make_catalog()

    def test_gallery_photos_carry_their_size(self):
        self.photo(self.event)
        photo = self.client.get("/api/events/annual-day/").json()["photos"][0]
        self.assertEqual((photo["width"], photo["height"]), (64, 48))

    def test_crop_to_frame_cuts_centre_and_keeps_the_original(self):
        from io import StringIO

        from django.core.management import call_command

        obj = self.photo(self.event)  # 64x48, wider than the 4:5 gallery frame
        before = obj.original.name
        out = StringIO()
        with self.captureOnCommitCallbacks(execute=True):
            call_command("crop_to_frame", model=["catalog.eventphoto"], stdout=out)
        obj.refresh_from_db()
        self.assertEqual((obj.width, obj.height), (38, 48))  # 48 * 4/5, full height kept
        self.assertEqual(obj.image_status, ImageStatus.READY)
        self.assertNotEqual(obj.original.name, before)
        self.assertTrue(storages["private"].exists(before), "the uncropped file is the backup")
        self.assertIn("cropped 1", out.getvalue())
        # Second run: already 4:5, nothing to do.
        out = StringIO()
        call_command("crop_to_frame", model=["catalog.eventphoto"], stdout=out)
        self.assertIn("cropped 0, already 4:5 1", out.getvalue())
