from django.contrib import admin
from django.urls import reverse

from apps.content.models import HomePage

from .base import SpectrumTestCase


class AdminSmokeTests(SpectrumTestCase):
    def setUp(self):
        super().setUp()
        self.make_catalog()
        self.photo(self.event)
        self.client.force_login(self.make_staff())

    def test_every_admin_page_renders(self):
        self.assertEqual(self.client.get("/admin/").status_code, 200)
        for model, model_admin in admin.site._registry.items():
            meta = model._meta
            response = self.client.get(reverse(f"admin:{meta.app_label}_{meta.model_name}_changelist"), follow=True)
            self.assertEqual(response.status_code, 200, meta.label)
            if model_admin.has_add_permission(response.wsgi_request):
                add = self.client.get(reverse(f"admin:{meta.app_label}_{meta.model_name}_add"))
                self.assertEqual(add.status_code, 200, f"{meta.label} add")
            first = model.objects.first()
            if first is not None:
                change = self.client.get(reverse(f"admin:{meta.app_label}_{meta.model_name}_change", args=[first.pk]))
                self.assertEqual(change.status_code, 200, f"{meta.label} change")

    def test_home_page_has_hero_uploader_and_grouped_index(self):
        HomePage.load()
        html = self.client.get("/admin/content/homepage/", follow=True).content.decode()
        self.assertIn('data-target="content.heroslide"', html)
        index = self.client.get("/admin/").content.decode()
        for group in ("Website content", "Events &amp; galleries", "Institution portal", "Inbox"):
            self.assertIn(group, index)


class DeleteConfirmationTests(SpectrumTestCase):
    """Delete pages list what goes as counts, never a line per object."""

    def setUp(self):
        super().setUp()
        self.make_catalog()
        self.client.force_login(self.make_staff())

    def test_bulk_and_single_deletes_show_only_counts(self):
        from apps.portal.models import SchoolClass, Student

        cls = SchoolClass.objects.create(institution=self.institution, name="6C")
        students = [Student.objects.create(school_class=cls, source_name=f"{i}.jpg") for i in range(3)]
        page = self.client.post("/admin/portal/student/", {
            "action": "delete_selected", "_selected_action": [s.pk for s in students]}).content.decode()
        self.assertIn("Students: 3", page)
        self.assertNotIn(f"Student {students[0].pk}<", page, "no line per object")
        self.assertIn('name="post" value="yes"', page)
        self.client.post("/admin/portal/student/", {
            "action": "delete_selected", "_selected_action": [s.pk for s in students], "post": "yes"})
        self.assertFalse(Student.objects.filter(school_class=cls).exists(), "Yes, I'm sure still deletes")

        Student.objects.create(school_class=cls, source_name="x.jpg")
        page = self.client.get(f"/admin/portal/schoolclass/{cls.pk}/delete/").content.decode()
        self.assertIn("Students: 1", page)
        self.assertNotIn('id="deleted-objects"', page)


class ActiveFilterChipTests(SpectrumTestCase):
    """Every changelist shows what it is filtered by, beside the search bar."""

    def setUp(self):
        super().setUp()
        self.make_catalog()
        self.client.force_login(self.make_staff())

    def chips(self, url):
        html = self.client.get(url).content.decode()
        if 'class="active-filters"' not in html:
            return html, ""
        start = html.index('class="active-filters"')
        return html, html[start:html.index("</div>", start)]

    def test_no_chips_without_filters(self):
        html, chips = self.chips("/admin/catalog/event/")
        self.assertEqual(chips, "")

    def test_filters_date_and_search_become_removable_chips(self):
        from django.utils.html import escape

        self.event.date = __import__("datetime").date(2026, 10, 3)
        self.event.save()
        url = (f"/admin/catalog/event/?institution__id__exact={self.institution.pk}&is_published__exact=1"
               "&date__year=2026&date__month=10&q=annual")
        html, chips = self.chips(url)
        self.assertIn("Delhi Public School", chips)
        self.assertIn("Published:</span> Yes", chips)
        self.assertIn("October 2026", chips)
        self.assertIn("“annual”", chips)
        self.assertIn("Clear all", chips)
        # The chips sit right under the search bar, above the results.
        self.assertLess(html.index('id="changelist-search"'), html.index('class="active-filters"'))
        self.assertLess(html.index('class="active-filters"'), html.index('id="result_list"'))
        # Removing the institution chip keeps every other filter.
        remove = escape("?date__month=10&date__year=2026&is_published__exact=1&q=annual")
        self.assertIn(f'href="{remove}"', chips)
        self.assertIn('href="?"', chips)  # clear all

    def test_lookup_from_a_link_without_a_sidebar_filter(self):
        from apps.portal.models import SchoolClass

        cls = SchoolClass.objects.create(institution=self.institution, name="6C")
        html, chips = self.chips(f"/admin/portal/student/?school_class__id__exact={cls.pk}")
        self.assertIn("6C", chips)
        html, chips = self.chips(f"/admin/portal/student/?school_class__institution__id__exact={self.institution.pk}")
        self.assertIn("Delhi Public School", chips)
        self.assertNotIn("Clear all", chips, "one chip needs no clear-all")


class WordingAndHeadingTests(SpectrumTestCase):
    def setUp(self):
        super().setUp()
        self.make_catalog()
        self.client.force_login(self.make_staff())

    def test_titles_say_edit_not_change(self):
        from spectrum.admin_site import edit_wording

        html = self.client.get("/admin/portal/captionworkspace/").content.decode()
        self.assertIn("Select institution workspace to edit", html)
        self.assertNotIn("to change", html)
        html = self.client.get(f"/admin/catalog/institution/{self.institution.pk}/change/").content.decode()
        self.assertIn("<h1>Edit institution</h1>", html)
        self.assertIn("| Edit institution |", html)  # the browser tab too
        self.assertEqual(edit_wording("Change password: admin"), "Change password: admin")
        self.assertEqual(edit_wording("Add event"), "Add event")

    def test_form_section_headers_are_upper_case(self):
        html = self.client.get(f"/admin/catalog/event/{self.event.pk}/change/").content.decode()
        self.assertIn(".change-form fieldset .fieldset-heading", html)
        self.assertIn("text-transform: uppercase", html)


class EventDeleteConfirmationTests(SpectrumTestCase):
    def setUp(self):
        super().setUp()
        self.make_catalog()
        self.client.force_login(self.make_staff())

    def test_confirmation_lists_events_not_their_photos(self):
        for i in range(3):
            self.photo(self.event, f"Photo {i}")
        page = self.client.get(f"/admin/catalog/event/{self.event.pk}/delete/").content.decode()
        self.assertIn("Annual Day", page)
        self.assertNotIn("Photo 1", page, "photos aren't listed one by one")
        self.assertIn("All photos: 3", page.replace("\n", " ").replace("</li>", "").replace("<li>", ""))
        bulk = self.client.post("/admin/catalog/event/", {"action": "delete_selected",
                                                          "_selected_action": [self.event.pk, self.other_event.pk]})
        html = bulk.content.decode()
        self.assertIn("Events: 2", html, "counts only (spectrum/templates/admin/delete_*)")
        self.assertNotIn("Founder", html)
        self.assertNotIn("Photo 1", html)



class FakeS3:
    """Just enough of boto3's S3 client for multipart uploads, kept in memory."""

    def __init__(self):
        self.uploads, self.objects, self.aborted = {}, {}, []

    def create_multipart_upload(self, Bucket, Key, ContentType):
        upload_id = f"up-{len(self.uploads) + 1}"
        self.uploads[upload_id] = {"key": Key, "parts": {}, "initiated": self.now()}
        return {"UploadId": upload_id}

    def now(self):
        from django.utils import timezone

        return timezone.now()

    def generate_presigned_url(self, operation, Params, ExpiresIn):
        return f"https://s3.test/{Params['Key']}?{operation}&part={Params.get('PartNumber', '')}"

    def put_part(self, upload_id, number, data):  # what the browser's PUT does
        self.uploads[upload_id]["parts"][number] = data

    def list_parts(self, Bucket, Key, UploadId, PartNumberMarker=0):
        upload = self.uploads[UploadId]
        assert upload["key"] == Key
        numbers = sorted(n for n in upload["parts"] if n > PartNumberMarker)
        page = numbers[:2]  # small pages, so paging is exercised
        return {"Parts": [{"PartNumber": n, "ETag": f'"etag-{n}"'} for n in page],
                "IsTruncated": len(numbers) > 2, "NextPartNumberMarker": page[-1] if page else 0}

    def complete_multipart_upload(self, Bucket, Key, UploadId, MultipartUpload):
        upload = self.uploads.pop(UploadId)
        self.objects[Key] = b"".join(upload["parts"][p["PartNumber"]] for p in MultipartUpload["Parts"])

    def abort_multipart_upload(self, Bucket, Key, UploadId):
        self.uploads.pop(UploadId, None)
        self.aborted.append(UploadId)

    def list_multipart_uploads(self, Bucket, Prefix, **markers):
        return {"Uploads": [{"Key": u["key"], "UploadId": i, "Initiated": u["initiated"]}
                            for i, u in self.uploads.items() if u["key"].startswith(Prefix)], "IsTruncated": False}


class FakeS3Storage:
    bucket_name = "test-bucket"

    def __init__(self, client):
        from types import SimpleNamespace

        self.connection = SimpleNamespace(meta=SimpleNamespace(client=client))

    def _normalize_name(self, name):
        return f"private/{name}"

    def exists(self, name):
        return self._normalize_name(name) in self.connection.meta.client.objects


class MultipartVideoUploadTests(SpectrumTestCase):
    """On S3, a video over 200 MB goes up in parts, so the 5 GB single-PUT limit no longer applies."""

    def setUp(self):
        from unittest import mock

        super().setUp()
        self.make_catalog()
        self.client.force_login(self.make_staff())
        self.s3 = FakeS3()
        storage = FakeS3Storage(self.s3)
        for target in ("apps.catalog.video_uploads.private_storage", "apps.core.uploads.private_storage"):
            patcher = mock.patch(target, return_value=storage)
            patcher.start()
            self.addCleanup(patcher.stop)

    def post(self, name, body):
        return self.client.post(reverse(name), body, content_type="application/json")

    def test_a_video_over_5_gb_is_prepared_in_parts(self):
        from apps.catalog.video_uploads import part_size

        size = 6 * 1024 ** 3
        entry = self.post("admin-video-upload-prepare", {"name": "day.mp4", "size": size, "type": "video/mp4"}).json()
        self.assertEqual(entry["method"], "MULTIPART")
        self.assertEqual(entry["partSize"], 64 * 1024 ** 2)
        self.assertLessEqual(-(-size // entry["partSize"]), 10_000)
        self.assertGreater(part_size(1024 ** 4), 64 * 1024 ** 2, "a 1 TB file still fits in 10,000 parts")
        small = self.post("admin-video-upload-prepare", {"name": "clip.mp4", "size": 50 * 1024 ** 2}).json()
        self.assertEqual(small["method"], "PUT", "small videos keep the single upload")
        with self.settings(VIDEO_UPLOAD_MAX_BYTES=10 * 1024 ** 3):
            refused = self.post("admin-video-upload-prepare", {"name": "day.mp4", "size": 11 * 1024 ** 3})
        self.assertEqual(refused.status_code, 400, "the configured cap still applies")

    def test_parts_are_presigned_then_joined_and_the_video_saves(self):
        entry = self.post("admin-video-upload-prepare", {"name": "day.mp4", "size": 300 * 1024 ** 2}).json()
        base = {"token": entry["token"], "uploadId": entry["uploadId"]}
        urls = self.post("admin-video-upload-parts", {**base, "numbers": [1, 2, 3, 4, 5]}).json()["urls"]
        self.assertEqual(sorted(urls), ["1", "2", "3", "4", "5"])
        self.assertIn("upload_part", urls["1"])
        for n in range(1, 6):
            self.s3.put_part(entry["uploadId"], n, f"part{n};".encode())
        self.assertEqual(self.post("admin-video-upload-complete", {**base, "parts": 6}).status_code, 409,
                         "a missing part is caught")
        self.assertEqual(self.post("admin-video-upload-complete", {**base, "parts": 5}).json(), {"ok": True})
        key = next(iter(self.s3.objects))
        self.assertEqual(self.s3.objects[key], b"part1;part2;part3;part4;part5;")

        url = reverse("admin:catalog_event_change", args=[self.event.pk])
        form = VideoUploadTests.form(self, video=entry["token"])
        self.assertRedirects(self.client.post(url, form), url)
        self.assertEqual("private/" + self.event.videos.get().video.name, key)

    def test_a_forged_token_or_an_abandoned_upload_is_handled(self):
        from datetime import timedelta

        from apps.catalog.video_uploads import abort_stale_multipart_uploads

        entry = self.post("admin-video-upload-prepare", {"name": "day.mp4", "size": 300 * 1024 ** 2}).json()
        forged = self.post("admin-video-upload-parts", {"token": "nope", "uploadId": entry["uploadId"], "numbers": [1]})
        self.assertEqual(forged.status_code, 400)
        self.assertEqual(abort_stale_multipart_uploads(), 0, "a fresh upload is left alone")
        self.s3.uploads[entry["uploadId"]]["initiated"] -= timedelta(days=3)
        self.assertEqual(abort_stale_multipart_uploads(), 1)
        self.assertEqual(self.s3.aborted, [entry["uploadId"]])
        again = self.post("admin-video-upload-prepare", {"name": "b.mp4", "size": 300 * 1024 ** 2}).json()
        self.post("admin-video-upload-abort", {"token": again["token"], "uploadId": again["uploadId"]})
        self.assertIn(again["uploadId"], self.s3.aborted)


class VideoUploadTests(SpectrumTestCase):
    """The event's video field uploads as soon as a file is chosen; Save
    sends only the upload's token."""

    def setUp(self):
        super().setUp()
        self.make_catalog()
        self.client.force_login(self.make_staff())
        self.url = reverse("admin:catalog_event_change", args=[self.event.pk])

    def upload(self, name="highlights.mp4", data=b"fake-video-bytes"):
        from django.core.files.uploadedfile import SimpleUploadedFile

        entry = self.client.post(reverse("admin-video-upload-prepare"), {"name": name, "size": len(data)},
                                 content_type="application/json").json()
        self.assertEqual(entry["method"], "POST")
        sent = self.client.post(entry["uploadUrl"], {"token": entry["token"], "file": SimpleUploadedFile(name, data)})
        self.assertEqual(sent.json(), {"ok": True})
        return entry["token"]

    def form(self, video="", initial=0, pk="", **extra):
        return {
            "name": "Annual Day", "slug": "annual-day", "institution": self.institution.pk,
            "price_per_photo": 29, "price_per_video": 199, "bundle_price": 299, "is_published": "on",
            "sort_order": 0, "videos-TOTAL_FORMS": 1, "videos-INITIAL_FORMS": initial, "videos-MIN_NUM_FORMS": 0,
            "videos-MAX_NUM_FORMS": 1000, "videos-0-id": pk, "videos-0-event": self.event.pk,
            "videos-0-title": "Highlights", "videos-0-sort_order": 0, "videos-0-video": video,
            "_continue": "Save and continue editing", **extra,
        }

    def test_event_page_has_the_instant_video_uploader(self):
        html = self.client.get(self.url).content.decode()
        self.assertIn('class="video-upload-input"', html)
        self.assertIn("catalog/video-upload.js", html)
        self.assertIn(reverse("admin-video-upload-prepare"), html)
        self.assertIn("Video file</th>", html.replace("\n", "").replace("  ", ""))

    def test_prepare_refuses_what_is_not_a_video_or_too_big(self):
        prepare = reverse("admin-video-upload-prepare")
        refused = self.client.post(prepare, {"name": "a.jpg", "size": 10}, content_type="application/json")
        self.assertEqual(refused.status_code, 400)
        with self.settings(VIDEO_UPLOAD_MAX_BYTES=100):
            big = self.client.post(prepare, {"name": "a.mp4", "size": 101}, content_type="application/json")
        self.assertEqual(big.status_code, 400)

    def test_saving_with_the_token_attaches_the_uploaded_file(self):
        from spectrum.storages import private_storage

        token = self.upload()
        response = self.client.post(self.url, self.form(video=token))
        self.assertRedirects(response, self.url)
        video = self.event.videos.get()
        self.assertTrue(video.video.name.startswith("catalog/eventvideo/videos/"))
        self.assertTrue(video.video.name.endswith(".mp4"))
        with private_storage().open(video.video.name) as stored:
            self.assertEqual(stored.read(), b"fake-video-bytes")

    def test_saving_without_a_new_upload_keeps_the_video_and_replacing_deletes_the_old(self):
        from spectrum.storages import private_storage

        video = self.video(self.event, "Highlights")
        old = video.video.name
        self.assertRedirects(self.client.post(self.url, self.form(initial=1, pk=video.pk)), self.url)
        video.refresh_from_db()
        self.assertEqual(video.video.name, old)

        token = self.upload()
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(self.url, self.form(video=token, initial=1, pk=video.pk))
        video.refresh_from_db()
        self.assertNotEqual(video.video.name, old)
        self.assertFalse(private_storage().exists(old))

    def test_new_row_needs_a_finished_upload_and_a_real_token(self):
        response = self.client.post(self.url, self.form())
        self.assertContains(response, "Choose the video file and wait for its upload to finish.")
        response = self.client.post(self.url, self.form(video="forged"))
        self.assertContains(response, "This upload has expired.")
        self.assertFalse(self.event.videos.exists())

    def test_housekeeping_deletes_uploads_that_were_never_saved(self):
        from datetime import timedelta

        from django.utils import timezone

        from apps.catalog.video_uploads import unsign
        from apps.core.jobs import housekeeping
        from apps.core.models import UploadBatch
        from spectrum.storages import private_storage

        kept = self.upload()
        dropped = unsign(self.upload())
        self.client.post(self.url, self.form(video=kept))
        UploadBatch.objects.update(created_at=timezone.now() - timedelta(days=8))
        housekeeping()
        self.assertFalse(private_storage().exists(dropped))
        self.assertTrue(private_storage().exists(self.event.videos.get().video.name))


class EventSlugTests(SpectrumTestCase):
    """Events with the same name at different schools get different links."""

    def setUp(self):
        super().setUp()
        self.make_catalog()
        self.client.force_login(self.make_staff())

    def add(self, **extra):
        data = {"name": "Prize Distribution", "slug": "", "institution": self.institution.pk,
                "price_per_photo": 29, "price_per_video": 199, "bundle_price": 299, "is_published": "on",
                "sort_order": 0, "videos-TOTAL_FORMS": 0, "videos-INITIAL_FORMS": 0, "videos-MIN_NUM_FORMS": 0,
                "videos-MAX_NUM_FORMS": 1000, **extra}
        response = self.client.post(reverse("admin:catalog_event_add"), data)
        self.assertEqual(response.status_code, 302, response.content.decode()[:3000])
        from apps.catalog.models import Event

        return Event.objects.latest("pk")

    def test_blank_slug_becomes_name_and_number_so_same_names_never_clash(self):
        first = self.add()
        second = self.add(institution=self.other.pk)
        self.assertEqual(first.slug, f"prize-distribution-{first.pk}")
        self.assertEqual(second.slug, f"prize-distribution-{second.pk}")
        self.assertEqual(self.client.get(f"/api/events/{second.slug}/").status_code, 200)

    def test_existing_and_typed_slugs_are_kept(self):
        self.event.name = "Annual Day 2026"
        self.event.save()
        self.event.refresh_from_db()
        self.assertEqual(self.event.slug, "annual-day", "old links keep working")
        typed = self.add(slug="dps-prize-day")
        self.assertEqual(typed.slug, "dps-prize-day")

    def test_a_number_slug_someone_already_took_is_stepped_past(self):
        from apps.catalog.models import Event

        taken = Event.objects.latest("pk").pk + 1
        Event.objects.create(slug=f"prize-distribution-{taken}", name="Old", institution=self.other)
        event = Event.objects.create(name="Prize Distribution", institution=self.institution)
        self.assertNotEqual(event.slug, f"prize-distribution-{taken}")
        self.assertTrue(event.slug.startswith(f"prize-distribution-{event.pk}"))

    def test_add_page_no_longer_prefills_the_slug(self):
        html = self.client.get(reverse("admin:catalog_event_add")).content.decode()
        self.assertIn('data-prepopulated-fields="[]"', html)
