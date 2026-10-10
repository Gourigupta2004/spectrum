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
        # A "6C/a.jpg" name is the file a.jpg inside the folder 6C.
        paths = [name.rsplit("/", 1) if "/" in name else ["", name] for name in filenames]
        filenames = [name for _, name in paths]
        files = [{"clientId": f"c{i}", "name": name, "folder": folder, "size": 1000, "type": "image/jpeg"}
                 for i, (folder, name) in enumerate(paths)]
        prepared = self.post("/admin/uploads/prepare/", {
            "target": target, "parentId": parent_id, "files": files,
        }).json()
        entries = {e["clientId"]: e for e in prepared["files"]}
        refused = {key: entry["error"] for key, entry in entries.items() if "error" in entry}
        for i, name in enumerate(filenames):
            if f"c{i}" not in refused:
                self.client.post("/admin/uploads/direct/", {
                    "token": entries[f"c{i}"]["token"],
                    "file": SimpleUploadedFile(name, jpeg_bytes(), content_type="image/jpeg"),
                })
        with self.captureOnCommitCallbacks(execute=True):
            result = self.post(f"/admin/uploads/{prepared['batchId']}/commit/", {
                "files": [{"token": entries[f"c{i}"]["token"], "index": i, "name": name, "folder": folder}
                          for i, (folder, name) in enumerate(paths) if f"c{i}" not in refused],
                "options": options or {},
            }).json()
        # Files refused before upload are reported with the commit's refusals.
        result["errors"] = {**refused, **result.get("errors", {})}
        return result

    def upload_to_workspace(self, workspace, filename, requested="needs-caption"):
        result = self.upload_batch("portal.captionitem", workspace.pk, [filename],
                                   {"requested": requested})
        self.assertEqual(len(result["created"]), 1)

    def workspace_students(self, filenames, institution=None):
        from apps.portal.models import CaptionWorkspace

        workspace = CaptionWorkspace.for_institution((institution or self.institution).pk)
        return self.upload_batch("portal.workspacestudent", workspace.pk, filenames)

    def test_workspace_batch_files_students_into_classes_from_file_names(self):
        from apps.portal.models import SchoolClass, Student

        result = self.workspace_students([
            "6C_amity_1.jpg", "6C_amity_2.jpg", "12AB_x_42.jpg", "2bb_front.jpg",
        ])
        self.assertEqual(len(result["created"]), 4)
        self.assertEqual(result["skipped"], [])

        classes = {c.name: c for c in SchoolClass.objects.filter(institution=self.institution)}
        self.assertEqual(set(classes), {"6C", "12AB", "2BB"})
        self.assertEqual(classes["2BB"].group, "Primary")
        self.assertEqual(classes["6C"].group, "Middle")
        self.assertEqual(classes["12AB"].group, "Senior")
        self.assertEqual(Student.objects.filter(school_class=classes["6C"]).count(), 2)
        self.assertEqual(Student.objects.filter(school_class=classes["12AB"]).count(), 1)
        # A second batch reuses the classes instead of duplicating them.
        self.workspace_students(["6C_amity_3.jpg"])
        self.assertEqual(SchoolClass.objects.filter(institution=self.institution).count(), 3)
        self.assertEqual(Student.objects.filter(school_class=classes["6C"]).count(), 3)

    def test_class_photos_download_zips_originals_named_after_students(self):
        import zipfile
        from io import BytesIO

        from apps.portal.models import SchoolClass, Student

        self.workspace_students(["6C_amity_1.jpg", "6C_amity_2.jpg"])
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
        self.assertEqual(len(names), 2, "unnamed students are included too")
        self.assertIn("Aarav Sharma.jpg", names[0])
        self.assertTrue(names[1].endswith("/Unnamed 6C_amity_2.jpg"), names[1])
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

    def test_delete_selected_event_photos_from_the_grid(self):
        from apps.portal.models import CaptionWorkspace

        keep = self.photo(self.event, title="Keep")
        drop = self.photo(self.event, title="Drop")
        elsewhere = self.photo(self.other_event, title="Elsewhere")
        html = self.client.get(f"/admin/catalog/event/{self.event.pk}/change/").content.decode()
        self.assertIn(f'class="bulk-select" value="{drop.pk}"', html)
        self.assertIn("Delete selected images", html)
        workspace = CaptionWorkspace.objects.create(institution=self.institution)
        html = self.client.get(f"/admin/portal/captionworkspace/{workspace.pk}/change/").content.decode()
        self.assertNotIn("bulk-selectbar", html)  # only event photos get tick boxes

        file_name = drop.original.name
        with self.captureOnCommitCallbacks(execute=True):
            # A photo of another event among the ids is ignored: only this event's rows go.
            response = self.post("/admin/uploads/delete/", {
                "target": "catalog.eventphoto", "parent": self.event.pk, "ids": [drop.pk, elsewhere.pk]})
        self.assertEqual(response.status_code, 200)
        self.assertIn("Deleted 1 photo.", response.content.decode())
        self.assertFalse(EventPhoto.objects.filter(pk=drop.pk).exists())
        self.assertEqual(EventPhoto.objects.filter(pk__in=[keep.pk, elsewhere.pk]).count(), 2)
        self.assertFalse(storages["private"].exists(file_name))

        # Other targets don't take deletes from the grid.
        response = self.post("/admin/uploads/delete/", {
            "target": "portal.captionitem", "parent": workspace.pk, "ids": [1]})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.client.get("/admin/uploads/delete/").status_code, 405)

    def test_delete_selected_needs_delete_permission(self):
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Permission

        photo = self.photo(self.event)
        clerk = get_user_model().objects.create_user("clerk", password="pass", is_staff=True)
        clerk.user_permissions.add(*Permission.objects.filter(
            codename__in=["view_event", "change_event", "view_eventphoto", "add_eventphoto"]))
        self.client.force_login(clerk)
        html = self.client.get(f"/admin/catalog/event/{self.event.pk}/change/").content.decode()
        self.assertNotIn("bulk-selectbar", html)
        response = self.post("/admin/uploads/delete/", {
            "target": "catalog.eventphoto", "parent": self.event.pk, "ids": [photo.pk]})
        self.assertEqual(response.status_code, 404)
        self.assertTrue(EventPhoto.objects.filter(pk=photo.pk).exists())

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
        # Both drops live on the workspace, class photographs first, with the
        # workspace tools inside that section rather than under the students.
        self.assertIn('data-target="portal.workspacestudent"', html)
        self.assertIn("Class Photographs", html)
        self.assertIn("Individual Photographs Upload", html)
        self.assertLess(html.index('data-target="portal.captionitem"'),
                        html.index('data-target="portal.workspacestudent"'))
        html = self.client.get(f"/admin/catalog/institution/{self.institution.pk}/change/").content.decode()
        self.assertNotIn("data-target=", html)  # no uploader on the institution page
        self.assertIn("Tick every row for deletion", html)  # access-email rows keep their select-all

    def test_workspace_refuses_unfileable_names_before_upload(self):
        from django.core import signing

        from apps.core.models import UploadBatch
        from apps.core.uploads import TOKEN_SALT
        from apps.portal.models import CaptionWorkspace, Student
        from spectrum.storages import private_storage

        workspace = CaptionWorkspace.for_institution(self.institution.pk)
        prepared = self.post("/admin/uploads/prepare/", {
            "target": "portal.workspacestudent", "parentId": workspace.pk, "files": [
                {"clientId": "a", "name": "IMG_7932.JPG", "size": 1000, "type": "image/jpeg"},
                {"clientId": "b", "name": "6C_Aarav.jpg", "size": 1000, "type": "image/jpeg"},
            ]}).json()
        entries = {e["clientId"]: e for e in prepared["files"]}
        self.assertIn("not inside a class folder", entries["a"]["error"])
        self.assertNotIn("token", entries["a"], "a refused file gets no upload slot")
        self.assertIn("token", entries["b"])
        # A bad name that reaches commit anyway is still refused there.
        batch = UploadBatch.objects.get(pk=prepared["batchId"])
        key = private_storage().save("originals/x/IMG_1.JPG", ContentFile(jpeg_bytes()))
        token = signing.dumps([str(batch.pk), "z", key], salt=TOKEN_SALT, compress=True)
        result = self.post(f"/admin/uploads/{batch.pk}/commit/", {
            "files": [{"token": token, "index": 0, "name": "IMG_1.JPG"}]}).json()
        self.assertEqual(result["skipped"], ["z"])
        self.assertFalse(Student.objects.exists())

        html = self.client.get(f"/admin/portal/captionworkspace/{workspace.pk}/change/").content.decode()
        self.assertIn("Drop one folder per class", html)
        self.assertIn("webkitdirectory", html)

    def test_each_folder_becomes_a_class(self):
        from apps.portal.models import SchoolClass, Student

        result = self.workspace_students([
            "6C/IMG_10.jpg", "6C/IMG_2.jpg", "Nursery/a.jpg", "10 science/x.jpg", "12ab/y.jpg", "IMG_7.jpg",
        ])
        self.assertEqual(len(result["created"]), 5)
        self.assertIn("not inside a class folder", result["errors"]["c5"], "a loose camera file is refused")
        classes = {c.name: c for c in SchoolClass.objects.filter(institution=self.institution)}
        self.assertEqual(set(classes), {"6C", "Nursery", "10 science", "12AB"})
        self.assertEqual((classes["10 science"].group, classes["Nursery"].group), ("Senior", "Primary"))
        self.assertEqual([s.source_name for s in Student.objects.filter(school_class=classes["6C"])],
                         ["IMG_2.jpg", "IMG_10.jpg"], "photos in file-name order, numbers numeric")
        # The same folder again adds to its class; the same file name replaces that photo, keeping the name.
        student = Student.objects.get(school_class=classes["6C"], source_name="IMG_2.jpg")
        Student.objects.filter(pk=student.pk).update(name="Aarav Sharma")
        before = student.original.name
        self.workspace_students(["6c/IMG_2.jpg", "6C/IMG_3.jpg"])
        self.assertEqual(SchoolClass.objects.filter(institution=self.institution).count(), 4)
        self.assertEqual(Student.objects.filter(school_class=classes["6C"]).count(), 3)
        student.refresh_from_db()
        self.assertEqual(student.name, "Aarav Sharma")
        self.assertNotEqual(student.original.name, before)

    def test_workspace_grid_groups_photos_by_class_with_download(self):
        import zipfile
        from io import BytesIO

        from apps.portal.models import CaptionWorkspace, SchoolClass, Student

        self.workspace_students(["10A/b.jpg", "2B/a.jpg", "2B/c.jpg", "LKG/k.jpg"])
        workspace = CaptionWorkspace.for_institution(self.institution.pk)
        html = self.client.get(f"/admin/portal/captionworkspace/{workspace.pk}/change/").content.decode()
        section = html[html.index('data-target="portal.workspacestudent"'):]
        titles = [section.index(f'<h3 class="bulk-group-title">{name} ') for name in ("LKG", "2B", "10A")]
        self.assertEqual(titles, sorted(titles), "classes in school order")
        self.assertIn('<option value="all">All classes</option>', section)
        download = f"/admin/portal/captionworkspace/{workspace.pk}/download-students/"
        self.assertIn(f'href="{download}?class=all"', section)

        # Named and unnamed students alike; unnamed ones go by their uploaded file name.
        Student.objects.filter(school_class__name="2B", source_name="a.jpg").update(name="Diya")
        Student.objects.filter(school_class__name="10A").update(name="Kabir")
        with zipfile.ZipFile(BytesIO(b"".join(self.client.get(download + "?class=all").streaming_content))) as zf:
            self.assertEqual(sorted(zf.namelist()), ["DPS-10A-Photos/Kabir.jpg", "DPS-2B-Photos/Diya.jpg",
                                                     "DPS-2B-Photos/Unnamed c.jpg", "DPS-LKG-Photos/Unnamed k.jpg"])
        two_b = SchoolClass.objects.get(institution=self.institution, name="2B")
        response = self.client.get(f"{download}?class={two_b.pk}")
        self.assertIn("DPS-2B-Photos.zip", response["Content-Disposition"])
        # Another institution's class is never in this workspace's zip: back to the page instead.
        other = SchoolClass.objects.create(institution=self.other, name="2B")
        self.assertEqual(self.client.get(f"{download}?class={other.pk}").status_code, 302)

    def test_classes_and_students_come_in_order_on_the_portal(self):
        from apps.portal.models import SchoolClass, class_sort_key

        names = ["12C", "1A", "UKG", "Nursery", "10B", "2A", "LKG", "Class 3"]
        for name in names:
            SchoolClass.objects.create(institution=self.institution, name=name)
        ordered = list(SchoolClass.objects.filter(institution=self.institution).values_list("name", flat=True))
        self.assertEqual(ordered, ["Nursery", "LKG", "UKG", "1A", "2A", "Class 3", "10B", "12C"])
        self.assertLess(class_sort_key("KG"), class_sort_key("1A"))
        changelist = self.client.get("/admin/portal/schoolclass/").content.decode()
        self.assertLess(changelist.index(">Nursery<"), changelist.index(">12C<"))

    def test_workspace_students_land_in_that_institutions_classes(self):
        from apps.portal.models import SchoolClass, Student

        self.workspace_students(["6C_a.jpg"], institution=self.other)
        self.assertFalse(SchoolClass.objects.filter(institution=self.institution).exists())
        self.assertEqual(Student.objects.filter(school_class__institution=self.other).count(), 1)
        # The grid on the workspace page links to the institution's students.
        workspace = self.other.caption_workspace
        html = self.client.get(f"/admin/portal/captionworkspace/{workspace.pk}/change/").content.decode()
        link = f"/admin/portal/student/?school_class__institution__id__exact={self.other.pk}"
        self.assertIn(link, html)
        self.assertEqual(self.client.get(link).status_code, 200)
        # The old institution-page key is gone, so a leftover batch can't misfile.
        response = self.post("/admin/uploads/prepare/", {
            "target": "portal.studentbatch", "parentId": self.institution.pk, "files": []})
        self.assertEqual(response.status_code, 404)


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
