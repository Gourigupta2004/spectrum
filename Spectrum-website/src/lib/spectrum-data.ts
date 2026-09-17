export const IMG = (id: string, w = 900, h = 1200) =>
  `https://images.unsplash.com/photo-${id}?auto=format&fit=crop&w=${w}&h=${h}&q=80`;

const POOL = [
  "1541339907198-e08756dedf3f",
  "1524178232363-1fb2b075b655",
  "1509062522246-3755977927d7",
  "1546519638-68e109498ffc",
  "1461896836934-ffe607ba8211",
  "1470229722913-7c0e2dbbafd3",
  "1492684223066-81342ee5ff30",
  "1531058020387-3be344556be6",
  "1540575467063-178a50c2df87",
  "1511578314322-379afb476865",
  "1505236858219-8359eb29e329",
  "1571260899304-425eee4c7efc",
  "1544928147-79a2dbc1f389",
  "1552674605-db6ffd4facb5",
  "1519671482749-fd09be7ccebf",
  "1508997449629-303059a039c0",
  "1517486808906-6ca8b3f04846",
  "1567168544813-cc03465b4fa8",
];

export const pick = (i: number): string => POOL[i % POOL.length] as string;

export type Institution = {
  id: string;
  name: string;
  short: string;
  city: string;
  image: string;
  type: "school" | "college";
  /** Supplied by the API (and derived in demo mode) for the homepage click-through. */
  eventCount?: number;
  firstEventSlug?: string | null;
};

export const institutions: Institution[] = [
  {
    id: "dps",
    name: "Delhi Public School",
    short: "Delhi Public School",
    city: "New Delhi",
    image: IMG(pick(1), 500, 500),
    type: "school",
  },
  {
    id: "xaviers",
    name: "St. Xavier's College",
    short: "St. Xavier's",
    city: "Mumbai",
    image: IMG(pick(0), 500, 500),
    type: "college",
  },
  {
    id: "ryan",
    name: "Ryan International School",
    short: "Ryan International",
    city: "Bengaluru",
    image: IMG(pick(2), 500, 500),
    type: "school",
  },
  {
    id: "amity",
    name: "Amity University",
    short: "Amity",
    city: "Noida",
    image: IMG(pick(8), 500, 500),
    type: "college",
  },
  {
    id: "doon",
    name: "The Doon School",
    short: "The Doon School",
    city: "Dehradun",
    image: IMG(pick(16), 500, 500),
    type: "school",
  },
];

export type SpectrumEvent = {
  slug: string;
  name: string;
  institutionId: string;
  institution: string;
  date: string;
  photos: number;
  pricePerPhoto: number;
  image: string;
  tags: ("recent" | "popular")[];
  institutionType?: "school" | "college";
};

/**
 * The gallery is every photo from the event, one tile each — not "moments"
 * that stand in for a bundle of shots. Priced per photo; the album bundle is a
 * flat price for all of them.
 */
export type Photo = {
  id: string;
  title: string;
  image: string;
  thumb?: string;
  /** Pixel size of the uploaded photo, so the gallery can show it at its own proportions. */
  width?: number | null;
  height?: number | null;
};

const GALLERY: string[] = [
  "Welcome & Opening Address",
  "Lighting the Lamp",
  "Chief Guest Speech",
  "Solo Dance Performance",
  "Group Dance Performance",
  "Musical Segment",
  "Drama / Skit",
  "Fashion Show Walk",
  "Award Distribution",
  "Prize Distribution",
  "Backstage Candids",
  "Audience & Crowd Shots",
  "Group Photo — Faculty",
  "Group Photo — Students",
  "Vote of Thanks",
  "Closing Ceremony",
  "Finale & Confetti",
  "Campus & Decor Shots",
];

export const galleryPhotos: Photo[] = GALLERY.map((title, i) => ({
  id: `p-${i}`,
  title,
  image: IMG(pick(i + 3), 800, 1000),
}));

export const events: SpectrumEvent[] = [
  {
    slug: "annual-day-2025-dps",
    name: "Annual Day 2025",
    institutionId: "dps",
    institution: "Delhi Public School",
    date: "March 15, 2025",
    photos: galleryPhotos.length, // the gallery is the source of truth for this event
    pricePerPhoto: 29,
    image: IMG(pick(4)),
    tags: ["recent", "popular"],
  },
  {
    slug: "graduation-ceremony-2025-xaviers",
    name: "Graduation Ceremony 2025",
    institutionId: "xaviers",
    institution: "St. Xavier's College",
    date: "April 3, 2025",
    photos: 94,
    pricePerPhoto: 49,
    image: IMG(pick(11)),
    tags: ["recent"],
  },
  {
    slug: "sports-meet-2025-ryan",
    name: "Sports Meet 2025",
    institutionId: "ryan",
    institution: "Ryan International School",
    date: "February 20, 2025",
    photos: 210,
    pricePerPhoto: 29,
    image: IMG(pick(13)),
    tags: ["popular"],
  },
  {
    slug: "republic-day-2025-ryan",
    name: "Republic Day Celebration 2025",
    institutionId: "ryan",
    institution: "Ryan International School",
    date: "January 26, 2025",
    photos: 76,
    pricePerPhoto: 29,
    image: IMG(pick(9)),
    tags: ["recent"],
  },
  {
    slug: "cultural-fest-rang-2025-amity",
    name: 'Cultural Fest "Rang" 2025',
    institutionId: "amity",
    institution: "Amity University",
    date: "January 18, 2025",
    photos: 340,
    pricePerPhoto: 29,
    image: IMG(pick(5)),
    tags: ["popular"],
  },
  {
    slug: "founders-day-2025-doon",
    name: "Founder's Day 2025",
    institutionId: "doon",
    institution: "The Doon School",
    date: "December 10, 2024",
    photos: 128,
    pricePerPhoto: 49,
    image: IMG(pick(15)),
    tags: [],
  },
];

export const eventsByInstitution = (id: string) => events.filter((e) => e.institutionId === id);

export const galleryEvent = events[0] as SpectrumEvent;
export const BUNDLE_PRICE = 299;
/** Bundle saving against buying every photo singly; 0 when the bundle is not cheaper. */
export const bundleSavings = Math.max(
  0,
  Math.round((1 - BUNDLE_PRICE / (galleryEvent.photos * galleryEvent.pricePerPhoto)) * 100),
);

export const heroSlides = [4, 5, 11, 13, 6, 9, 15, 3].map((i, k) => ({
  id: k,
  src: IMG(pick(i), 900, 1150),
  caption: [
    "Annual Day 2025",
    "Cultural Fest Rang",
    "Graduation Ceremony",
    "Sports Meet",
    "Stage Performance",
    "Republic Day",
    "Founder's Day",
    "Classroom Candids",
  ][k],
}));

export const services = [
  "Annual class pictures",
  "Student portraits",
  "School annual days",
  "Annual sports events",
  "Conferences and seminars",
  "Award ceremonies",
  "Cultural programmes",
  "Corporate and institutional events",
  "Campus virtual tours",
];
