import { galleryPhotos, type Photo } from "./spectrum-data";

/**
 * Two rounds. A first upload asks the institution for a title ("needs-caption",
 * shown as Pending); the teacher writes it, reviews it and saves — "corrected",
 * shown as Submitted and locked. Edited photos come back "needs-approval",
 * where the wording can still be adjusted before approving — "approved",
 * locked. (There is no separate correction round any more.)
 */
export type CaptionStatus = "needs-caption" | "needs-approval" | "approved" | "corrected";

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
  /**
   * The photo's title text. Empty for `needs-caption` items — the institution
   * has yet to write one. A correction rewrites this in place, so it is
   * always the current wording.
   */
  caption: string;
  /** What Spectrum originally asked the institution to do. */
  requested: CaptionRequest;
  status: CaptionStatus;
  updatedAt: string;
  actionBy?: string;
  /** The mobile number given alongside the name when the action was taken. */
  actionByPhone?: string;
};

/** On-screen wording; the status values underneath keep their historic names. */
export const captionStatusLabel: Record<CaptionStatus, string> = {
  "needs-caption": "Pending",
  "needs-approval": "For Approval",
  approved: "Approved",
  corrected: "Submitted",
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
]);

export const pluralImages = (n: number): string => `${n} ${n === 1 ? "image" : "images"}`;

/**
 * Workspace display order: by the photo's name (taken from its file name at
 * upload), numerically first and alphabetically second. The first number in
 * the name is the primary key, whatever text surrounds it ("2.jpg" < "DSC_10"
 * < "IMG_11"); names sharing that number — and names with no number at all,
 * which sort after every numbered one — fall back to a natural alphabetical
 * order ("IMG_2" < "IMG_10"). The backend lists items the same way, so the
 * admin table and the website always agree.
 */
const firstNumber = (s: string): number => {
  const match = /\d+/.exec(s);
  return match ? parseInt(match[0], 10) : Infinity;
};
export const byMomentTitle = (a: CaptionItem, b: CaptionItem): number => {
  const na = firstNumber(a.momentTitle);
  const nb = firstNumber(b.momentTitle);
  if (na !== nb) return na < nb ? -1 : 1;
  return (
    a.momentTitle.localeCompare(b.momentTitle, undefined, { numeric: true, sensitivity: "base" }) ||
    a.id.localeCompare(b.id, undefined, { numeric: true })
  );
};

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
    requested: "needs-approval",
    status: "needs-approval",
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
    requested: "needs-caption",
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
    requested: "needs-approval",
    status: "needs-approval",
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
