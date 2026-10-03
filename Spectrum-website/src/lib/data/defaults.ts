/**
 * Page copy used when the site runs without the backend. Keep in step with the
 * field defaults in Spectrum-backend/apps/content/models.py (same text, camelCase keys).
 */
export const siteCopy = {
  introSkipLabel: "Skip",
  navHome: "Home",
  navEvents: "Events",
  navAbout: "About Us",
  navContact: "Contact",
  navPortal: "Institution Portal",
  notFoundTitle: "Page not found",
  notFoundBody: "The page you're looking for doesn't exist or has been moved.",
  notFoundCta: "Go home",
  errorTitle: "This page didn't load",
  errorBody: "Something went wrong on our end. You can try refreshing or head back home.",
  errorRetry: "Try again",
};

export const homeCopy = {
  heroTitle: "Every Moment, [Yours] Forever",
  heroSubtitle:
    "Spectrum captures the moments for institutions. Browse, choose, and own your memories.",
  searchPlaceholder: "Find your school, college, or event…",
  institutionsHeading: "Browse by Institution",
  servicesHeading: "Our Services",
  servicesSubtitle: "We provide professional coverage.",
  featuredHeading: "Recently Captured",
  featuredCta: "View All Events",
};

export const aboutCopy = {
  backLabel: "Home",
  leadLine: "Established in 1980 — Nearly [Five Decades] of Experience, Precision, and Trust.",
  pullQuote:
    "[Technology] has changed. [Photography] has evolved. Our [commitment] to quality remains constant.",
  tieupsHeading: "Our Tie-Ups",
  tieupsSubtitle: "Decades-long relationships with the institutions we're proud to call partners.",
  tieupYearsTemplate: "Tied up for {years} years",
  faqsHeading: "FAQs",
};

export const contactCopy = {
  backLabel: "Home",
  title: "Get In [Touch]",
  subtitle:
    "Planning an annual day, fest or graduation? Tell us the date and we'll take it from there.",
  namePlaceholder: "Your Name",
  emailPlaceholder: "Email Address",
  phonePlaceholder: "Phone Number",
  institutionPlaceholder: "Institution",
  servicePlaceholder: "Services",
  otherServiceOption: "Other",
  otherServicePlaceholder: "Tell us which service you need",
  messagePlaceholder: "Tell us about your event",
  submitLabel: "Send Message",
  successMessage: "Thank you. We'll get back to you within one working day.",
  detailsHeading: "Reach us directly",
  replyNote:
    "We reply to every enquiry within one working day. For an event happening this week, WhatsApp is fastest.",
};

export const eventsCopy = {
  backLabel: "Home",
  title: "All Events",
  filterAll: "All",
  filterRecent: "Recent",
  filterPopular: "Popular",
  emptyState: "No events match this filter.",
  searchPlaceholder: "Search events or institutions…",
  searchEmpty: "Nothing matches “{query}”. Try the institution's name or the event.",
  photosLabel: "photos",
  pricePrefix: "From ₹",
};

export const galleryCopy = {
  seoTitleTemplate: "{event} Gallery — {institution} | Spectrum",
  seoDescriptionTemplate:
    "Browse every photo from {event} at {institution}. Select the ones you love and get full-resolution files instantly.",
  backLabel: "All Events",
  watermarkText: "Preview Only",
  selectLabel: "Select This Photo",
  selectedLabel: "Selected",
  selectionOne: "{count} photo selected · ₹{price}",
  selectionMany: "{count} photos selected · ₹{price}",
  selectionMixed: "{photos} photos + {videos} videos · ₹{price}",
  videosHeading: "Event Videos",
  bundleSelected: "Full album selected · {photos} photos · ₹{price}",
  bundleButton: "Full Album Bundle — Save {savings}% · ₹{price} for all {photos} photos",
  bundleButtonNoSaving: "Full Album Bundle — ₹{price} for all {photos} photos",
  payCta: "Pay & Get Photos →",
  summaryHeading: "Order Summary",
  bundleLine: "Full Album Bundle — all {photos} photos",
  totalLabel: "Total",
  namePlaceholder: "Your Name",
  whatsappPlaceholder: "WhatsApp Number",
  emailPlaceholder: "Email Address",
  deliverVia: "Deliver via {channel}",
  payButton: "Pay ₹{total} with Razorpay →",
  checkoutError: "Payment could not be completed. Please try again.",
  successTitle: "Your Memories Are On Their Way.",
  successBodyWhatsapp:
    "We're sending your full-resolution photos to your WhatsApp right now. Check your messages in a while.",
  successBodyEmail:
    "We're sending your full-resolution photos to your email right now. Check your inbox in a while.",
  successNote: "Didn't receive? Contact us at support@spectrum.in",
  successDownload: "Open your photos now",
  successBack: "Back to Events",
  downloadTitle: "Your photos",
  downloadSubtitle: "{event} · {institution}",
  downloadAll: "Download all (zip)",
  downloadOne: "Download",
  downloadMissing: "This download link is not valid. Contact support@spectrum.in.",
};

export const portalCopy = {
  accessEyebrow: "Institution Access",
  accessTitle: "Enter your institution email",
  accessSubtitle:
    "The workspace is open to institutions Spectrum works with. Use the email address registered with us.",
  accessPlaceholder: "you@yourschool.edu",
  accessButton: "Continue →",
  accessError: "This email doesn't have workspace access yet. Contact support@spectrum.in.",
  accessChange: "Use a different email",
  loginEyebrow: "Institution Login",
  loginSubtitle: "Institution Workspace",
  loginTitle: "Sign in to your workspace",
  loginIdPlaceholder: "Institution ID",
  loginPasswordPlaceholder: "Password",
  loginButton: "Log In →",
  loginError: "That ID or password didn't match.",
  signedInAs: "Signed in as",
  signOut: "Sign Out",
  workspaceTitle: "What would you like to work on?",
  workspaceSubtitle: "One institution account, everything in one place.",
  eventsCardTitle: "Events",
  eventsCardCopy: "Review and correct photo captions for event moments.",
  studentsCardTitle: "Students",
  studentsCardCopy: "Identify students in class photos and export a labeled roster.",
  idcardsCardTitle: "ID Cards",
  idcardsCardCopy: "Design, proof and order student ID cards from the class photos.",
  idcardsCardBadge: "Coming soon",
  captionsTitle: "Caption Workspace",
  guidelinesTitle: "Caption Guidelines",
  guidelinesIntro:
    "Captions travel with every photo we deliver, so a little care here saves a round of corrections later. Please read these before you write or approve a caption.",
  guidelinesPoints: [
    "Write one clear sentence per photo: who is in it, what is happening, and where or when.",
    "Use full names and correct titles for staff and guests, exactly as the institution spells them.",
    "Check spellings of student names against the class register before approving.",
    "Keep to plain, present-tense language; avoid slang and abbreviations.",
    "If a caption is wrong, describe what should change rather than rewriting it from scratch.",
  ].join("\n"),
  guidelinesOutro: "Approved captions are locked, so take a moment before you approve.",
  guidelinesPrompt: "Please follow the guidelines",
  guidelinesLink: "View guidelines",
  guidelinesDismiss: "Got it",
  captionsEmptyAll: "No images yet.",
  captionsEmptyPending: "Nothing pending — all caught up.",
  captionsEmptyApproved: "No approved images yet.",
  lockedTitle: "Locked",
  lockedBody: "This caption is approved and can no longer be edited.",
  classesSubtitle: "{count} classes · tap a class to name its students.",
  rosterTitle: "{class} — Name the Students",
  studentPlaceholder: "Add student's name…",
  downloadPhotos: "Download Class Photos →",
  downloadNote: "Only named students are included — {count} still unnamed.",
  downloadToast: "{count} photos downloaded",
};

export type SiteCopy = typeof siteCopy;
export type HomeCopy = typeof homeCopy;
export type AboutCopy = typeof aboutCopy;
export type ContactCopy = typeof contactCopy;
export type EventsCopy = typeof eventsCopy;
export type GalleryCopy = typeof galleryCopy;
export type PortalCopy = typeof portalCopy;
