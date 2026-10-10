from django.contrib import admin

from apps.core.admin_tools import BulkUploadMixin, ImagePreviewMixin, SingletonAdmin, thumb_html

from .models import (
    AboutPage, Capability, ContactDetail, ContactPage, Enquiry, EventsPage, Faq, GalleryPage, HeroSlide, HomePage,
    PortalPage, Service, SiteSettings, Stat, StoryBlock, TieUp,
)

SEO = ("Search & sharing", {"classes": ("collapse",),
                            "fields": ("seo_title", "seo_description", "og_title", "og_description")})


class OrderedInline(admin.TabularInline):
    extra = 0
    ordering = ("sort_order", "pk")


class ImageInline(ImagePreviewMixin, OrderedInline):
    pass


@admin.register(SiteSettings)
class SiteSettingsAdmin(SingletonAdmin):
    fieldsets = (
        ("Logo & intro video", {"fields": ("logo_light", "logo_mark", "favicon", "intro_video_webm",
                                           "intro_video_mp4", "intro_audio", "session_audio", "intro_skip_label")}),
        ("Navigation", {"fields": ("nav_home", "nav_events", "nav_about", "nav_contact", "nav_portal")}),
        ("Default search & sharing", {"fields": ("seo_title", "seo_description", "og_title", "og_description")}),
        ("Error pages", {"classes": ("collapse",), "fields": ("not_found_title", "not_found_body",
                                                             "not_found_cta", "error_title", "error_body",
                                                             "error_retry")}),
    )


class HeroSlideInline(ImageInline):
    model = HeroSlide
    fields = ("original", "caption", "sort_order")


class StatInline(OrderedInline):
    model = Stat
    fields = ("value", "suffix", "label", "source", "sort_order")


class ServiceInline(OrderedInline):
    model = Service
    fields = ("label", "sort_order")


@admin.register(HomePage)
class HomePageAdmin(BulkUploadMixin, SingletonAdmin):
    bulk_upload_targets = ("content.heroslide",)
    inlines = [HeroSlideInline, StatInline, ServiceInline]
    fieldsets = (
        ("Hero", {"fields": ("hero_title", "hero_subtitle")}),
        ("Sections", {"fields": ("search_placeholder", "institutions_heading", "services_heading",
                                 "services_subtitle", "featured_heading", "featured_cta", "featured_count")}),
        SEO,
    )


class CapabilityInline(OrderedInline):
    model = Capability
    fields = ("label", "sort_order")


class StoryInline(ImageInline):
    model = StoryBlock
    fields = ("original", "title", "body", "alt", "sort_order")


class TieUpInline(ImageInline):
    model = TieUp
    fields = ("original", "name", "note", "sort_order")


class FaqInline(OrderedInline):
    model = Faq
    fields = ("question", "answer", "sort_order")


@admin.register(AboutPage)
class AboutPageAdmin(BulkUploadMixin, SingletonAdmin):
    bulk_upload_targets = ("content.tieup",)
    inlines = [CapabilityInline, StoryInline, TieUpInline, FaqInline]
    fieldsets = (
        ("Copy", {"fields": ("back_label", "lead_line", "pull_quote", "tieups_heading", "tieups_subtitle",
                             "faqs_heading")}),
        ("Our story ticker", {"description": "The slim band above the tie-ups where the story text rises and "
                                             "fades away. One line per sentence.",
                              "fields": ("ticker_heading", "ticker_text")}),
        SEO,
    )


class ContactDetailInline(OrderedInline):
    model = ContactDetail
    fields = ("icon", "label", "value", "sort_order")


@admin.register(ContactPage)
class ContactPageAdmin(SingletonAdmin):
    inlines = [ContactDetailInline]
    fieldsets = (
        ("Heading", {"fields": ("back_label", "title", "subtitle")}),
        ("Form", {"fields": ("name_placeholder", "email_placeholder", "phone_placeholder",
                             "institution_placeholder", "service_placeholder", "other_service_option",
                             "other_service_placeholder", "message_placeholder", "submit_label",
                             "success_message")}),
        ("Details panel", {"fields": ("details_heading", "reply_note")}),
        SEO,
    )


@admin.register(EventsPage)
class EventsPageAdmin(SingletonAdmin):
    fieldsets = (
        (None, {"fields": ("back_label", "title", "empty_state", "photos_label", "price_prefix")}),
        ("Browse institutions step", {"fields": ("browse_title", "browse_subtitle", "browse_events_template")}),
        ("Search", {"fields": ("search_placeholder", "search_empty")}),
        ("Filters", {"description": "The type chips (Schools, Colleges, …) are edited under "
                                    "Catalog → Institution types.",
                     "fields": ("filter_all", "filter_recent", "filter_popular")}),
        SEO,
    )


@admin.register(GalleryPage)
class GalleryPageAdmin(SingletonAdmin):
    fieldsets = (
        ("Gallery", {"fields": ("seo_title_template", "seo_description_template", "back_label", "watermark_text",
                                "select_label", "selected_label")}),
        ("Selection bar", {"fields": ("selection_one", "selection_many", "selection_mixed", "videos_heading",
                                      "filter_photos", "filter_videos", "bundle_selected", "bundle_button",
                                      "bundle_button_no_saving", "pay_cta")}),
        ("Checkout", {"fields": ("summary_heading", "bundle_line", "total_label", "name_placeholder",
                                 "whatsapp_placeholder", "whatsapp_hint", "email_placeholder", "email_hint",
                                 "contact_required", "pay_button", "checkout_error", "not_for_sale_message")}),
        ("After payment", {"fields": ("success_title", "success_body_whatsapp", "success_body_email",
                                      "success_note", "success_back")}),
    )


@admin.register(PortalPage)
class PortalPageAdmin(SingletonAdmin):
    fieldsets = (
        ("Access & sign-in", {"fields": ("access_eyebrow", "access_title", "access_subtitle", "access_placeholder",
                                          "access_button", "access_error", "access_change", "login_eyebrow",
                                          "login_subtitle", "login_title", "login_id_placeholder",
                                          "login_password_placeholder", "login_button", "login_error",
                                          "signed_in_as", "sign_out")}),
        ("Workspace", {"fields": ("workspace_title", "workspace_subtitle", "events_card_title", "events_card_copy",
                                  "students_card_title", "students_card_copy", "idcards_card_title",
                                  "idcards_card_copy", "idcards_card_badge")}),
        ("Caption workspace", {"fields": ("captions_title", "captions_empty_all", "captions_empty_pending",
                                          "captions_empty_submitted", "captions_empty_approved", "locked_title",
                                          "locked_body")}),
        ("Class photographs guidelines popup", {"fields": (
            "guidelines_title", "guidelines_intro", "guidelines_points", "guidelines_outro", "guidelines_prompt",
            "guidelines_link", "guidelines_dismiss")}),
        ("Individual photographs guidelines popup", {"fields": (
            "roster_guidelines_title", "roster_guidelines_intro", "roster_guidelines_points",
            "roster_guidelines_outro", "roster_guidelines_link", "roster_guidelines_dismiss")}),
        ("Students", {"fields": ("classes_subtitle", "roster_title", "student_placeholder")}),
    )


@admin.register(Enquiry)
class EnquiryAdmin(admin.ModelAdmin):
    list_display = ("name", "institution", "service", "email", "phone", "created_at", "handled")
    list_editable = ("handled",)
    list_filter = ("handled",)
    search_fields = ("name", "institution", "email", "phone", "message")
    readonly_fields = ("name", "email", "phone", "institution", "service", "message", "ip", "created_at")
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False


# Keep the thumbnail helper importable for other admins.
__all__ = ["thumb_html"]
