"""
Everything on the public site except the footer.

Text fields default to the copy the site shipped with, so a fresh database already
renders the current site. Wrap a word in [brackets] to paint it with the Spectrum
gradient, e.g. "Every Moment, [Yours] Forever".
"""

from django.db import models

from apps.core.models import ProcessedImage, SingletonModel

BRACKET_HELP = "Wrap words in [brackets] to show them in the Spectrum gradient."


def line(default: str, max_length: int = 200, help_text: str = "") -> models.CharField:
    return models.CharField(max_length=max_length, default=default, blank=True, help_text=help_text)


def para(default: str, help_text: str = "") -> models.TextField:
    return models.TextField(default=default, blank=True, help_text=help_text)


class Seo(models.Model):
    seo_title = line("")
    seo_description = models.TextField(blank=True, default="")
    og_title = line("", help_text="Title when shared on WhatsApp or social media. Blank uses the page title.")
    og_description = models.TextField(blank=True, default="")

    class Meta:
        abstract = True

    def seo(self) -> dict:
        return {
            "title": self.seo_title,
            "description": self.seo_description,
            "ogTitle": self.og_title or self.seo_title,
            "ogDescription": self.og_description or self.seo_description,
        }


class Ordered(models.Model):
    sort_order = models.PositiveIntegerField("order", default=0, db_index=True)

    class Meta:
        abstract = True
        ordering = ["sort_order", "pk"]


# --------------------------------------------------------------------------- site


def site_upload(instance, filename):
    return f"site/{filename}"


class SiteSettings(SingletonModel):
    logo_light = models.FileField("logo (light, for dark backgrounds)", upload_to=site_upload, blank=True)
    logo_mark = models.FileField("logo mark (small screens)", upload_to=site_upload, blank=True)
    favicon = models.FileField(upload_to=site_upload, blank=True)
    intro_video_webm = models.FileField("intro video (WebM)", upload_to=site_upload, blank=True)
    intro_video_mp4 = models.FileField("intro video (MP4)", upload_to=site_upload, blank=True)
    intro_audio = models.FileField("intro sound (MP3)", upload_to=site_upload, blank=True,
                                   help_text="Plays with the brand intro. Browsers only allow sound after the "
                                             "visitor has interacted, so it may start on their first tap/click.")
    intro_skip_label = line("Skip", 40)
    session_audio = models.FileField("background music (MP3)", upload_to=site_upload, blank=True,
                                     help_text="Soft loop that plays through the visit, starting a beat after "
                                               "the intro. Visitors can mute it from the navbar.")

    nav_home = line("Home", 40, help_text="Used in the footer; the navbar shows the logo instead.")
    nav_events = line("Events", 40)
    nav_about = line("About Us", 40)
    nav_contact = line("Contact", 40)
    nav_portal = line("Institution Portal", 40, help_text="Navbar link to the institution portal.")

    seo_title = line("Spectrum — Every Moment, Yours Forever")
    seo_description = para("Spectrum captures school and college events across India.")
    og_title = line("Spectrum — Every Moment, Yours Forever")
    og_description = para("Premium school and college event photography.")

    not_found_title = line("Page not found")
    not_found_body = para("The page you're looking for doesn't exist or has been moved.")
    not_found_cta = line("Go home", 60)
    error_title = line("This page didn't load")
    error_body = para("Something went wrong on our end. You can try refreshing or head back home.")
    error_retry = line("Try again", 60)

    class Meta:
        verbose_name = "site settings"
        verbose_name_plural = "site settings"


# --------------------------------------------------------------------------- home


class HomePage(Seo, SingletonModel):
    seo_title = line("Spectrum — School & College Event Photography")
    seo_description = para(
        "Spectrum captures the events that define institutions. Browse protected galleries, choose your photos, "
        "and own your memories in full resolution."
    )
    og_title = line("Spectrum — Every Moment, Yours Forever")
    og_description = para("Premium event photography for schools and colleges. Browse, choose, and own your memories.")
    hero_title = line("Every Moment, [Yours] Forever", help_text=BRACKET_HELP)
    hero_subtitle = para("Spectrum captures the moments for institutions. Browse, choose, and own your memories.")
    search_placeholder = line("Click here to browse institutions…",
                              help_text="Label on the search-bar-styled button that opens the institutions page.")
    institutions_heading = line("Browse by Institution")
    services_heading = line("Our Services")
    services_subtitle = para("We provide professional coverage.")
    featured_heading = line("Recently Captured")
    featured_cta = line("View All Events", 60)
    featured_count = models.PositiveSmallIntegerField("events to feature", default=6)

    class Meta:
        verbose_name = "home page"


class HeroSlide(Ordered, ProcessedImage):
    VARIANTS = {"web": 1200, "thumb": 400}

    page = models.ForeignKey(HomePage, default=1, on_delete=models.CASCADE, related_name="hero_slides", editable=False)
    caption = line("")

    class Meta(Ordered.Meta):
        verbose_name = "hero slide"

    def __str__(self):
        return self.caption or f"Slide {self.pk}"


class Stat(Ordered):
    EVENTS, INSTITUTIONS, PHOTOS = "events", "institutions", "photos"
    SOURCES = [
        ("", "Nothing — show the number as is"),
        (EVENTS, "Published events"),
        (INSTITUTIONS, "Published institutions"),
        (PHOTOS, "Photos delivered (paid orders)"),
    ]

    page = models.ForeignKey(HomePage, default=1, on_delete=models.CASCADE, related_name="stats", editable=False)
    value = models.PositiveIntegerField(help_text="Base number. The live count, if chosen, is added on top.")
    suffix = models.CharField(max_length=10, blank=True, help_text='Shown after the number, e.g. "+".')
    label = models.CharField(max_length=80)
    source = models.CharField("add live count of", max_length=12, choices=SOURCES, default="", blank=True,
                              help_text="The number grows by itself as the platform delivers more.")

    class Meta(Ordered.Meta):
        verbose_name = "stat"

    def __str__(self):
        return self.label


class Service(Ordered):
    page = models.ForeignKey(HomePage, default=1, on_delete=models.CASCADE, related_name="services", editable=False)
    label = models.CharField(max_length=120)

    class Meta(Ordered.Meta):
        verbose_name = "service"

    def __str__(self):
        return self.label


# --------------------------------------------------------------------------- about


class AboutPage(Seo, SingletonModel):
    seo_title = line("About Us — Spectrum")
    seo_description = para(
        "Established in 1980, Spectrum has spent nearly five decades photographing the institutions of the NCR — "
        "from film to digital, all in-house."
    )
    og_title = line("About Us — Spectrum")
    og_description = para("Nearly five decades of experience, precision, and trust in institutional photography.")
    back_label = line("Home", 40)
    lead_line = para(
        "Established in 1980 — Nearly [Five Decades] of Experience, Precision, and Trust.", BRACKET_HELP
    )
    pull_quote = para(
        "[Technology] has changed. [Photography] has evolved. Our [commitment] to quality remains constant.",
        BRACKET_HELP,
    )
    ticker_heading = line("Our [Story]", 80, help_text=BRACKET_HELP)
    ticker_text = para(
        "In 1980, a single camera and a belief: every institution's moments deserve to be kept beautifully.\n"
        "We began in the darkrooms of Delhi, printing school annual days frame by frame.\n"
        "Film gave way to digital; our standards never did.\n"
        "Four decades on, the same families recognise us at the school gate.\n"
        "Every event we cover is edited, curated and delivered entirely in-house.\n"
        "Because a photograph is not a file — it is the day itself, kept safe.\n"
        "Spectrum — imagination that works, since 1980.",
        help_text="The slowly rising story above the tie-ups. Each line scrolls past on its own; "
                  "wrap words in [brackets] for the gradient.",
    )
    tieups_heading = line("Our Tie-Ups")
    tieups_subtitle = para("Decades-long relationships with the institutions we're proud to call partners.")
    faqs_heading = line("FAQs")

    class Meta:
        verbose_name = "about page"


class Capability(Ordered):
    page = models.ForeignKey(AboutPage, default=1, on_delete=models.CASCADE, related_name="capabilities", editable=False)
    label = models.CharField(max_length=120)

    class Meta(Ordered.Meta):
        verbose_name_plural = "capabilities"

    def __str__(self):
        return self.label


class StoryBlock(Ordered, ProcessedImage):
    VARIANTS = {"web": 1200, "thumb": 400}

    page = models.ForeignKey(AboutPage, default=1, on_delete=models.CASCADE, related_name="story", editable=False)
    title = models.CharField(max_length=120)
    body = models.TextField()
    alt = models.CharField("image description", max_length=200, blank=True)

    class Meta(Ordered.Meta):
        verbose_name = "story section"

    def __str__(self):
        return self.title


class TieUp(Ordered, ProcessedImage):
    VARIANTS = {"web": 480, "thumb": 200}

    page = models.ForeignKey(AboutPage, default=1, on_delete=models.CASCADE, related_name="tie_ups", editable=False)
    name = models.CharField(max_length=160)
    note = models.CharField("line under the name", max_length=120, blank=True,
                            help_text='Shown as written, e.g. "Tied up for 15+ years". Blank shows nothing.')

    class Meta(Ordered.Meta):
        verbose_name = "tie-up"

    def __str__(self):
        return self.name


class Faq(Ordered):
    page = models.ForeignKey(AboutPage, default=1, on_delete=models.CASCADE, related_name="faqs", editable=False)
    question = models.CharField(max_length=300)
    answer = models.TextField()

    class Meta(Ordered.Meta):
        verbose_name = "FAQ"

    def __str__(self):
        return self.question


# --------------------------------------------------------------------------- contact


class ContactPage(Seo, SingletonModel):
    seo_title = line("Contact Spectrum — Book Event Photography")
    seo_description = para(
        "Talk to Spectrum about covering your school or college event. Email, WhatsApp or send us a message "
        "and we'll plan the shoot."
    )
    og_title = line("Contact Spectrum")
    og_description = para("Get in touch with Spectrum for school and college event photography in India.")
    back_label = line("Home", 40)
    title = line("Get In [Touch]", help_text=BRACKET_HELP)
    subtitle = para("Planning an annual day, fest or graduation? Tell us the date and we'll take it from there.")
    name_placeholder = line("Your Name")
    email_placeholder = line("Email Address")
    phone_placeholder = line("Phone Number")
    institution_placeholder = line("Institution")
    service_placeholder = line("Services")
    other_service_option = line("Other", 60)
    other_service_placeholder = line("Tell us which service you need")
    message_placeholder = line("Tell us about your event")
    submit_label = line("Send Message", 60)
    success_message = para("Thank you. We'll get back to you within one working day.")
    details_heading = line("Reach us directly")
    reply_note = para(
        "We reply to every enquiry within one working day. For an event happening this week, WhatsApp is fastest."
    )

    class Meta:
        verbose_name = "contact page"


class ContactDetail(Ordered):
    ICONS = [("mail", "Email"), ("phone", "Phone"), ("whatsapp", "WhatsApp"), ("map", "Address"), ("clock", "Hours")]

    page = models.ForeignKey(ContactPage, default=1, on_delete=models.CASCADE, related_name="details", editable=False)
    icon = models.CharField(max_length=20, choices=ICONS, default="mail")
    label = models.CharField(max_length=60)
    value = models.CharField(max_length=200)

    class Meta(Ordered.Meta):
        verbose_name = "contact detail"

    def __str__(self):
        return self.label


class Enquiry(models.Model):
    name = models.CharField(max_length=120)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    institution = models.CharField(max_length=160, blank=True)
    service = models.CharField(max_length=160, blank=True)
    message = models.TextField(blank=True)
    handled = models.BooleanField(default=False, db_index=True)
    ip = models.GenericIPAddressField(null=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "enquiries"

    def __str__(self):
        return f"{self.name} · {self.institution or self.email}"


# --------------------------------------------------------------------------- events, gallery, portal copy


class EventsPage(Seo, SingletonModel):
    seo_title = line("All Events — Spectrum Event Photography")
    seo_description = para(
        "Browse every school and college event captured by Spectrum — annual days, sports meets, graduations "
        "and cultural fests."
    )
    og_title = line("All Events — Spectrum")
    og_description = para("Browse every school and college event captured by Spectrum.")
    back_label = line("Home", 40)
    title = line("All Events")
    browse_title = line("Choose Your [Institution]", help_text=BRACKET_HELP)
    browse_subtitle = para("Pick your school or college to see every event we've covered there.")
    browse_events_template = line("{count} events", 60, help_text="Under each icon; {count} is the event count.")
    filter_all = line("All", 40)
    # The chips between "All" and "Recent" come from the institution types in the catalog.
    filter_recent = line("Recent", 40)
    filter_popular = line("Popular", 40)
    empty_state = line("No events match this filter.")
    search_placeholder = line("Search events or institutions…", 80)
    search_empty = line("Nothing matches “{query}”. Try the institution's name or the event.")
    photos_label = line("photos", 40, help_text='Shown on event cards: "March 15, 2025 · 182 photos".')
    price_prefix = line("From ₹", 40)

    class Meta:
        verbose_name = "events page"


class GalleryPage(SingletonModel):
    seo_title_template = line("{event} Gallery — {institution} | Spectrum",
                              help_text="{event} and {institution} are filled in per event.")
    seo_description_template = para(
        "Browse every photo from {event} at {institution}. Select the ones you love and get full-resolution files instantly."
    )
    back_label = line("All Events", 40)
    watermark_text = line("Preview Only", 60)
    select_label = line("Select This Photo", 60)
    selected_label = line("Selected", 60)
    selection_one = line("{count} photo selected · ₹{price}")
    selection_many = line("{count} photos selected · ₹{price}")
    selection_mixed = line("{photos} photos + {videos} videos · ₹{price}",
                           help_text="Shown when the selection includes videos.")
    videos_heading = line("Event Videos", 80, help_text="Heading above the videos; hidden when an event has none.")
    filter_photos = line("Photos", 40, help_text="Gallery filter chip; shown when the event has videos.")
    filter_videos = line("Videos", 40)
    bundle_selected = line("Full album selected · {photos} photos · ₹{price}")
    bundle_button = line("Full Album Bundle — Save {savings}% · ₹{price} for all {photos} photos")
    bundle_button_no_saving = line("Full Album Bundle — ₹{price} for all {photos} photos")
    pay_cta = line("Pay & Get Photos →", 60)

    summary_heading = line("Order Summary", 60)
    bundle_line = line("Full Album Bundle — all {photos} photos")
    total_label = line("Total", 40)
    name_placeholder = line("Your Name")
    whatsapp_placeholder = line("WhatsApp Number")
    whatsapp_hint = line("Add, if you want photographs on WhatsApp")
    email_placeholder = line("Email Address")
    email_hint = line("Add, if you want photographs on email")
    contact_required = line("Add a WhatsApp number or email address so we can deliver your memories.")
    pay_button = line("Pay ₹{total} with Razorpay →")
    checkout_error = line("Payment could not be completed. Please try again.")
    not_for_sale_message = para(
        "These photographs are not available for sale. Please contact your Institute’s management.",
        help_text="Shown in place of the checkout for events marked Not for sale.")

    success_title = line("Your Memories Are On Their Way.")
    success_body_whatsapp = para(
        "We're sending your full-resolution photos to your WhatsApp right now. Check your messages in a while."
    )
    success_body_email = para(
        "We're sending your full-resolution photos to your email right now. Check your inbox in a while."
    )
    success_note = line("Didn't receive? Contact us at support@spectrum.in")
    success_back = line("Back to Events", 60)

    class Meta:
        verbose_name = "gallery & checkout page"


class PortalPage(SingletonModel):
    access_eyebrow = line("Institution Access", 60)
    access_title = line("Enter your institution email")
    access_subtitle = para(
        "The workspace is open to institutions Spectrum works with. Use the email address registered with us."
    )
    access_placeholder = line("you@yourschool.edu", 60)
    access_button = line("Continue →", 60)
    access_error = line("This email doesn't have workspace access yet. Contact support@spectrum.in.")
    access_change = line("Use a different email", 60)

    login_eyebrow = line("Institution Login", 60)
    login_subtitle = line("Institution Workspace")
    login_title = line("Sign in to your workspace")
    login_id_placeholder = line("Institution ID", 60)
    login_password_placeholder = line("Password", 60)
    login_button = line("Log In →", 60)
    login_error = line("That ID or password didn't match.")
    signed_in_as = line("Signed in as", 60)
    sign_out = line("Sign Out", 40)

    workspace_title = line("What would you like to work on?")
    workspace_subtitle = line("One institution account, everything in one place.")
    events_card_title = line("Class Photographs", 60)
    events_card_copy = line("Review and correct photo titles for event moments.")
    students_card_title = line("Individual Photographs", 60)
    students_card_copy = line("Identify students in class photos and export a labeled roster.")
    # Announced but not built yet: the card shows, and cannot be opened.
    idcards_card_title = line("ID Cards", 60)
    idcards_card_copy = line("Design, proof and order student ID cards from the class photos.")
    idcards_card_badge = line("Coming soon", 40)

    captions_title = line("Title Workspace")

    # The guidelines popup: shown once per session when a teacher opens the
    # title workspace, and again from the link beside the status tag in the
    # title editor. Placeholder wording until the real guidelines are written.
    guidelines_title = line("Title Guidelines")
    guidelines_intro = para(
        "Titles travel with every photo we deliver, so a little care here saves a round of corrections "
        "later. Please read these before you write or approve a title."
    )
    guidelines_points = para(
        "Write one clear sentence per photo: who is in it, what is happening, and where or when.\n"
        "Use full names and correct titles for staff and guests, exactly as the institution spells them.\n"
        "Check spellings of student names against the class register before approving.\n"
        "Keep to plain, present-tense language; avoid slang and abbreviations.\n"
        "If a title is wrong, write the corrected title in its place.",
        help_text="One pointer per line.",
    )
    guidelines_outro = para("Approved titles are locked, so take a moment before you approve.")
    guidelines_prompt = line("Please follow the guidelines", 80, help_text="Shown beside the status tag in the editor.")
    guidelines_link = line("View guidelines", 60)
    guidelines_dismiss = line("Got it", 40)
    captions_empty_all = line("No images yet.")
    captions_empty_pending = line("Nothing pending — all caught up.")
    captions_empty_submitted = line("Nothing submitted yet.")
    captions_empty_approved = line("No approved images yet.")
    locked_title = line("Locked", 40)
    locked_body = line("This title has been submitted and locked. Only the Spectrum team can change it now.")

    classes_subtitle = line("{count} classes · tap a class to name its students.")
    roster_title = line("{class} — Name the Students")
    student_placeholder = line("Add student's name…", 60)

    class Meta:
        verbose_name = "institution portal page"
        verbose_name_plural = "institution portal pages"
