import { moments, type Moment } from "./spectrum-data";

export type CaptionStatus =
  | "needs-caption"
  | "needs-approval"
  | "needs-correction"
  | "final-approval"
  | "approved"
  | "corrected";

/**
 * The states Spectrum can put an item into. `approved`/`corrected` are outcomes
 * the institution produces, so they are never a request.
 */
export type CaptionRequest = Exclude<CaptionStatus, "approved" | "corrected">;

export type CaptionItem = {
  id: string;
  momentTitle: string;
  image: string;
  /** Empty for `needs-caption` items — the institution has yet to write one. */
  caption: string;
  /** What Spectrum originally asked the institution to do. */
  requested: CaptionRequest;
  status: CaptionStatus;
  updatedAt: string;
  actionBy?: string;
};

export const captionStatusLabel: Record<CaptionStatus, string> = {
  "needs-caption": "Needs Caption",
  "needs-approval": "Needs Approval",
  "needs-correction": "Needs Correction",
  "final-approval": "Final Approval",
  approved: "Approved",
  corrected: "Corrected",
};

/** Demo institution for this build — Delhi Public School, New Delhi. */
export const portalInstitution = {
  id: "dps",
  name: "Delhi Public School",
  city: "New Delhi",
  event: "Annual Day 2025",
};

const img = (title: string): string =>
  (moments.find((m: Moment) => m.title === title)?.image ?? moments[0]!.image);

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
    caption:
      "Principal Mrs. Sharma presents the Excellence Award to Class XII topper.",
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
    requested: "final-approval",
    status: "final-approval",
    updatedAt: "March 22, 2025",
  },
  {
    id: "c-12",
    momentTitle: "Group Photo — Students",
    image: img("Group Photo — Students"),
    caption: "Class XII students gather on stage after the closing performance.",
    requested: "final-approval",
    status: "final-approval",
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
