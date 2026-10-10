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
  searchPlaceholder: "Click here to browse institutions…",
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
  tickerHeading: "Our [Story]",
  tickerText: [
    "In 1980, a single camera and a belief: every institution's moments deserve to be kept beautifully.",
    "We began in the darkrooms of Delhi, printing school annual days frame by frame.",
    "Film gave way to digital; our standards never did.",
    "Four decades on, the same families recognise us at the school gate.",
    "Every event we cover is edited, curated and delivered entirely in-house.",
    "Because a photograph is not a file — it is the day itself, kept safe.",
    "Spectrum — imagination that works, since 1980.",
  ].join("\n"),
  tieupsHeading: "Our Tie-Ups",
  tieupsSubtitle: "Decades-long relationships with the institutions we're proud to call partners.",
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
  browseTitle: "Choose Your [Institution]",
  browseSubtitle: "Pick your school or college to see every event we've covered there.",
  browseEventsTemplate: "{count} events",
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
  filterPhotos: "Photos",
  filterVideos: "Videos",
  bundleSelected: "Full album selected · {photos} photos · ₹{price}",
  bundleButton: "Full Album Bundle — Save {savings}% · ₹{price} for all {photos} photos",
  bundleButtonNoSaving: "Full Album Bundle — ₹{price} for all {photos} photos",
  payCta: "Pay & Get Photos →",
  summaryHeading: "Order Summary",
  bundleLine: "Full Album Bundle — all {photos} photos",
  totalLabel: "Total",
  namePlaceholder: "Your Name",
  whatsappPlaceholder: "WhatsApp Number",
  whatsappHint: "Add, if you want photographs on WhatsApp",
  emailPlaceholder: "Email Address",
  emailHint: "Add, if you want photographs on email",
  contactRequired: "Add a WhatsApp number or email address so we can deliver your memories.",
  payButton: "Pay ₹{total} with Razorpay →",
  checkoutError: "Payment could not be completed. Please try again.",
  successTitle: "Your Memories Are On Their Way.",
  successBodyWhatsapp:
    "We're sending your full-resolution photos to your WhatsApp right now. Check your messages in a while.",
  successBodyEmail:
    "We're sending your full-resolution photos to your email right now. Check your inbox in a while.",
  successNote: "Didn't receive? Contact us at support@spectrum.in",
  successBack: "Back to Events",
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
  eventsCardTitle: "Class Photographs",
  eventsCardCopy: "Review and correct photo titles for event moments.",
  studentsCardTitle: "Individual Photographs",
  studentsCardCopy: "Identify students in class photos and export a labeled roster.",
  idcardsCardTitle: "ID Cards",
  idcardsCardCopy: "Design, proof and order student ID cards from the class photos.",
  idcardsCardBadge: "Coming soon",
  captionsTitle: "Title Workspace",
  guidelinesTitle: "Title Guidelines",
  guidelinesIntro:
    "Titles travel with every photo we deliver, so a little care here saves a round of corrections later. Please read these before you write or approve a title.",
  guidelinesPoints: [
    "Write one clear sentence per photo: who is in it, what is happening, and where or when.",
    "Use full names and correct titles for staff and guests, exactly as the institution spells them.",
    "Check spellings of student names against the class register before approving.",
    "Keep to plain, present-tense language; avoid slang and abbreviations.",
    "If a title is wrong, write the corrected title in its place.",
  ].join("\n"),
  guidelinesOutro: "Approved titles are locked, so take a moment before you approve.",
  guidelinesPrompt: "Please follow the guidelines",
  guidelinesLink: "View guidelines",
  guidelinesDismiss: "Got it",
  captionsEmptyAll: "No images yet.",
  captionsEmptyPending: "Nothing pending — all caught up.",
  captionsEmptySubmitted: "Nothing submitted yet.",
  captionsEmptyApproved: "No approved images yet.",
  lockedTitle: "Locked",
  lockedBody: "This title has been submitted and locked. Only the Spectrum team can change it now.",
  classesSubtitle: "{count} classes · tap a class to name its students.",
  rosterTitle: "{class} — Name the Students",
  studentPlaceholder: "Add student's name…",
};

export type SiteCopy = typeof siteCopy;
export type HomeCopy = typeof homeCopy;
export type AboutCopy = typeof aboutCopy;
export type ContactCopy = typeof contactCopy;
export type EventsCopy = typeof eventsCopy;
export type GalleryCopy = typeof galleryCopy;
export type PortalCopy = typeof portalCopy;
