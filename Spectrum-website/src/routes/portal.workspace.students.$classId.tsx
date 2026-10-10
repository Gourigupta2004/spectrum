import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Check } from "lucide-react";
import { classLabel, type Student } from "@/lib/student-data";
import { useRoster, useStudentNames } from "@/lib/portal-data";
import { usePortalCopy } from "@/lib/use-portal-copy";
import { fill } from "@/lib/text";

export const Route = createFileRoute("/portal/workspace/students/$classId")({
  head: () => ({
    meta: [
      { title: "Name the Students — Spectrum Student Roster" },
      {
        name: "description",
        content: "Identify each student in the class photos, name by name.",
      },
      { property: "og:title", content: "Name the Students — Spectrum Student Roster" },
      {
        property: "og:description",
        content: "Name students in their class photos.",
      },
    ],
  }),
  component: ClassRoster,
});

function ClassRoster() {
  const { classId } = Route.useParams();
  const copy = usePortalCopy();
  const { cls, students, loading } = useRoster(classId);
  const { names, commit } = useStudentNames(classId, students);

  if (!cls) {
    if (loading) return <p className="text-sm text-muted-foreground">Loading…</p>;
    return <ClassNotFound classId={classId} />;
  }

  const namedCount = students.filter((s) => (names[s.id] ?? "").trim().length > 0).length;
  const countLine = `${namedCount} of ${students.length} students named.`;

  return (
    <div>
      <Link
        to="/portal/workspace/students"
        className="-my-2 inline-flex min-h-11 items-center text-sm font-medium text-muted-foreground transition-colors hover:text-teal"
      >
        ← All Classes
      </Link>

      <h1 className="mt-6 font-display text-4xl text-foreground md:text-5xl">
        {fill(copy.rosterTitle, { class: classLabel(cls) })}
      </h1>
      <p className="mt-2 text-sm font-medium text-muted-foreground">{countLine}</p>

      {/* Six across on desktop — compact square frames, short enough that
          three rows fit on screen at once — the photos only rendered
          smaller (the stored images are untouched; full-size downloads live in
          the admin now, not here). A grid, so every card lines up: this is a
          form to work down, and ragged rows make it hard to keep your place.
          Each photo fills its frame, trimmed from the bottom if need be. */}
      <div className="mt-8 grid grid-cols-2 items-stretch gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
        {students.map((s, i) => (
          <StudentCard
            key={s.id}
            student={s}
            index={i}
            committed={names[s.id] ?? ""}
            onCommit={commit}
            placeholder={copy.studentPlaceholder}
          />
        ))}
      </div>
    </div>
  );
}

/** Enter commits and hops to the next card, so a teacher can name a class without touching the mouse. */
function focusNext(current: HTMLInputElement) {
  const all = Array.from(document.querySelectorAll<HTMLInputElement>("input[data-roster-input]"));
  all[all.indexOf(current) + 1]?.focus();
}

function StudentCard({
  student,
  index,
  committed,
  onCommit,
  placeholder,
}: {
  student: Student;
  index: number;
  committed: string;
  onCommit: (studentId: string, value: string) => void;
  placeholder: string;
}) {
  // Local draft while typing; the store only learns about it on blur or Enter.
  // That is what flips the card to its named state, so progress reads as
  // "names entered", not "keys pressed".
  const [draft, setDraft] = useState(committed);
  useEffect(() => setDraft(committed), [committed]);
  const named = committed.trim().length > 0;

  const commit = () => {
    const value = draft.trim();
    if (value !== committed) onCommit(student.id, value);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: Math.min(index, 14) * 0.02 }}
      // `ring` for the unnamed hairline (no layout impact) so the card is the
      // same size in both states — a real border would shift it by a pixel.
      className={`relative flex h-full flex-col overflow-hidden rounded-2xl bg-surface ${
        named ? "spectrum-border" : "ring-1 ring-border"
      }`}
    >
      {/* One square frame for every student, filled by the photo. It is
          pinned to the top, so a portrait loses a little from the bottom and
          never the face — that is all a teacher needs to name the student. */}
      <div className="relative aspect-square w-full shrink-0 overflow-hidden bg-[#14131a]">
        {student.photo ? (
          <img
            src={student.photo}
            alt=""
            loading="lazy"
            draggable={false}
            className="absolute inset-0 h-full w-full object-cover object-top"
          />
        ) : (
          <div className="h-full w-full bg-background/60" />
        )}
        <AnimatePresence>
          {named && (
            <motion.span
              key="named"
              initial={{ scale: 0.6, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.6, opacity: 0 }}
              transition={{ type: "spring", stiffness: 380, damping: 22 }}
              className="absolute left-3 top-3 z-[2] grid h-7 w-7 place-items-center rounded-full bg-teal"
            >
              <Check className="h-4 w-4 text-[#14231d]" />
            </motion.span>
          )}
        </AnimatePresence>
      </div>
      <div className="flex flex-1 items-end p-2.5">
        <input
          data-roster-input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => {
            if (e.key !== "Enter") return;
            e.preventDefault();
            e.currentTarget.blur();
            focusNext(e.currentTarget);
          }}
          placeholder={placeholder}
          aria-label={`Name for student ${index + 1}`}
          className="w-full rounded-xl border border-border bg-background/60 px-3 py-1.5 text-sm text-foreground placeholder:text-muted-foreground focus:border-transparent focus:outline-none focus:ring-2 focus:ring-violet"
        />
      </div>
    </motion.div>
  );
}

function ClassNotFound({ classId }: { classId: string }) {
  return (
    <div>
      <Link
        to="/portal/workspace/students"
        className="text-sm font-medium text-muted-foreground transition-colors hover:text-teal"
      >
        ← All Classes
      </Link>
      <h1 className="mt-6 font-display text-4xl text-foreground">Class not found</h1>
      <p className="mt-2 text-sm font-medium text-muted-foreground">
        There is no class “{classId}” in this roster.
      </p>
    </div>
  );
}
