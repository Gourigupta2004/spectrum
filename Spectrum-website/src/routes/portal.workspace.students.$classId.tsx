import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Check, MessageSquarePlus, UserPlus, X } from "lucide-react";
import { classLabel, type Student } from "@/lib/student-data";
import { absenteePreviews, useClassExtras, useRoster, useStudentNames } from "@/lib/portal-data";
import { useStore } from "@/lib/portal-store";
import { useOpenRosterGuidelines } from "@/lib/roster-guidelines";
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
  const { comment, addAbsentees, removeAbsentee, saveComment } = useClassExtras(classId);
  const previews = useStore(absenteePreviews);
  const fileRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState<{ done: number; total: number } | null>(null);
  const [actionError, setActionError] = useState("");
  const [commenting, setCommenting] = useState(false);
  const openGuidelines = useOpenRosterGuidelines();

  const upload = async (files: File[]) => {
    if (!files.length) return;
    setActionError("");
    setUploading({ done: 0, total: files.length });
    try {
      await addAbsentees(files, (done) => setUploading({ done, total: files.length }));
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Could not add the photos.");
    } finally {
      setUploading(null);
    }
  };
  const remove = async (studentId: string) => {
    if (!window.confirm("Remove this absentee photo?")) return;
    setActionError("");
    try {
      await removeAbsentee(studentId);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Could not remove the photo.");
    }
  };

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

      {/* The title, with what a teacher can add beside it: photos of absent
          students (named like everyone else) and one comment for the class. */}
      <div className="mt-6 flex flex-wrap items-end justify-between gap-4">
        <h1 className="font-display text-4xl text-foreground md:text-5xl">
          {fill(copy.rosterTitle, { class: classLabel(cls) })}
        </h1>
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => fileRef.current?.click()}
            disabled={uploading !== null}
            className="spectrum-border inline-flex min-h-11 items-center gap-2 rounded-full px-5 py-2.5 text-sm font-semibold text-foreground transition-colors hover:bg-violet/20 disabled:cursor-wait disabled:opacity-70"
          >
            <UserPlus className="h-4 w-4" />
            {uploading ? `Adding ${uploading.done} of ${uploading.total}…` : "Add Absentees"}
          </button>
          <button
            type="button"
            onClick={() => setCommenting(true)}
            className="spectrum-border inline-flex min-h-11 items-center gap-2 rounded-full px-5 py-2.5 text-sm font-semibold text-foreground transition-colors hover:bg-violet/20"
          >
            <MessageSquarePlus className="h-4 w-4" /> Add Comments
          </button>
          <input
            ref={fileRef}
            type="file"
            accept="image/*"
            multiple
            hidden
            onChange={(e) => {
              const files = Array.from(e.target.files ?? []);
              e.target.value = ""; // the same files can be picked again
              void upload(files);
            }}
          />
        </div>
      </div>
      <p className="mt-2 text-sm font-medium text-muted-foreground">
        {countLine}{" "}
        <button
          type="button"
          onClick={openGuidelines}
          className="font-semibold text-teal underline decoration-teal/40 underline-offset-4 transition-colors hover:text-foreground hover:decoration-foreground/40"
        >
          {copy.rosterGuidelinesLink}
        </button>
      </p>
      {comment && (
        <p className="mt-3 max-w-3xl whitespace-pre-line rounded-xl border border-border bg-background/40 px-4 py-2.5 text-sm text-foreground">
          <span className="font-semibold text-muted-foreground">Comment: </span>
          {comment}
        </p>
      )}
      {actionError && (
        <p role="alert" className="mt-3 text-sm font-medium text-[#ff9b6a]">
          {actionError}
        </p>
      )}

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
            student={s.photo || !previews[s.id] ? s : { ...s, photo: previews[s.id]! }}
            index={i}
            committed={names[s.id] ?? ""}
            onCommit={commit}
            onRemove={s.absentee ? () => void remove(s.id) : undefined}
            placeholder={copy.studentPlaceholder}
          />
        ))}
      </div>

      <CommentBox
        open={commenting}
        title={`Comment for ${classLabel(cls)}`}
        initial={comment}
        onClose={() => setCommenting(false)}
        onSave={saveComment}
      />
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
  onRemove,
  placeholder,
}: {
  student: Student;
  index: number;
  committed: string;
  onCommit: (studentId: string, value: string) => void;
  /** Absentees only: they were added by the institution and can be taken out again. */
  onRemove?: (() => void) | undefined;
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
        {student.absentee && (
          <span className="absolute bottom-2 left-2 z-[2] rounded-full bg-black/60 px-2.5 py-1 text-[0.65rem] font-semibold uppercase tracking-[0.12em] text-white backdrop-blur-sm">
            Absentee
          </span>
        )}
        {onRemove && (
          <button
            type="button"
            onClick={onRemove}
            aria-label="Remove this absentee photo"
            className="absolute right-2 top-2 z-[2] grid h-8 w-8 place-items-center rounded-full bg-black/55 text-white/90 backdrop-blur-sm transition-colors hover:bg-[#ba2121] hover:text-white"
          >
            <X className="h-4 w-4" />
          </button>
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

/** One comment per class, for the Spectrum team; it goes into the class's photo download. */
function CommentBox({
  open,
  title,
  initial,
  onClose,
  onSave,
}: {
  open: boolean;
  title: string;
  initial: string;
  onClose: () => void;
  onSave: (comment: string) => Promise<void>;
}) {
  const [text, setText] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    if (open) {
      setText(initial);
      setError("");
    }
  }, [open, initial]);

  const save = async () => {
    setBusy(true);
    setError("");
    try {
      await onSave(text.trim());
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save the comment.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={busy ? undefined : onClose}
          className="fixed inset-0 z-[80] grid place-items-center bg-black/70 p-4 backdrop-blur-md"
        >
          <motion.div
            initial={{ scale: 0.95, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.96, opacity: 0 }}
            transition={{ type: "spring", stiffness: 260, damping: 26 }}
            onClick={(e) => e.stopPropagation()}
            className="spectrum-border glass relative w-full max-w-lg rounded-3xl bg-surface p-6"
          >
            <button
              onClick={onClose}
              aria-label="Close"
              className="absolute right-4 top-4 text-foreground/80 transition-colors hover:text-foreground"
            >
              <X className="h-5 w-5" />
            </button>
            <h2 className="font-display text-2xl text-foreground">{title}</h2>
            <p className="mt-1 text-xs font-medium text-muted-foreground">
              Anything the Spectrum team should know about this class's photos.
            </p>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={6}
              maxLength={5000}
              autoFocus
              placeholder="e.g. Two students were away on a school trip; their photos are added as absentees."
              className="mt-4 w-full resize-none rounded-xl border border-border bg-background/60 px-4 py-3 text-sm leading-relaxed text-foreground placeholder:text-muted-foreground focus:border-transparent focus:outline-none focus:ring-2 focus:ring-violet"
            />
            <div className="mt-4 flex gap-3">
              <button
                onClick={onClose}
                disabled={busy}
                className="flex-1 rounded-xl border border-border py-3 text-sm font-semibold text-muted-foreground transition-colors hover:text-foreground"
              >
                Cancel
              </button>
              <button
                onClick={() => void save()}
                disabled={busy}
                className="spectrum-fill flex-1 rounded-xl py-3 text-sm font-semibold disabled:cursor-wait disabled:opacity-70"
              >
                {busy ? "Saving…" : "Save Comment"}
              </button>
            </div>
            {error && (
              <p role="alert" className="mt-3 text-center text-xs font-medium text-[#ff9b6a]">
                {error}
              </p>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
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
