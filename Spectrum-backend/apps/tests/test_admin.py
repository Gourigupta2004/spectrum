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
