import { createFileRoute, Link } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { motion } from "motion/react";
import { Check } from "lucide-react";
import { namesStore, useStore } from "@/lib/portal-store";
import { classGroups, classes, type ClassGroup } from "@/lib/student-data";
import { portalInstitution } from "@/lib/caption-data";

export const Route = createFileRoute("/portal/workspace/students/")({
  head: () => ({
    meta: [
      { title: "Classes — Spectrum Student Roster" },
      {
        name: "description",
        content:
          "Pick a class to identify students in their photos and export a labelled roster PDF.",
      },
      { property: "og:title", content: "Classes — Spectrum Student Roster" },
      {
        property: "og:description",
        content: "Name students class by class and export a roster PDF.",
      },
    ],
  }),
  component: ClassList,
});

/**
 * Soft glass tints for the class squares, rotated by position so the grid has
 * colour without any square reading as "selected". Pairs are the brand stops
 * already used across the site; low alpha over the surface tone keeps them
 * glassy rather than filled.
 */
const TINTS: [string, string][] = [
  ["255,201,60", "255,138,61"], // amber -> orange
  ["124,77,224", "214,51,154"], // violet -> magenta
  ["47,191,143", "61,139,255"], // teal -> blue
  ["232,80,58", "214,51,154"], // red -> magenta
  ["61,139,255", "124,77,224"], // blue -> violet
  ["255,138,61", "232,80,58"], // orange -> red
];
const tintFor = (i: number): string => {
  const [a, b] = TINTS[i % TINTS.length]!;
  return [
    `radial-gradient(110% 110% at 22% 18%, rgba(${a},0.36), transparent 62%)`,
    `radial-gradient(110% 110% at 82% 88%, rgba(${b},0.28), transparent 62%)`,
    "rgba(28,26,34,0.72)",
  ].join(", ");
};

function ClassList() {
  const names = useStore(namesStore);
  const [group, setGroup] = useState<ClassGroup>("All");

  const list = useMemo(
    () => (group === "All" ? classes : classes.filter((c) => c.group === group)),
    [group],
  );

  const namedIn = (id: string) =>
    Object.entries(names).filter(
      ([k, v]) => k.startsWith(`${id}-`) && v.trim().length > 0,
    ).length;

  return (
    <div>
      <Link
        to="/portal/workspace"
        className="text-sm font-medium text-muted-foreground transition-colors hover:text-teal"
      >
        ← Workspace
      </Link>

      <h1 className="mt-6 font-display text-4xl text-foreground md:text-5xl">
        {portalInstitution.name} — Classes
      </h1>
      <p className="mt-2 text-sm font-medium text-muted-foreground">
        {classes.length} classes · tap a class to name its students.
      </p>

      <div className="no-scrollbar mt-8 flex gap-3 overflow-x-auto pb-2">
        {classGroups.map((g) => (
          <button
            key={g}
            onClick={() => setGroup(g)}
            className={`spectrum-border shrink-0 rounded-full px-5 py-2 text-xs font-semibold transition-colors ${
              group === g ? "bg-violet text-foreground" : "text-foreground"
            }`}
          >
            {g}
          </button>
        ))}
      </div>

      <div className="mt-8 grid grid-cols-3 gap-4 sm:grid-cols-4 lg:grid-cols-6">
        {list.map((c, i) => {
          const done = namedIn(c.id);
          const complete = done === c.size;
          return (
            <motion.div
              key={c.id}
              layout
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35, delay: Math.min(i, 12) * 0.02 }}
            >
              <Link
                to="/portal/workspace/students/$classId"
                params={{ classId: c.id }}
                /* `glass` supplies the backdrop blur; the tinted background is
                   inline because the utility's own background would otherwise win. */
                className="spectrum-border glass relative grid aspect-square place-items-center overflow-hidden rounded-2xl transition-all duration-300 hover:-translate-y-1 hover:shadow-[0_18px_40px_-18px_rgba(124,77,224,0.6)]"
                style={{ background: tintFor(i) }}
              >
                <span
                  className={`absolute right-2 top-2 z-[2] inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[0.6rem] font-semibold ${
                    complete
                      ? "bg-teal text-[#10281f]"
                      : "bg-background/80 text-muted-foreground"
                  }`}
                >
                  {complete && <Check className="h-3 w-3" />}
                  {done}/{c.size}
                </span>
                <span className="font-display text-xl font-bold uppercase text-foreground">
                  {c.name}
                </span>
              </Link>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
