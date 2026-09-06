/**
 * Hardcoded roster for the single-institution demo (Delhi Public School).
 * Shape is deliberately `class -> [{ id, photo, name }]` so a real storage
 * layer can be swapped in later without a rebuild.
 */

export type SchoolClass = {
  id: string;
  name: string;
  group: "Primary" | "Middle" | "Senior";
  size: number;
};

export const classGroups = ["All", "Primary", "Middle", "Senior"] as const;
export type ClassGroup = (typeof classGroups)[number];

const GRADES: [string, "Primary" | "Middle" | "Senior", string[]][] = [
  ["Nursery", "Primary", [""]],
  ["LKG", "Primary", [""]],
  ["UKG", "Primary", [""]],
  ["1", "Primary", ["A", "B", "C"]],
  ["2", "Primary", ["A", "B", "C"]],
  ["3", "Primary", ["A", "B"]],
  ["4", "Primary", ["A", "B"]],
  ["5", "Primary", ["A", "B"]],
  ["6", "Middle", ["A", "B", "C"]],
  ["7", "Middle", ["A", "B"]],
  ["8", "Middle", ["A", "B"]],
  ["9", "Senior", ["A", "B"]],
  ["10", "Senior", ["A", "B"]],
  ["11", "Senior", ["A", "B"]],
  ["12", "Senior", ["A", "B"]],
];

export const classes: SchoolClass[] = GRADES.flatMap(([grade, group, sections]) =>
  sections.map((s, i) => {
    const name = `${grade}${s}`;
    // Deterministic, realistic-looking strength between 28 and 36.
    const size = 28 + ((grade.length + s.charCodeAt(0) + i * 3) % 9);
    return { id: name.toLowerCase(), name, group, size };
  }),
);

export type Student = { id: string; photo: string; name: string };

/** Passport-style placeholder headshot, rendered as an inline SVG data URI. */
export function avatar(seed: number): string {
  const hue = (seed * 47) % 360;
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="300" height="400" viewBox="0 0 300 400">
<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
<stop offset="0" stop-color="hsl(${hue},32%,74%)"/><stop offset="1" stop-color="hsl(${(hue + 40) % 360},28%,56%)"/>
</linearGradient></defs>
<rect width="300" height="400" fill="url(#g)"/>
<circle cx="150" cy="152" r="66" fill="rgba(255,255,255,0.92)"/>
<path d="M150 236c-62 0-104 40-112 96h224c-8-56-50-96-112-96z" fill="rgba(255,255,255,0.92)"/>
</svg>`;
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
}

export function studentsOf(classId: string): Student[] {
  const cls = classes.find((c) => c.id === classId);
  if (!cls) return [];
  return Array.from({ length: cls.size }, (_, i) => ({
    id: `${cls.id}-${i + 1}`,
    photo: avatar(cls.name.charCodeAt(0) + i * 7 + cls.size),
    name: "",
  }));
}

export const totalStudents = classes.reduce((n, c) => n + c.size, 0);

/** A couple of classes come part-named so progress badges have something to show. */
export const seedNames: Record<string, string> = {
  "6c-1": "Aarav Sharma",
  "6c-2": "Diya Menon",
  "6c-3": "Kabir Nair",
  "1a-1": "Ishaan Gupta",
  "1a-2": "Anaya Rao",
};

export const findClass = (id: string): SchoolClass | undefined =>
  classes.find((c) => c.id === id);
