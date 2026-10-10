from functools import wraps

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


def edit_wording(title: str) -> str:
    """Page titles say "edit" where Django says "change":
    "Select event to change" -> "Select event to edit", "Change event" ->
    "Edit event". Titles with a colon ("Change password: …", "Change
    history: …") name a different page and are left as they are."""
    if title.startswith("Select ") and title.endswith(" to change"):
        return title[: -len("change")] + "edit"
    if title.startswith("Change ") and ":" not in title:
        return "Edit " + title[len("Change "):]
    return title


class SpectrumAdminSite(AdminSite):
    site_header = "Spectrum"
    site_title = "Spectrum admin"
    index_title = "Manage the website"
    enable_nav_sidebar = True

    def admin_view(self, view, cacheable=False):
        # Every admin page passes through here (ModelAdmin URLs included), so
        # one place rewrites the titles before the page is rendered.
        wrapped = super().admin_view(view, cacheable)

        @wraps(wrapped)
        def inner(request, *args, **kwargs):
            response = wrapped(request, *args, **kwargs)
            context = getattr(response, "context_data", None)
            if isinstance(context, dict) and isinstance(context.get("title"), str):
                context["title"] = edit_wording(context["title"])
            return response

        return inner

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
