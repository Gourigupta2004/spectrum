import { galleryPhotos, type Photo } from "./spectrum-data";

export type CaptionStatus =
  "needs-caption" | "needs-approval" | "needs-correction" | "approved" | "corrected";

/**
 * The states Spectrum can put an item into. `approved`/`corrected` are outcomes
 * the institution produces, so they are never a request.
 */
export type CaptionRequest = Exclude<CaptionStatus, "approved" | "corrected">;

export type CaptionItem = {
  id: string;
  momentTitle: string;
  image: string;
  /** Pixel size of the uploaded photo; the card takes its proportions from it. */
  width?: number | null;
  height?: number | null;
  /** Empty for `needs-caption` items — the institution has yet to write one. */
  caption: string;
  /**
   * The institution's correction note. Kept apart from `caption` so the
   * original wording is never overwritten; Spectrum applies it on their side.
   */
  correction?: string;
  /** What Spectrum originally asked the institution to do. */
  requested: CaptionRequest;
  status: CaptionStatus;
  updatedAt: string;
  actionBy?: string;
  /** The mobile number given alongside the name when the action was taken. */
  actionByPhone?: string;
};

/** On-screen wording says "title"; the status values underneath are unchanged. */
export const captionStatusLabel: Record<CaptionStatus, string> = {
  "needs-caption": "Needs Title",
  "needs-approval": "Needs Approval",
  "needs-correction": "Needs Correction",
  approved: "Approved",
  corrected: "Corrected",
};

/**
 * Who is signed in. The backend will supply this; for the demo the portal is
 * the institution's view, so Spectrum-only tools (uploading and replacing
 * photos) stay hidden. Flip to "spectrum" to see them.
 */
export const portalRole: "institution" | "spectrum" = "institution";

/** Statuses where the next move is the institution's, not Spectrum's. */
export const awaitingInstitution: ReadonlySet<CaptionStatus> = new Set([
  "needs-caption",
  "needs-approval",
  "needs-correction",
]);

export const pluralImages = (n: number): string => `${n} ${n === 1 ? "image" : "images"}`;

/**
 * Workspace display order: by the photo's name (taken from its file name at
 * upload), alphabetically and numerically — "IMG_2" sorts before "IMG_10".
 * The backend lists items in the same order, so the admin table and the
 * website always agree.
 */
export const byMomentTitle = (a: CaptionItem, b: CaptionItem): number =>
  a.momentTitle.localeCompare(b.momentTitle, undefined, { numeric: true, sensitivity: "base" }) ||
  a.id.localeCompare(b.id, undefined, { numeric: true });

/** Demo institution for this build — Delhi Public School, New Delhi. */
export const portalInstitution = {
  id: "dps",
  name: "Delhi Public School",
  city: "New Delhi",
  event: "Annual Day 2025",
};

const img = (title: string): string =>
  galleryPhotos.find((m: Photo) => m.title === title)?.image ?? galleryPhotos[0]!.image;

export const captionItems: CaptionItem[] = [
  {
    id: "c-1",
    momentTitle: "Lighting the Lamp",
    image: img("Lighting the Lamp"),
    caption: "Chief guest lights the ceremonial lamp to open Annual Day 2025.",
    requested: "needs-approval",
    status: "needs-approval",
    updatedAt: "March 18, 2025",
  },
  {
    id: "c-2",
    momentTitle: "Chief Guest Speech",
    image: img("Chief Guest Speech"),
    caption: "Our chief guest addressing the gathering.",
    requested: "needs-correction",
    status: "needs-correction",
    updatedAt: "March 18, 2025",
  },
  {
    id: "c-3",
    momentTitle: "Solo Dance Performance",
    image: img("Solo Dance Performance"),
    caption: "A student performs a classical solo dance.",
    requested: "needs-approval",
    status: "needs-approval",
    updatedAt: "March 19, 2025",
  },
  {
    id: "c-4",
    momentTitle: "Award Distribution",
    image: img("Award Distribution"),
    caption: "Principal Mrs. Sharma presents the Excellence Award to Class XII topper.",
    requested: "needs-correction",
    status: "corrected",
    updatedAt: "March 21, 2025",
    actionBy: "R. Menon",
  },
  {
    id: "c-5",
    momentTitle: "Group Photo — Faculty",
    image: img("Group Photo — Faculty"),
    caption: "Faculty group photo, Annual Day 2025.",
    requested: "needs-approval",
    status: "approved",
    updatedAt: "March 20, 2025",
    actionBy: "A. Kapoor",
  },
  {
    id: "c-6",
    momentTitle: "Drama / Skit",
    image: img("Drama / Skit"),
    caption: "Students perform a short skit.",
    requested: "needs-correction",
    status: "needs-correction",
    updatedAt: "March 19, 2025",
  },
  {
    id: "c-7",
    momentTitle: "Musical Segment",
    image: img("Musical Segment"),
    caption: "School choir performs during the event.",
    requested: "needs-approval",
    status: "approved",
    updatedAt: "March 20, 2025",
    actionBy: "A. Kapoor",
  },
  {
    id: "c-9",
    momentTitle: "Finale & Confetti",
    image: img("Finale & Confetti"),
    caption: "",
    requested: "needs-caption",
    status: "needs-caption",
    updatedAt: "March 22, 2025",
  },
  {
    id: "c-10",
    momentTitle: "Backstage Candids",
    image: img("Backstage Candids"),
    caption: "",
    requested: "needs-caption",
    status: "needs-caption",
    updatedAt: "March 22, 2025",
  },
  {
    id: "c-11",
    momentTitle: "Prize Distribution",
    image: img("Prize Distribution"),
    caption: "Head Girl receives the Best Performer trophy at Annual Day 2025.",
    requested: "needs-approval",
    status: "needs-approval",
    updatedAt: "March 22, 2025",
  },
  {
    id: "c-12",
    momentTitle: "Group Photo — Students",
    image: img("Group Photo — Students"),
    caption: "Class XII students gather on stage after the closing performance.",
    requested: "needs-approval",
    status: "needs-approval",
    updatedAt: "March 22, 2025",
  },
  {
    id: "c-8",
    momentTitle: "Closing Ceremony",
    image: img("Closing Ceremony"),
    caption: "Vote of thanks and closing remarks.",
    requested: "needs-approval",
    status: "needs-approval",
    updatedAt: "March 21, 2025",
  },
];

export const todayLabel = (): string =>
  new Date().toLocaleDateString("en-IN", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
