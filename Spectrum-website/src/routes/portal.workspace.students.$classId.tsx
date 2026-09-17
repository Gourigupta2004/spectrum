import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Check, FolderDown } from "lucide-react";
import { classLabel, type Student } from "@/lib/student-data";
import { exportRosterFolder } from "@/lib/roster-zip";
import { useRoster, useStudentNames } from "@/lib/portal-data";
import { usePortalMember } from "@/lib/portal-session";
import { usePortalCopy } from "@/lib/use-portal-copy";
import { fill } from "@/lib/text";

export const Route = createFileRoute("/portal/workspace/students/$classId")({
  head: () => ({
    meta: [
      { title: "Name the Students — Spectrum Student Roster" },
      {
        name: "description",
        content:
          "Identify each student in the class photos, then download the photos as a folder named after them.",
      },
      { property: "og:title", content: "Name the Students — Spectrum Student Roster" },
      {
        property: "og:description",
        content: "Name students in their class photos and download them as a folder.",
      },
    ],
  }),
  component: ClassRoster,
});

const TOAST_MS = 3600;

function ClassRoster() {
  const { classId } = Route.useParams();
  const copy = usePortalCopy();
  const { institution } = usePortalMember();
  const { cls, students, loading } = useRoster(classId);
  const { names, commit, current } = useStudentNames(classId, students);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [error, setError] = useState("");
  const toastTimer = useRef<number | null>(null);
  useEffect(
    () => () => {
      if (toastTimer.current) window.clearTimeout(toastTimer.current);
    },
    [],
  );

  if (!cls) {
    if (loading) return <p className="text-sm text-muted-foreground">Loading…</p>;
    return <ClassNotFound classId={classId} />;
  }

  const namedCount = students.filter((s) => (names[s.id] ?? "").trim().length > 0).length;
  const remaining = students.length - namedCount;
  const countLine = `${namedCount} of ${students.length} students named.`;

  const handleExport = async () => {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      // Read the store directly rather than the render-time snapshot: clicking
      // this button blurs whichever input had focus, and that blur commits a
      // name synchronously — so the store is already ahead of `names` here.
      const result = await exportRosterFolder(cls, students, current(), institution.name);
      if (result.included === 0) {
        setError("None of the named students' photos could be read.");
        return;
      }
      setToast(fill(copy.downloadToast, { count: result.included }));
      if (result.failed > 0)
        setError(`${result.failed} photo(s) could not be read and were left out.`);
      if (toastTimer.current) window.clearTimeout(toastTimer.current);
      toastTimer.current = window.setTimeout(() => setToast(null), TOAST_MS);
    } catch {
      setError("Could not build the folder. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="pb-14 md:pb-0">
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

      {/* Five across on desktop (spec allows 4–6): six left each input too narrow for
          the full placeholder copy at this container width. */}
      {/* A grid, so every card lines up: this is a form to work down, and ragged
          rows make it hard to keep your place. The photo inside each frame is
          shown whole rather than cropped — see the card below. */}
      <div className="mt-8 grid grid-cols-2 items-stretch gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
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

      {/* Sticky bar — same construction as the gallery's: dark base, gradient hairline, count left, action right. */}
      <div className="fixed inset-x-0 bottom-0 z-40 bg-surface/95 backdrop-blur-xl">
        <div className="spectrum-hairline w-full" />
        <div className="mx-auto flex max-w-6xl flex-col items-center gap-3 px-6 py-4 text-center md:flex-row md:justify-between md:text-left">
          <div>
            <p className="text-sm text-foreground">{countLine}</p>
            {error && (
              <p role="alert" className="mt-1 text-xs font-medium text-[#ff9b6a]">
                {error}
              </p>
            )}
          </div>
          <div className="flex flex-col items-center gap-3 md:flex-row md:gap-4">
            {remaining > 0 && (
              <span className="text-xs font-medium text-muted-foreground">
                {fill(copy.downloadNote, { count: remaining })}
              </span>
            )}
            <button
              onClick={handleExport}
              disabled={busy || namedCount === 0}
              aria-busy={busy}
              title={namedCount === 0 ? "Name at least one student first" : undefined}
              className="spectrum-fill inline-flex items-center gap-2 rounded-full px-6 py-3 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50"
            >
              <FolderDown className="h-4 w-4" />
              {busy ? "Preparing…" : copy.downloadPhotos}
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
              {toast}
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
      {/* One frame for every student, with the whole photo inside it: a blurred
          copy of the same picture fills the frame, so a photo that is not the
          usual portrait shape sits on its own colours and is never cropped. */}
      <div className="relative aspect-[3/4] w-full shrink-0 overflow-hidden bg-[#14131a]">
        {student.photo ? (
          <>
            <img
              src={student.photo}
              alt=""
              aria-hidden
              loading="lazy"
              draggable={false}
              className="absolute inset-0 h-full w-full scale-110 object-cover opacity-45 blur-2xl"
            />
            <img
              src={student.photo}
              alt=""
              loading="lazy"
              draggable={false}
              className="absolute inset-0 h-full w-full object-contain"
            />
          </>
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
      <div className="flex flex-1 items-end p-3">
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
