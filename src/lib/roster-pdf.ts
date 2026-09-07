import type { jsPDF as JsPdf } from "jspdf";
import { portalInstitution, todayLabel } from "./caption-data";
import { classLabel, type SchoolClass, type Student } from "./student-data";

/**
 * Builds the class roster PDF directly with jsPDF's drawing API rather than
 * screenshotting the DOM with html2canvas. That keeps the text as real,
 * selectable vectors, gives proper multi-page pagination instead of one tall
 * raster sliced up, produces a far smaller file, and avoids html2canvas's
 * well-known trouble with the backdrop-filter / blend-mode CSS this site uses.
 * The headshots are SVG data URIs, which jsPDF cannot embed, so they are
 * rasterised through a canvas first.
 *
 * Client-only by construction: it touches `Image`, `document` and `jspdf`, so
 * it must only ever be called from an event handler, never during render.
 */

type Rgb = [number, number, number];
const BAND: Rgb = [34, 31, 41]; // #221F29 — the site base, carries the light logo
const INK: Rgb = [28, 26, 34]; // #1C1A22 — body text on paper
const MUTED: Rgb = [150, 148, 158];
const ON_BAND_MUTED: Rgb = [196, 192, 204];
/** The Spectrum gradient stops, drawn as a thin strip under the header band. */
const SPECTRUM: Rgb[] = [
  [255, 201, 60],
  [255, 138, 61],
  [232, 80, 58],
  [214, 51, 154],
  [124, 77, 224],
  [47, 191, 143],
];

const PAGE = { w: 210, h: 297 }; // A4 portrait, mm
const MARGIN = 14;
const COLS = 5;
const GAP = 5;
const FIRST_BAND = 30;
const LATER_BAND = 16;
const FOOTER = 10;

export function rosterFilename(cls: SchoolClass): string {
  const code = portalInstitution.name
    .split(/\s+/)
    .map((w) => w[0])
    .join("")
    .toUpperCase(); // Delhi Public School -> DPS
  return `${code}-${cls.name.toUpperCase()}-Roster.pdf`;
}

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error(`image failed to load: ${src.slice(0, 48)}`));
    img.src = src;
  });
}

async function rasterise(
  src: string,
  w: number,
  h: number,
  type: "image/jpeg" | "image/png",
  quality?: number,
): Promise<string> {
  const img = await loadImage(src);
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  canvas.getContext("2d")!.drawImage(img, 0, 0, w, h);
  return canvas.toDataURL(type, quality);
}

/** Shrink to fit, then truncate with an ellipsis if even the floor size overflows. */
function fitName(doc: JsPdf, text: string, maxW: number): string {
  let pt = 8.5;
  doc.setFontSize(pt);
  while (doc.getTextWidth(text) > maxW && pt > 6.5) {
    pt -= 0.5;
    doc.setFontSize(pt);
  }
  if (doc.getTextWidth(text) <= maxW) return text;
  let cut = text;
  while (cut.length > 1 && doc.getTextWidth(`${cut}…`) > maxW) cut = cut.slice(0, -1);
  return `${cut}…`;
}

export async function exportRosterPdf(
  cls: SchoolClass,
  students: Student[],
  names: Record<string, string>,
): Promise<void> {
  // Dynamic import keeps jspdf off the SSR path and out of the initial bundle —
  // it is only ever needed once someone clicks Download.
  const { jsPDF } = await import("jspdf");
  const doc = new jsPDF({ unit: "mm", format: "a4" });
  doc.setProperties({
    title: `${portalInstitution.name} — ${classLabel(cls)} Roster`,
    subject: "Student roster",
    creator: "Spectrum",
  });

  // Assets. A failed image degrades to a grey placeholder rather than aborting
  // the whole export.
  const [logo, ...photos] = await Promise.all([
    rasterise("/spectrum-logo-light.png", 640, 200, "image/png").catch(() => null),
    ...students.map((s) => rasterise(s.photo, 180, 240, "image/jpeg", 0.82).catch(() => null)),
  ]);

  const contentW = PAGE.w - MARGIN * 2;
  const cardW = (contentW - GAP * (COLS - 1)) / COLS;
  const photoH = (cardW * 4) / 3;
  const nameH = 9;
  const rowStep = photoH + nameH + GAP;

  const rowsFor = (band: number) =>
    Math.max(1, Math.floor((PAGE.h - band - MARGIN - FOOTER) / rowStep));
  const firstCap = rowsFor(FIRST_BAND) * COLS;
  const laterCap = rowsFor(LATER_BAND) * COLS;

  // Pagination: the first page carries the full header, so it fits fewer rows.
  const pages: number[][] = [];
  let cursor = 0;
  do {
    const cap = pages.length === 0 ? firstCap : laterCap;
    const n = Math.min(cap, students.length - cursor);
    pages.push(Array.from({ length: n }, (_, k) => cursor + k));
    cursor += cap;
  } while (cursor < students.length);

  const drawBand = (h: number) => {
    doc.setFillColor(...BAND);
    doc.rect(0, 0, PAGE.w, h, "F");
    const seg = PAGE.w / SPECTRUM.length;
    SPECTRUM.forEach((c, k) => {
      doc.setFillColor(...c);
      doc.rect(k * seg, h - 1.2, seg + 0.3, 1.2, "F"); // slight overlap hides hairline seams
    });
  };

  pages.forEach((indices, p) => {
    if (p > 0) doc.addPage();
    const band = p === 0 ? FIRST_BAND : LATER_BAND;
    drawBand(band);

    if (p === 0) {
      if (logo) doc.addImage(logo, "PNG", MARGIN, 8.5, 32, 10);
      doc.setTextColor(255, 255, 255);
      doc.setFont("helvetica", "bold");
      doc.setFontSize(13);
      doc.text(portalInstitution.name, PAGE.w - MARGIN, 11.5, { align: "right" });
      doc.setFont("helvetica", "normal");
      doc.setFontSize(9.5);
      doc.text(`${classLabel(cls)} · Student Roster`, PAGE.w - MARGIN, 17.5, { align: "right" });
      doc.setTextColor(...ON_BAND_MUTED);
      doc.setFontSize(8);
      doc.text(`Exported ${todayLabel()}`, PAGE.w - MARGIN, 23, { align: "right" });
    } else {
      if (logo) doc.addImage(logo, "PNG", MARGIN, 4, 22.4, 7);
      doc.setTextColor(255, 255, 255);
      doc.setFont("helvetica", "normal");
      doc.setFontSize(9);
      doc.text(`${portalInstitution.name} · ${classLabel(cls)}`, PAGE.w - MARGIN, 9.6, {
        align: "right",
      });
    }

    const top = band + 8;
    indices.forEach((idx, pos) => {
      const s = students[idx]!;
      const col = pos % COLS;
      const row = Math.floor(pos / COLS);
      const x = MARGIN + col * (cardW + GAP);
      const y = top + row * rowStep;

      const photo = photos[idx];
      if (photo) {
        doc.addImage(photo, "JPEG", x, y, cardW, photoH);
      } else {
        doc.setFillColor(228, 226, 232);
        doc.rect(x, y, cardW, photoH, "F");
      }
      doc.setDrawColor(205, 203, 210);
      doc.setLineWidth(0.2);
      doc.rect(x, y, cardW, photoH);

      const name = (names[s.id] ?? "").trim();
      const baseline = y + photoH + 5.2;
      if (name) {
        doc.setTextColor(...INK);
        doc.setFont("helvetica", "normal");
        const label = fitName(doc, name, cardW - 2);
        doc.text(label, x + cardW / 2, baseline, { align: "center" });
      } else {
        // Unnamed: a dashed line where the name would go, so it can be filled in by hand.
        doc.setDrawColor(...MUTED);
        doc.setLineWidth(0.3);
        doc.setLineDashPattern([1, 1], 0);
        doc.line(x + 3, baseline, x + cardW - 3, baseline);
        doc.setLineDashPattern([], 0);
      }
    });

    doc.setTextColor(...MUTED);
    doc.setFont("helvetica", "normal");
    doc.setFontSize(7.5);
    doc.text(`Page ${p + 1} of ${pages.length}`, PAGE.w / 2, PAGE.h - 6, { align: "center" });
    doc.text("Spectrum · Imagination That Works", MARGIN, PAGE.h - 6);
  });

  doc.save(rosterFilename(cls));
}
