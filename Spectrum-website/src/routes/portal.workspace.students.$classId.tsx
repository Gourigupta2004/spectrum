import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Check, Clock, Eye, Lock, MessageSquarePlus, Send, UserPlus, X } from "lucide-react";
import { classLabel, DEFAULT_EDIT_HOURS, type SchoolClass, type Student } from "@/lib/student-data";
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
  const { cls, students, loading, refresh } = useRoster(classId);
  const { names, commit, flush } = useStudentNames(classId, students);
  const { comment, addAbsentees, saveComment, submitClass } = useClassExtras(classId);
  // The review journey, the same as for titles:
  //   edit   — name, add absentees, comment; one button: Review
  //   review — everything read-only to check it; Re-edit or Submit
  //   reedit — one more chance to change anything; one button: Submit
  // Submit locks every photo named so far. The first Submit also starts the
  // clock: until it runs out the rest can still be named, absentees added
  // and the comment changed; then the whole class locks by itself (the
  // Spectrum team can unlock it).
  const [phase, setPhase] = useState<"edit" | "review" | "reedit">("edit");
  const frozen = phase === "review"; // nothing can change right now
  const left = useCountdown(cls?.deadlineAt, refresh);
  const gridRef = useRef<HTMLDivElement>(null);
  const toNames = () => gridRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
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

  if (!cls) {
    if (loading) return <p className="text-sm text-muted-foreground">Loading…</p>;
    return <ClassNotFound classId={classId} />;
  }
  if (cls.locked) return <LockedClass cls={cls} />;

  const open = students.filter((s) => !s.locked).length;
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
            disabled={uploading !== null || frozen}
            className="spectrum-border inline-flex min-h-11 items-center gap-2 rounded-full px-5 py-2.5 text-sm font-semibold text-foreground transition-colors hover:bg-violet/20 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <UserPlus className="h-4 w-4" />
            {uploading ? `Adding ${uploading.done} of ${uploading.total}…` : "Add Absentees"}
          </button>
          <button
            type="button"
            onClick={() => setCommenting(true)}
            disabled={frozen}
            className="spectrum-border inline-flex min-h-11 items-center gap-2 rounded-full px-5 py-2.5 text-sm font-semibold text-foreground transition-colors hover:bg-violet/20 disabled:cursor-not-allowed disabled:opacity-50"
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
      {left !== null ? (
        <WindowBanner left={left} until={cls.deadlineLabel ?? ""} />
      ) : (
        <p className="mt-4 flex max-w-3xl items-start gap-2 text-xs font-medium text-muted-foreground">
          <Clock className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          When you press Submit, the names you have given are locked and you have{" "}
          {cls.editHours ?? DEFAULT_EDIT_HOURS} hours to finish the rest of the class. After that it
          is submitted automatically and can no longer be changed.
        </p>
      )}

      {/* Six across on desktop — compact square frames, short enough that
          three rows fit on screen at once — the photos only rendered
          smaller (the stored images are untouched; full-size downloads live in
          the admin now, not here). A grid, so every card lines up: this is a
          form to work down, and ragged rows make it hard to keep your place.
          Each photo fills its frame, trimmed from the bottom if need be. */}
      <div
        ref={gridRef}
        className="mt-8 grid scroll-mt-28 grid-cols-2 items-stretch gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6"
      >
        {students.map((s, i) => (
          <StudentCard
            key={s.id}
            student={s.photo || !previews[s.id] ? s : { ...s, photo: previews[s.id]! }}
            index={i}
            committed={names[s.id] ?? ""}
            onCommit={commit}
            readOnly={frozen || Boolean(s.locked)}
            locked={Boolean(s.locked)}
            lockedTitle={copy.lockedTitle}
            lockedBody="This name has been submitted and locked. Only the Spectrum team can change it now."
            reviewing={phase === "review" && !s.locked}
            placeholder={copy.studentPlaceholder}
          />
        ))}
      </div>

      <SubmitPanel
        phase={open === 0 && cls.submitted ? "done" : phase}
        total={open}
        onReview={() => {
          setPhase("review");
          toNames();
        }}
        onReedit={() => {
          setPhase("reedit");
          toNames();
        }}
        onSubmit={async () => {
          await submitClass(() => flush());
          setPhase("edit");
        }}
      />

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

/** Enter commits and hops to the next card still open, so a teacher can name a class without touching the mouse. */
function focusNext(current: HTMLInputElement) {
  const all = Array.from(document.querySelectorAll<HTMLInputElement>("input[data-roster-input]"));
  all
    .slice(all.indexOf(current) + 1)
    .find((input) => !input.readOnly)
    ?.focus();
}

/**
 * Milliseconds left until `deadlineAt`, ticking every second, or null when
 * there is no deadline. Calls `onEnd` once as it reaches zero.
 */
function useCountdown(deadlineAt: number | undefined, onEnd: () => void): number | null {
  const [now, setNow] = useState(() => Date.now());
  const ended = useRef(false);
  useEffect(() => {
    ended.current = false;
    if (deadlineAt === undefined) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [deadlineAt]);
  const left = deadlineAt === undefined ? null : Math.max(0, deadlineAt - now);
  useEffect(() => {
    if (left === 0 && !ended.current) {
      ended.current = true;
      onEnd();
    }
  }, [left, onEnd]);
  return left;
}

function formatLeft(ms: number): string {
  const total = Math.floor(ms / 1000);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = String(total % 60).padStart(2, "0");
  return h ? `${h}h ${String(m).padStart(2, "0")}m ${s}s` : `${m}m ${s}s`;
}

/** After the first Submit: how long is left to finish, counting down. */
function WindowBanner({ left, until }: { left: number; until: string }) {
  return (
    <div
      role="status"
      className="mt-4 flex max-w-4xl flex-wrap items-center justify-between gap-4 rounded-2xl border border-amber-300/40 bg-amber-300/10 px-5 py-4"
    >
      <div className="flex min-w-0 flex-1 items-start gap-3">
        <Clock className="mt-0.5 h-5 w-5 shrink-0 text-amber-300" />
        <div className="min-w-[14rem]">
          <p className="text-sm font-semibold text-foreground">
            This class can be edited until {until}.
          </p>
          <p className="mt-1 text-xs font-medium text-muted-foreground">
            Submitted names are locked. Until then you can still name the remaining students, add
            absentees and comments. After that the class is submitted automatically and can no
            longer be changed.
          </p>
        </div>
      </div>
      <div className="text-right">
        <p className="text-[0.65rem] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
          Time left
        </p>
        <p className="font-display text-2xl font-bold tabular-nums text-amber-300">
          {formatLeft(left)}
        </p>
      </div>
    </div>
  );
}

/** Once the time to finish has run out (or the team locked it): nothing to open. */
function LockedClass({ cls }: { cls: SchoolClass }) {
  return (
    <div>
      <Link
        to="/portal/workspace/students"
        className="-my-2 inline-flex min-h-11 items-center text-sm font-medium text-muted-foreground transition-colors hover:text-teal"
      >
        ← All Classes
      </Link>
      <h1 className="mt-6 font-display text-4xl text-foreground md:text-5xl">{classLabel(cls)}</h1>
      <div className="mt-8 flex max-w-2xl items-start gap-4 rounded-2xl border border-teal/40 bg-teal/10 p-6">
        <span className="grid h-11 w-11 shrink-0 place-items-center rounded-full border border-teal/60 bg-teal/20 text-teal">
          <Lock className="h-5 w-5" />
        </span>
        <div>
          <p className="font-display text-xl font-semibold text-foreground">This class is locked</p>
          <p className="mt-1 text-sm font-medium text-muted-foreground">
            It was submitted{cls.submittedAt ? ` on ${cls.submittedAt}` : ""} and can no longer be
            changed. Please contact Spectrum if something needs correcting.
          </p>
        </div>
      </div>
    </div>
  );
}

function StudentCard({
  student,
  index,
  committed,
  onCommit,
  readOnly,
  locked,
  lockedTitle,
  lockedBody,
  reviewing,
  placeholder,
}: {
  student: Student;
  index: number;
  committed: string;
  onCommit: (studentId: string, value: string) => void;
  /** While reviewing, or once the name is submitted: the name can't change. */
  readOnly: boolean;
  /** Named and submitted: a tap explains why it can't be edited. */
  locked: boolean;
  lockedTitle: string;
  lockedBody: string;
  /** While reviewing: the name box is outlined so the names are easy to read through. */
  reviewing: boolean;
  placeholder: string;
}) {
  // Local draft while typing; the store only learns about it on blur or Enter.
  // That is what flips the card to its named state, so progress reads as
  // "names entered", not "keys pressed".
  const [draft, setDraft] = useState(committed);
  useEffect(() => setDraft(committed), [committed]);
  const named = committed.trim().length > 0;
  const [explaining, setExplaining] = useState(false);

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
      onClick={locked ? () => setExplaining((v) => !v) : undefined}
      className={`relative flex h-full flex-col overflow-hidden rounded-2xl bg-surface ${
        named ? "spectrum-border" : "ring-1 ring-border"
      } ${locked ? "cursor-not-allowed" : ""}`}
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
        {locked && (
          <span
            title={lockedTitle}
            className="absolute right-3 top-3 z-[2] grid h-7 w-7 place-items-center rounded-full bg-background/85 text-teal"
          >
            <Lock className="h-3.5 w-3.5" />
          </span>
        )}
        {/* The same "locked" card the class photographs show when tapped. */}
        <AnimatePresence>
          {explaining && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
              role="status"
              aria-live="polite"
              className="absolute inset-0 z-[3] grid place-items-center bg-black/70 p-3 backdrop-blur-sm"
            >
              <div className="flex flex-col items-center gap-1.5 text-center">
                <span className="grid h-10 w-10 place-items-center rounded-full border border-teal/60 bg-teal/25 text-white">
                  <Lock className="h-4 w-4" />
                </span>
                <p className="font-display text-sm font-semibold text-white">{lockedTitle}</p>
                <p className="text-[0.7rem] font-medium leading-snug text-white/80">{lockedBody}</p>
                <p className="text-[0.62rem] font-medium text-white/50">Tap again to dismiss</p>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
      <div className="flex flex-1 items-end p-2.5">
        <input
          data-roster-input
          value={draft}
          readOnly={readOnly}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => {
            if (e.key !== "Enter") return;
            e.preventDefault();
            e.currentTarget.blur();
            focusNext(e.currentTarget);
          }}
          placeholder={placeholder}
          aria-label={`Name for student ${index + 1}${locked ? " (submitted, locked)" : ""}`}
          className={`w-full rounded-xl border bg-background/60 px-3 py-1.5 text-sm text-foreground placeholder:text-muted-foreground focus:border-transparent focus:outline-none focus:ring-2 focus:ring-violet ${
            reviewing ? "border-transparent ring-1 ring-violet/70" : "border-border"
          }`}
        />
      </div>
    </motion.div>
  );
}

/**
 * The buttons at the foot of the class page, by step:
 *   edit   -> [Review]
 *   review -> [Re-edit] [Submit]
 *   reedit -> [Submit]
 *   done   -> a note; every photo is submitted (absentees can still be added)
 */
function SubmitPanel({
  phase,
  total,
  onReview,
  onReedit,
  onSubmit,
}: {
  phase: "edit" | "review" | "reedit" | "done";
  /** Photos still open to name. */
  total: number;
  onReview: () => void;
  onReedit: () => void;
  onSubmit: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async () => {
    setBusy(true);
    setError("");
    try {
      await onSubmit();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not submit. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  if (phase === "done") {
    return (
      <p className="mt-10 flex flex-wrap items-center justify-center gap-2 rounded-2xl border border-teal/40 bg-teal/10 px-4 py-4 text-center text-sm font-semibold text-teal">
        <Lock className="h-4 w-4" /> Every name is submitted. You can still add absentees and
        comments until the time runs out.
      </p>
    );
  }

  const outlined =
    "w-full rounded-2xl border border-violet py-4 text-base font-semibold text-foreground transition-colors hover:bg-violet/20 disabled:cursor-not-allowed disabled:opacity-40";
  const filled =
    "spectrum-fill w-full rounded-2xl py-4 text-base font-semibold disabled:cursor-not-allowed disabled:opacity-40";
  const submitButton = (
    <button disabled={busy} onClick={() => void submit()} className={filled}>
      <span className="inline-flex items-center justify-center gap-2">
        <Send className="h-5 w-5" /> {busy ? "Submitting…" : "Submit"}
      </span>
    </button>
  );

  return (
    <div className="mt-10">
      {phase === "edit" && (
        <button onClick={onReview} disabled={total === 0} className={outlined}>
          <span className="inline-flex items-center justify-center gap-2">
            <Eye className="h-5 w-5" /> Review
          </span>
        </button>
      )}
      {phase === "review" && (
        <div className="grid gap-3 sm:grid-cols-2 sm:gap-4">
          <button onClick={onReedit} className={outlined}>
            Re-edit
          </button>
          {submitButton}
        </div>
      )}
      {phase === "reedit" && submitButton}
      {error && (
        <p role="alert" className="mt-2 text-center text-xs font-medium text-[#ff9b6a]">
          {error}
        </p>
      )}
    </div>
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
