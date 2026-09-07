import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Check } from "lucide-react";
import { namesStore, useStore } from "@/lib/portal-store";
import { classLabel, findClass, studentsOf, type Student } from "@/lib/student-data";
import { exportRosterPdf } from "@/lib/roster-pdf";

export const Route = createFileRoute("/portal/workspace/students/$classId")({
  head: () => ({
    meta: [
      { title: "Name the Students — Spectrum Student Roster" },
      {
        name: "description",
        content: "Identify each student in the class photos, then export a labelled roster PDF.",
      },
      { property: "og:title", content: "Name the Students — Spectrum Student Roster" },
      {
        property: "og:description",
        content: "Name students in their class photos and download the roster as a PDF.",
      },
    ],
  }),
  component: ClassRoster,
});

const TOAST_MS = 3600;

function ClassRoster() {
  const { classId } = Route.useParams();
  const cls = findClass(classId);
  const names = useStore(namesStore);
  const students = useMemo(() => (cls ? studentsOf(cls.id) : []), [cls]);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState(false);
  const toastTimer = useRef<number | null>(null);
  useEffect(
    () => () => {
      if (toastTimer.current) window.clearTimeout(toastTimer.current);
    },
    [],
  );

  if (!cls) return <ClassNotFound classId={classId} />;

  const namedCount = students.filter((s) => (names[s.id] ?? "").trim().length > 0).length;
  const remaining = students.length - namedCount;
  const countLine = `${namedCount} of ${students.length} students named.`;

  const handleExport = async () => {
    if (busy) return;
    setBusy(true);
    try {
      // Read the store directly rather than the render-time snapshot: clicking
      // this button blurs whichever input had focus, and that blur commits a
      // name synchronously — so the store is already ahead of `names` here.
      await exportRosterPdf(cls, students, namesStore.get());
      setToast(true);
      if (toastTimer.current) window.clearTimeout(toastTimer.current);
      toastTimer.current = window.setTimeout(() => setToast(false), TOAST_MS);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="pb-14 md:pb-0">
      <Link
        to="/portal/workspace/students"
        className="text-sm font-medium text-muted-foreground transition-colors hover:text-teal"
      >
        ← All Classes
      </Link>

      <h1 className="mt-6 font-display text-4xl text-foreground md:text-5xl">
        {classLabel(cls)} — Name the Students
      </h1>
      <p className="mt-2 text-sm font-medium text-muted-foreground">{countLine}</p>

      {/* Five across on desktop (spec allows 4–6): six left each input too narrow for
          the full placeholder copy at this container width. */}
      <div className="mt-8 grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
        {students.map((s, i) => (
          <StudentCard key={s.id} student={s} index={i} committed={names[s.id] ?? ""} />
        ))}
      </div>

      {/* Sticky bar — same construction as the gallery's: dark base, gradient hairline, count left, action right. */}
      <div className="fixed inset-x-0 bottom-0 z-40 bg-surface/95 backdrop-blur-xl">
        <div className="spectrum-hairline w-full" />
        <div className="mx-auto flex max-w-6xl flex-col items-center gap-3 px-6 py-4 text-center md:flex-row md:justify-between md:text-left">
          <p className="text-sm text-foreground">{countLine}</p>
          <div className="flex flex-col items-center gap-3 md:flex-row md:gap-4">
            {remaining > 0 && (
              <span className="text-xs font-medium text-muted-foreground">
                {remaining} {remaining === 1 ? "student" : "students"} still unnamed.
              </span>
            )}
            <button
              onClick={handleExport}
              disabled={busy}
              aria-busy={busy}
              className="spectrum-fill rounded-full px-6 py-3 text-sm font-semibold disabled:cursor-wait disabled:opacity-70"
            >
              {busy ? "Generating…" : "Download Class PDF →"}
            </button>
          </div>
        </div>
      </div>

      {/* Toast sits in a fixed, non-animated wrapper: motion writes `transform`
          inline, which would clobber a Tailwind translate used for centring. */}
      <div className="pointer-events-none fixed inset-x-0 bottom-28 z-50 flex justify-center px-4">
        <AnimatePresence>
          {toast && (
            <motion.div
              role="status"
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 10 }}
              transition={{ type: "spring", stiffness: 300, damping: 26 }}
              className="spectrum-border glass pointer-events-auto flex items-center gap-3 rounded-2xl px-5 py-3 text-sm font-medium text-foreground shadow-2xl"
            >
              <span className="grid h-6 w-6 place-items-center rounded-full bg-teal">
                <Check className="h-3.5 w-3.5 text-[#14231d]" />
              </span>
              PDF downloaded
            </motion.div>
          )}
        </AnimatePresence>
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
}: {
  student: Student;
  index: number;
  committed: string;
}) {
  // Local draft while typing; the store only learns about it on blur or Enter.
  // That is what flips the card to its named state, so progress reads as
  // "names entered", not "keys pressed".
  const [draft, setDraft] = useState(committed);
  useEffect(() => setDraft(committed), [committed]);
  const named = committed.trim().length > 0;

  const commit = () => {
    const value = draft.trim();
    if (value !== committed) namesStore.set((prev) => ({ ...prev, [student.id]: value }));
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: Math.min(index, 14) * 0.02 }}
      // `ring` for the unnamed hairline (no layout impact) so the card is the
      // same size in both states — a real border would shift it by a pixel.
      className={`relative overflow-hidden rounded-2xl bg-surface ${
        named ? "spectrum-border" : "ring-1 ring-border"
      }`}
    >
      <div className="relative aspect-[3/4]">
        <img src={student.photo} alt="" draggable={false} className="h-full w-full object-cover" />
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
      <div className="p-3">
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
          placeholder="Add student's name…"
          aria-label={`Name for student ${index + 1}`}
          className="w-full rounded-xl border border-border bg-background/60 px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-transparent focus:outline-none focus:ring-2 focus:ring-violet"
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
