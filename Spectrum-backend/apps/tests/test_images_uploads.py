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

    def upload_to_workspace(self, workspace, filename, requested="needs-caption"):
        prepared = self.post("/admin/uploads/prepare/", {
            "target": "portal.captionitem", "parentId": workspace.pk,
            "files": [{"clientId": "c0", "name": filename, "size": 1000, "type": "image/jpeg"}],
        }).json()
        entry = prepared["files"][0]
        self.client.post("/admin/uploads/direct/", {
            "token": entry["token"],
            "file": SimpleUploadedFile(filename, jpeg_bytes(), content_type="image/jpeg"),
        })
        with self.captureOnCommitCallbacks(execute=True):
            result = self.post(f"/admin/uploads/{prepared['batchId']}/commit/", {
                "files": [{"token": entry["token"], "index": 0, "name": filename}],
                "options": {"requested": requested},
            }).json()
        self.assertEqual(len(result["created"]), 1)

    def test_reupload_same_filename_replaces_photo_and_keeps_title(self):
        from apps.portal.models import CaptionItem, CaptionWorkspace

        workspace = CaptionWorkspace.objects.create(institution=self.institution)
        self.upload_to_workspace(workspace, "6A KRM 2683 M.jpg")
        item = CaptionItem.objects.get(workspace=workspace)
        self.assertEqual(item.source_name, "6A KRM 2683 M.jpg")

        # The teacher titles it; the edited photo then comes back under the same name.
        CaptionItem.objects.filter(pk=item.pk).update(caption="Class 6A with Mrs. Mehta", status="corrected")
        before = item.original.name
        self.upload_to_workspace(workspace, "6A KRM 2683 M.jpg")

        items = list(CaptionItem.objects.filter(workspace=workspace))
        self.assertEqual(len(items), 1, "same file name must land in the same row")
        self.assertNotEqual(items[0].original.name, before, "the photo itself must be replaced")
        self.assertEqual(items[0].caption, "Class 6A with Mrs. Mehta")
        self.assertEqual(items[0].status, "corrected")

        # A new name is a new photo.
        self.upload_to_workspace(workspace, "6B KRM 2697 M.jpg")
        self.assertEqual(CaptionItem.objects.filter(workspace=workspace).count(), 2)

    def test_delete_all_photos_clears_the_workspace(self):
        from apps.portal.models import CaptionItem, CaptionWorkspace

        workspace = CaptionWorkspace.objects.create(institution=self.institution)
        self.upload_to_workspace(workspace, "6A KRM 2683 M.jpg")
        self.upload_to_workspace(workspace, "6B KRM 2697 M.jpg")
        html = self.client.get(f"/admin/portal/captionworkspace/{workspace.pk}/change/").content.decode()
        self.assertIn('id="bulk-delete-all"', html)
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
