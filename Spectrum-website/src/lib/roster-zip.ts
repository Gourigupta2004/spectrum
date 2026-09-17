import { zip, type Zippable } from "fflate";
import type { SchoolClass, Student } from "./student-data";

/**
 * Builds the class "folder" — a zip holding one JPEG per *named* student, each
 * file called after the student — entirely in the browser. Students without a
 * name have nothing to be filed under, so they are left out and counted.
 *
 * The web copies of the photos are WebP (or SVG data URIs in the demo), so each
 * one is redrawn through a canvas and re-encoded as JPEG at its natural size:
 * a folder of .jpg files opens anywhere, which is the point of a folder.
 *
 * Client-only by construction: it touches `Image`, `document` and `Blob`, so it
 * must only ever be called from an event handler, never during render.
 */

export type FolderResult = {
  /** Files written into the folder. */
  included: number;
  /** Students skipped because they have no name. */
  unnamed: number;
  /** Named students whose photo could not be read (blocked by CORS, missing). */
  failed: number;
};

const CONCURRENCY = 4;
const JPEG_QUALITY = 0.92;

function institutionCode(institutionName: string): string {
  return institutionName
    .split(/\s+/)
    .map((w) => w[0])
    .join("")
    .toUpperCase(); // Delhi Public School -> DPS
}

export function rosterFolderName(cls: SchoolClass, institutionName: string): string {
  return `${institutionCode(institutionName)}-${cls.name.toUpperCase()}-Photos`;
}

/** A filename that every OS accepts: no path separators or reserved characters. */
function safeFileName(name: string): string {
  return (
    name
      .trim()
      .replace(/[\\/:*?"<>|]+/g, " ")
      .replace(/\s+/g, " ")
      .replace(/^\.+/, "")
      .slice(0, 100)
      .trim() || "Student"
  );
}

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    // Photos come from the API or S3 on another origin; without CORS the canvas is tainted.
    if (!src.startsWith("data:")) img.crossOrigin = "anonymous";
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error(`image failed to load: ${src.slice(0, 48)}`));
    img.src = src;
  });
}

async function toJpeg(src: string): Promise<Uint8Array> {
  const img = await loadImage(src);
  const canvas = document.createElement("canvas");
  canvas.width = img.naturalWidth || 600;
  canvas.height = img.naturalHeight || 800;
  canvas.getContext("2d")!.drawImage(img, 0, 0, canvas.width, canvas.height);
  const blob = await new Promise<Blob | null>((resolve) =>
    canvas.toBlob(resolve, "image/jpeg", JPEG_QUALITY),
  );
  if (!blob) throw new Error("could not encode image");
  return new Uint8Array(await blob.arrayBuffer());
}

/** Run `fn` over `items`, at most CONCURRENCY at a time; failures resolve to null. */
async function mapLimited<T, R>(items: T[], fn: (item: T) => Promise<R>): Promise<(R | null)[]> {
  const out: (R | null)[] = new Array(items.length).fill(null);
  let next = 0;
  const worker = async () => {
    while (next < items.length) {
      const i = next++;
      out[i] = await fn(items[i]!).catch(() => null);
    }
  };
  await Promise.all(Array.from({ length: Math.min(CONCURRENCY, items.length) }, worker));
  return out;
}

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  // Give the browser a moment to start the download before the URL goes away.
  window.setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

export async function exportRosterFolder(
  cls: SchoolClass,
  students: Student[],
  names: Record<string, string>,
  institutionName: string,
): Promise<FolderResult> {
  const named = students.filter((s) => (names[s.id] ?? "").trim().length > 0);
  const unnamed = students.length - named.length;
  if (named.length === 0) return { included: 0, unnamed, failed: 0 };

  const folder = rosterFolderName(cls, institutionName);
  const photos = await mapLimited(named, (s) => toJpeg(s.photo));

  const files: Zippable = {};
  const used = new Map<string, number>();
  let included = 0;
  named.forEach((s, i) => {
    const bytes = photos[i];
    if (!bytes) return;
    const base = safeFileName(names[s.id]!);
    // Two students with the same name get "Name.jpg" and "Name (2).jpg".
    const n = (used.get(base.toLowerCase()) ?? 0) + 1;
    used.set(base.toLowerCase(), n);
    const file = n === 1 ? `${base}.jpg` : `${base} (${n}).jpg`;
    files[`${folder}/${file}`] = [bytes, { level: 0 }]; // JPEG is already compressed
    included += 1;
  });

  if (included > 0) {
    const archive = await new Promise<Uint8Array>((resolve, reject) =>
      zip(files, { level: 0 }, (err, data) => (err ? reject(err) : resolve(data))),
    );
    saveBlob(new Blob([archive as BlobPart], { type: "application/zip" }), `${folder}.zip`);
  }
  return { included, unnamed, failed: named.length - included };
}
