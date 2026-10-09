from django.contrib.admin import AdminSite

GROUPS = [
    ("Website content", [
        "content.sitesettings", "content.homepage", "content.aboutpage", "content.contactpage",
        "content.eventspage", "content.gallerypage", "content.portalpage",
    ]),
    ("Events & galleries", ["catalog.event", "catalog.eventphoto"]),
    # Institutions live in the catalog app (their table is unchanged); they are
    # only listed here, beside the portal they sign in to.
    # Class photograph items are edited on their institution workspace; portal
    # sign-ins live on the institution (and, for the Spectrum team, on Users).
    ("Institution portal", [
        "catalog.institution", "portal.captionworkspace", "portal.schoolclass", "portal.student",
        "portal.portalaccessemail",
    ]),
    ("Inbox", ["content.enquiry", "orders.order", "orders.delivery"]),
    ("System", ["core.task", "auth.user", "catalog.institutionkind"]),
]


class SpectrumAdminSite(AdminSite):
    site_header = "Spectrum"
    site_title = "Spectrum admin"
    index_title = "Manage the website"
    enable_nav_sidebar = True

    def get_app_list(self, request, app_label=None):
        app_list = super().get_app_list(request, app_label)
        if app_label:
            return app_list
        by_key = {
            f"{app['app_label']}.{model['object_name'].lower()}": model
            for app in app_list
            for model in app["models"]
        }
        grouped = []
        for index, (title, keys) in enumerate(GROUPS):
            models = [by_key.pop(key) for key in keys if key in by_key]
            if models:
                grouped.append({"name": title, "app_label": f"group{index}", "app_url": "",
                                "has_module_perms": True, "models": models})
        if by_key:
            grouped.append({"name": "Other", "app_label": "other", "app_url": "", "has_module_perms": True,
                            "models": list(by_key.values())})
        return grouped
