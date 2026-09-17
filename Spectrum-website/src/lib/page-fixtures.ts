/**
 * Hardcoded page content, kept as the offline fallback and as the seed source for
 * the backend (`bun scripts/export-fixtures.ts`). When VITE_API_URL is set, the
 * site reads the same shapes from the API instead.
 */
import { IMG, pick } from "./spectrum-data";

export type ContactIcon = "mail" | "phone" | "whatsapp" | "map" | "clock";

export const stats = [
  { to: 12000, suffix: "+", label: "Events Captured" },
  { to: 48, suffix: "", label: "Schools & Colleges" },
  { to: 240000, suffix: "+", label: "Photos Delivered" },
];

export const capabilities = [
  "Photography",
  "Mediagraphy",
  "Videography",
  "Cinematography",
  "Graphic Design",
  "Promotional Films",
  "Media Services",
  "ID Card Production",
];

/**
 * Placeholder imagery, each verified by eye rather than by search term, and
 * chosen dark: on this canvas a white-backed photo is the brightest thing on
 * the page and pulls the eye off the copy.
 */
export const story = [
  {
    title: "Our Evolution",
    body: "From black-and-white to colour film, and now advanced digital imaging — we've embraced every evolution in photography while staying true to its fundamentals: experience, precision, creativity, and attention to detail.",
    image: IMG("1516724562728-afc824a36e84", 900, 680),
    alt: "A classic compact camera lit in magenta and teal against black",
  },
  {
    title: "Institutional Expertise",
    body: "Having worked extensively with the top schools, colleges, and educational institutions across the NCR, we stand among the most experienced and dependable names in institutional photography.",
    image: IMG(pick(10), 900, 680),
    alt: "A crowd under confetti at a school annual-day finale",
  },
  {
    title: "Complete In-House Craft",
    body: "Our production facility at Saket uses the finest photo printing and binding equipment from Fuji and Noritsu, Japan. Every step — photographing, designing, printing, and binding — is handled in-house, with no outsourcing, so we can guarantee your timelines, your quality, and the complete privacy of your data.",
    image: IMG("1500051638674-ff996a0ec29e", 900, 680),
    alt: "Film rolls and printed photographs pinned on a board",
  },
];

/** One generic campus image per card, rotated so no frame of three repeats. */
const CAMPUS = [
  IMG("1562774053-701939374585", 400, 400),
  IMG("1427504494785-3a9ca7044f45", 400, 400),
  IMG("1509062522246-3755977927d7", 400, 400),
];

export const tieUps = [
  { name: "Amity Group of Institutions", years: "30+" },
  { name: "K.R. Mangalam Group of Institutions", years: "20+" },
  { name: "St. Andrews Group of Schools", years: "4+" },
  { name: "DPS International – Gurugram", years: "3+" },
  { name: "Bal Bharati Public School – Noida", years: "15+" },
  { name: "G.D. Goenka Public School – Gurugram", years: "15+" },
  { name: "G.D. Goenka Global School – Noida", years: "3+" },
  { name: "ASN Sr. Secondary School – New Delhi", years: "15+" },
  { name: "Colonel's Central Academy – Gurugram", years: "15+" },
  { name: "Mount Olympus School – Gurugram", years: "7+" },
  { name: "GBN Sr. Sec. School – Faridabad", years: "15+" },
  { name: "Universal Public School – New Delhi", years: "15+" },
  { name: "Balwant Rai Mehta School – New Delhi", years: "10+" },
].map((t, i) => ({ ...t, image: CAMPUS[i % CAMPUS.length]! }));

export const faqs = [
  {
    q: "How soon are photos available after the event?",
    a: "Your private gallery goes live within 48 hours of the event wrapping. Large multi-day fests can take up to 72 hours for the full set.",
  },
  {
    q: "How are the final files delivered?",
    a: "Instantly after checkout, over WhatsApp or email — whichever you choose. You receive full-resolution JPEGs with no watermark and no expiry on the link.",
  },
  {
    q: "What does it cost?",
    a: "Individual photos start at ₹29 each. The full album bundle for an event is ₹299 — usually the better value once you want more than ten photos.",
  },
  {
    q: "Can our institution book a coverage date?",
    a: "Yes. Reach out through the contact page with your event date and venue, and we'll confirm a crew and a coverage plan.",
  },
];

export const contactDetails: { icon: ContactIcon; label: string; value: string }[] = [
  { icon: "mail", label: "Email", value: "support@spectrum.in" },
  { icon: "phone", label: "Phone / WhatsApp", value: "+91 98100 44120" },
  { icon: "map", label: "Studio", value: "2nd Floor, Hauz Khas Village, New Delhi 110016" },
];
