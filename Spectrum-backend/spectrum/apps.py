from django.contrib.admin.apps import AdminConfig


class SpectrumAdminConfig(AdminConfig):
    default_site = "spectrum.admin_site.SpectrumAdminSite"
