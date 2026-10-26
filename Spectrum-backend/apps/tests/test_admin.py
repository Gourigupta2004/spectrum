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


class VideoUploadProgressTests(SpectrumTestCase):
    """The event page sends a chosen video with a progress bar: its script
    posts the form itself and is told where to go next."""

    def setUp(self):
        super().setUp()
        self.make_catalog()
        self.client.force_login(self.make_staff())
        self.url = reverse("admin:catalog_event_change", args=[self.event.pk])

    def form(self, **extra):
        from django.core.files.uploadedfile import SimpleUploadedFile

        return {
            "name": "Annual Day", "slug": "annual-day", "institution": self.institution.pk,
            "price_per_photo": 29, "price_per_video": 199, "bundle_price": 299, "is_published": "on",
            "sort_order": 0, "videos-TOTAL_FORMS": 1, "videos-INITIAL_FORMS": 0, "videos-MIN_NUM_FORMS": 0,
            "videos-MAX_NUM_FORMS": 1000, "videos-0-title": "Highlights", "videos-0-sort_order": 0,
            "videos-0-video": SimpleUploadedFile("highlights.mp4", b"fake-video-bytes", content_type="video/mp4"),
            "_continue": "Save and continue editing", **extra,
        }

    def test_event_page_loads_the_progress_script(self):
        html = self.client.get(self.url).content.decode()
        self.assertIn("core/save-progress.js", html)
        self.assertIn("core/save-progress.css", html)

    def test_save_from_the_script_answers_with_the_next_page_and_keeps_the_message(self):
        response = self.client.post(self.url, self.form(), HTTP_X_UPLOAD_PROGRESS="1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"redirect": self.url})
        self.assertEqual(self.event.videos.get().title, "Highlights")
        page = self.client.get(self.url).content.decode()
        self.assertIn("was changed successfully", page)

    def test_plain_save_still_redirects(self):
        response = self.client.post(self.url, self.form())
        self.assertRedirects(response, self.url)

    def test_form_errors_come_back_as_the_page(self):
        response = self.client.post(self.url, self.form(name=""), HTTP_X_UPLOAD_PROGRESS="1")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response["Content-Type"])
        self.assertFalse(self.event.videos.exists())
