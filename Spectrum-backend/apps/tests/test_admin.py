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
        self.assertIn("Founder", html)
        self.assertNotIn("Photo 1", html)



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
