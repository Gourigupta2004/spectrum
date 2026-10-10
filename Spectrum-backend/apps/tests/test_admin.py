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
