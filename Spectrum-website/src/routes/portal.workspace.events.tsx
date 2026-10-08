import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import {
  ArrowLeft,
  CheckCircle2,
  Clock,
  ImagePlus,
  LayoutGrid,
  Lock,
  Plus,
  RefreshCw,
  X,
} from "lucide-react";
import { StatusPill } from "@/components/spectrum/status-pill";
import { GuidelinesModal } from "@/components/spectrum/guidelines-modal";
import { hasApi } from "@/lib/api";
import {
  captionStatusLabel,
  pluralImages,
  type CaptionItem,
  type CaptionStatus,
} from "@/lib/caption-data";
import {
  useAddCaption,
  useCaptionItems,
  useReplaceCaptionImage,
  useResolveCaption,
  type NewCaption,
} from "@/lib/portal-data";
import {
  guidelinesSeenThisSession,
  markGuidelinesSeen,
  usePortalMember,
} from "@/lib/portal-session";
import { usePortalCopy } from "@/lib/use-portal-copy";

export const Route = createFileRoute("/portal/workspace/events")({
  head: () => ({
    meta: [
      { title: "Class Photographs — Spectrum Title Workspace" },
      {
        name: "description",
        content: "Review, approve and correct titles for Spectrum event photos.",
      },
      { property: "og:title", content: "Class Photographs — Spectrum Title Workspace" },
      {
        property: "og:description",
        content: "Review, approve and correct Spectrum event photo titles.",
      },
    ],
  }),
  component: Workspace,
});

/**
 * Teachers only need two buckets. Everything that still needs a hand from the
 * institution — captions to write, approvals, corrections — is
 * "pending"; once approved an item is locked and lives under "approved".
 * The fine-grained status stays on the card's pill, which the backend will own.
 */
type Filter = "all" | "pending" | "approved";

const isApproved = (i: CaptionItem) => i.status === "approved";

type FilterDef = {
  key: Filter;
  label: string;
  icon: typeof Clock;
  /** Two brand stops, as "r,g,b", matching the homepage service chips. */
  tint: [string, string];
};

const allFilter: FilterDef = {
  key: "all",
  label: "All",
  icon: LayoutGrid,
  tint: ["124,77,224", "61,139,255"], // violet -> blue
};

const filters: FilterDef[] = [
  {
    key: "pending",
    label: "Pending",
    icon: Clock,
    tint: ["232,80,58", "214,51,154"], // red -> magenta
  },
  {
    key: "approved",
    label: "Approved",
    icon: CheckCircle2,
    tint: ["94,183,70", "47,191,143"], // green -> teal
  },
];

/**
 * Same recipe as the homepage glass chips: a specular sheen, two radial brand
 * tints and a translucent dark base. Idle chips use the homepage's light tint
 * as-is; selecting one deepens both tints and darkens the base, but it stays
 * translucent so it still reads as glass.
 */
const chipBackground = ([a, b]: [string, string], on: boolean): string =>
  [
    `linear-gradient(180deg, rgba(255,255,255,${on ? 0.1 : 0.16}) 0%, rgba(255,255,255,0.04) 46%, rgba(255,255,255,0) 56%)`,
    `radial-gradient(120% 140% at 18% 0%, rgba(${a},${on ? 0.72 : 0.42}), transparent ${on ? 68 : 62}%)`,
    `radial-gradient(120% 140% at 88% 100%, rgba(${b},${on ? 0.64 : 0.34}), transparent ${on ? 68 : 62}%)`,
    `rgba(${on ? "12,10,16,0.82" : "28,26,34,0.55"})`,
  ].join(", ");

/** One soft coloured glow when selected; the gradient hairline is the only outline. */
const chipShadow = ([a]: [string, string], on: boolean): string =>
  on
    ? `inset 0 1px 0 rgba(255,255,255,0.12), 0 18px 44px -16px rgba(${a},0.65)`
    : "inset 0 1px 0 rgba(255,255,255,0.14), 0 10px 30px -16px rgba(0,0,0,0.7)";

const chipClass = (on: boolean) =>
  `spectrum-border glass relative flex items-center text-left text-foreground transition-all duration-300 ${
    on ? "" : "hover:-translate-y-0.5"
  }`;

function FilterIcon({ f, on }: { f: FilterDef; on: boolean }) {
  return (
    <span
      style={on ? { background: `rgba(${f.tint[0]},0.28)` } : undefined}
      className={`grid h-9 w-9 shrink-0 place-items-center rounded-full border transition-colors ${
        on ? "border-white/30" : "border-white/15 bg-white/5"
      }`}
    >
      <f.icon className="h-[1.1rem] w-[1.1rem]" />
    </span>
  );
}

function Workspace() {
  const copy = usePortalCopy();
  const { items, loading, error: loadError } = useCaptionItems();
  const { resolve, error: saveError } = useResolveCaption();
  const replaceImage = useReplaceCaptionImage();
  const [imageError, setImageError] = useState("");
  const addCaption = useAddCaption();
  const { role } = usePortalMember();
  const [filter, setFilter] = useState<Filter>("all");
  const [openId, setOpenId] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  // The guidelines open themselves the first time this workspace is visited in
  // a session, and afterwards only from the link in the caption editor.
  const [guidelines, setGuidelines] = useState(false);
  useEffect(() => {
    if (guidelinesSeenThisSession()) return;
    markGuidelinesSeen();
    setGuidelines(true);
  }, []);
  // Card that was tapped while locked; shows the warning for a moment.
  const [lockedId, setLockedId] = useState<string | null>(null);
  const lockTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const list = useMemo(
    () =>
      filter === "all"
        ? items
        : items.filter((i) => (filter === "approved" ? isApproved(i) : !isApproved(i))),
    [items, filter],
  );
  const pendingCount = items.filter((i) => !isApproved(i)).length;
  const approvedCount = items.length - pendingCount;
  const counts: Record<Filter, number> = {
    all: items.length,
    pending: pendingCount,
    approved: approvedCount,
  };
  const canManagePhotos = role === "spectrum";

  const dismissLock = () => {
    if (lockTimer.current) clearTimeout(lockTimer.current);
    lockTimer.current = null;
    setLockedId(null);
  };
  useEffect(() => () => void (lockTimer.current && clearTimeout(lockTimer.current)), []);

  const openItem = (item: CaptionItem) => {
    if (!isApproved(item)) {
      setOpenId(item.id);
      return;
    }
    // Second tap dismisses; otherwise it fades on its own.
    if (lockedId === item.id) {
      dismissLock();
      return;
    }
    if (lockTimer.current) clearTimeout(lockTimer.current);
    setLockedId(item.id);
    lockTimer.current = setTimeout(() => setLockedId(null), 2200);
  };
  const active = items.find((i) => i.id === openId) ?? null;

  return (
    <>
      <div>
        <Link
          to="/portal/workspace"
          className="-my-2 inline-flex min-h-11 items-center gap-2 text-sm font-medium text-muted-foreground transition-colors hover:text-teal"
        >
          <ArrowLeft className="h-4 w-4" /> Workspace
        </Link>

        <div className="mt-6 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="font-display text-4xl text-foreground md:text-5xl">
              {copy.captionsTitle}
            </h1>
          </div>
          {canManagePhotos && (
            <button
              onClick={() => setAdding(true)}
              className="spectrum-fill inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-xs font-semibold"
            >
              <Plus className="h-4 w-4" /> Add Image
            </button>
          )}
        </div>

        {/* all / pending / approved filter */}
        <div className="mt-8 grid grid-cols-2 gap-3 sm:flex sm:items-center sm:gap-4">
          {[allFilter, ...filters].map((f) => {
            const on = filter === f.key;
            const count = counts[f.key];
            const isAll = f.key === "all";
            return (
              <button
                key={f.key}
                onClick={() => setFilter(f.key)}
                aria-pressed={on}
                aria-label={`${f.label}, ${pluralImages(count)}`}
                style={{
                  background: chipBackground(f.tint, on),
                  boxShadow: chipShadow(f.tint, on),
                }}
                className={`${chipClass(on)} h-14 gap-3 rounded-full pl-2.5 pr-2.5 ${
                  isAll ? "col-span-2 sm:col-auto sm:shrink-0 sm:pr-3" : "sm:flex-1"
                }`}
              >
                <FilterIcon f={f} on={on} />
                <span
                  aria-hidden
                  className={`font-display text-base font-semibold leading-none ${
                    isAll ? "pr-1" : "flex-1"
                  }`}
                >
                  {f.label}
                </span>
                <span
                  aria-hidden
                  className={`rounded-full border px-3 py-1 font-display text-sm leading-none tabular-nums transition-colors ${
                    on ? "border-white/25 bg-white/15" : "border-white/10 bg-black/25"
                  }`}
                >
                  {count}
                </span>
              </button>
            );
          })}
        </div>

        {/* grid */}
        {/*
          A plain grid, deliberately. This is a review queue, not a photo wall:
          the eye runs down a column of cards comparing captions, and ragged
          card tops make that unreadable. Every card is the same size and the
          photo inside is shown whole rather than cropped — see the frame below.
        */}
        <div className="mt-8 grid items-stretch gap-6 sm:grid-cols-2 lg:grid-cols-3">
          <AnimatePresence mode="popLayout" initial={false}>
            {list.map((item) => (
              <motion.button
                key={item.id}
                layout
                initial={{ opacity: 0, y: 14 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.96 }}
                transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
                onClick={() => openItem(item)}
                aria-label={
                  isApproved(item) ? `${item.momentTitle}, approved and locked` : item.momentTitle
                }
                className={`spectrum-border group flex h-full w-full flex-col overflow-hidden rounded-2xl bg-surface p-0 text-left align-top transition-transform ${
                  isApproved(item) ? "cursor-not-allowed" : "hover:-translate-y-1"
                }`}
              >
                {/*
                  One frame for every card, with the whole photo inside it: a
                  blurred, over-scaled copy of the same picture fills the frame
                  so a tall or wide shot sits on its own colours instead of on
                  grey bars, and the sharp copy on top is never cropped.
                */}
                <div className="relative aspect-[4/3] w-full shrink-0 overflow-hidden rounded-t-2xl bg-[#14131a]">
                  {item.image && (
                    <>
                      <img
                        src={item.image}
                        alt=""
                        aria-hidden
                        loading="lazy"
                        draggable={false}
                        className="absolute inset-0 h-full w-full scale-110 object-cover opacity-45 blur-2xl"
                      />
                      <img
                        src={item.image}
                        alt={item.momentTitle}
                        loading="lazy"
                        draggable={false}
                        className={`absolute inset-0 h-full w-full object-contain transition-transform duration-700 ${
                          isApproved(item) ? "" : "group-hover:scale-[1.03]"
                        }`}
                      />
                    </>
                  )}
                  <div className="absolute inset-x-0 bottom-0 h-20 bg-gradient-to-t from-black/70 to-transparent" />
                  <StatusPill status={item.status} className="absolute left-3 top-3" />
                  <AnimatePresence>
                    {lockedId === item.id && (
                      <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        transition={{ duration: 0.15 }}
                        role="status"
                        aria-live="polite"
                        className="absolute inset-0 grid place-items-center bg-black/65 p-4 backdrop-blur-sm"
                      >
                        <motion.div
                          initial={{ scale: 0.9, y: 6 }}
                          animate={{ scale: 1, y: 0 }}
                          transition={{ type: "spring", stiffness: 320, damping: 22 }}
                          className="flex max-w-[16rem] flex-col items-center gap-2 text-center"
                        >
                          <span className="grid h-12 w-12 place-items-center rounded-full border border-teal/60 bg-teal/25 text-white backdrop-blur-md">
                            <Lock className="h-5 w-5" />
                          </span>
                          <p className="font-display text-base font-semibold text-white">
                            {copy.lockedTitle}
                          </p>
                          <p className="text-xs font-medium text-white/80">{copy.lockedBody}</p>
                          <p className="text-[0.7rem] sm:text-[0.65rem] font-medium text-white/50">
                            Tap again to dismiss
                          </p>
                        </motion.div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
                {/* Grows to fill the card so the "updated" line sits on the
                    same baseline across a row, whatever the caption's length. */}
                <div className="flex flex-1 flex-col p-4">
                  <p className="line-clamp-1 font-display text-base font-semibold text-foreground">
                    {item.momentTitle}
                  </p>
                  {item.caption ? (
                    <p className="mt-1 line-clamp-2 flex-1 text-xs font-medium text-muted-foreground">
                      {item.caption}
                    </p>
                  ) : (
                    <p className="mt-1 flex-1 text-xs font-medium italic text-muted-foreground/70">
                      No title yet
                    </p>
                  )}
                  <p className="mt-3 pt-1 text-[0.72rem] uppercase tracking-[0.14em] text-muted-foreground sm:text-[0.68rem]">
                    Updated {item.updatedAt}
                  </p>
                </div>
              </motion.button>
            ))}
          </AnimatePresence>
        </div>

        {(loadError || saveError || imageError) && (
          <p role="alert" className="mt-6 text-center text-sm font-medium text-[#ff9b6a]">
            {loadError || saveError || imageError}
          </p>
        )}
        {list.length === 0 && (
          <p className="mt-16 text-center text-sm text-muted-foreground">
            {loading
              ? "Loading…"
              : filter === "approved"
                ? copy.captionsEmptyApproved
                : filter === "pending"
                  ? copy.captionsEmptyPending
                  : copy.captionsEmptyAll}
          </p>
        )}
      </div>

      <CaptionEditor
        item={active}
        onClose={() => setOpenId(null)}
        onResolve={resolve}
        onReplaceImage={(id, file) => {
          setImageError("");
          replaceImage(id, file).catch((err: unknown) =>
            setImageError(err instanceof Error ? err.message : "Could not replace the photo."),
          );
        }}
        canManagePhotos={canManagePhotos}
        onOpenGuidelines={() => setGuidelines(true)}
      />
      <GuidelinesModal open={guidelines} onClose={() => setGuidelines(false)} copy={copy} />
      <AddImageModal
        open={adding}
        onClose={() => setAdding(false)}
        onAdd={async (input) => {
          await addCaption(input);
          setAdding(false);
        }}
      />
    </>
  );
}

/* ---------------- Caption editor overlay ---------------- */

function CaptionEditor({
  item,
  onClose,
  onResolve,
  onReplaceImage,
  canManagePhotos,
  onOpenGuidelines,
}: {
  item: CaptionItem | null;
  onClose: () => void;
  onResolve: (
    id: string,
    status: CaptionStatus,
    patch: Partial<CaptionItem>,
    by: string,
    phone: string,
  ) => void;
  onReplaceImage: (id: string, file: File) => void;
  canManagePhotos: boolean;
  onOpenGuidelines: () => void;
}) {
  return (
    <AnimatePresence>
      {item && (
        <CaptionEditorInner
          key={item.id}
          item={item}
          onClose={onClose}
          onResolve={onResolve}
          onReplaceImage={onReplaceImage}
          canManagePhotos={canManagePhotos}
          onOpenGuidelines={onOpenGuidelines}
        />
      )}
    </AnimatePresence>
  );
}

function CaptionEditorInner({
  item,
  onClose,
  onResolve,
  onReplaceImage,
  canManagePhotos,
  onOpenGuidelines,
}: {
  item: CaptionItem;
  onClose: () => void;
  onResolve: (
    id: string,
    status: CaptionStatus,
    patch: Partial<CaptionItem>,
    by: string,
    phone: string,
  ) => void;
  onReplaceImage: (id: string, file: File) => void;
  canManagePhotos: boolean;
  onOpenGuidelines: () => void;
}) {
  const copy = usePortalCopy();
  /*
   * One action per status, driven by the live status:
   *   caption — nothing written yet; the institution writes the title
   *   approve — sign off on the wording as-is; no correction is offered
   *   correct — rewrite the title in place: the box opens on the current
   *             wording and what is saved replaces it
   *             (also how a corrected item is revised)
   */
  const mode =
    item.status === "needs-caption"
      ? "caption"
      : item.status === "needs-approval"
        ? "approve"
        : "correct";
  const [text, setText] = useState(mode === "correct" ? item.caption : "");
  const [by, setBy] = useState(item.actionBy ?? "");
  const [phone, setPhone] = useState(item.actionByPhone ?? "");
  const photoRef = useRef<HTMLInputElement>(null);
  const hasText = text.trim().length > 0;
  // Both the name and a usable mobile number are required before acting.
  const phoneOk = phone.replace(/\D/g, "").length >= 7;
  const canAct = by.trim().length > 1 && phoneOk;

  const fieldLabel = mode === "caption" ? "Title" : "Correction";
  const byLabel =
    mode === "caption" ? "Title written by" : mode === "approve" ? "Approved by" : "Corrected by";
  const primaryLabel =
    mode === "caption" ? "Save Title" : mode === "approve" ? "Approve Title" : "Save Correction";
  const primaryDisabled = !canAct || (mode !== "approve" && !hasText);
  const submit = () => {
    if (mode === "approve") onResolve(item.id, "approved", {}, by.trim(), phone.trim());
    else onResolve(item.id, "corrected", { caption: text.trim() }, by.trim(), phone.trim());
    onClose();
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      onClick={onClose}
      className="fixed inset-0 z-[80] grid place-items-center bg-black/70 p-4 backdrop-blur-md md:px-[5vw]"
    >
      <motion.div
        initial={{ scale: 0.95, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.96, opacity: 0 }}
        transition={{ type: "spring", stiffness: 260, damping: 26 }}
        onClick={(e) => e.stopPropagation()}
        /* Landscape by design: most event photos are wider than tall. On desktop
           the window spans 90% of the width at 72% of the height, centred. */
        className="spectrum-border glass relative grid max-h-[90vh] w-full overflow-y-auto rounded-3xl bg-surface md:h-[72vh] md:max-w-[90vw] md:grid-cols-[3fr_2fr] md:overflow-hidden"
      >
        <button
          onClick={onClose}
          aria-label="Close"
          className="absolute right-4 top-4 z-10 grid h-9 w-9 place-items-center rounded-full bg-black/40 text-white/85 backdrop-blur-md transition-colors hover:text-white"
        >
          <X className="h-5 w-5" />
        </button>

        {/* The whole photo, letterboxed on the surface tone: the person reviewing
            a caption needs to see exactly what was shot, not a crop of it. */}
        <div className="group relative h-64 bg-[#1C1A22] sm:h-80 md:h-full">
          {item.image && (
            <img
              src={item.image}
              alt={item.momentTitle}
              draggable={false}
              className="absolute inset-0 h-full w-full object-contain"
            />
          )}

          {canManagePhotos && (
            <>
              {/* Scrim only behind the control, so it stays legible on a light photo
                  without dimming the image being reviewed. */}
              <div className="pointer-events-none absolute inset-x-0 bottom-0 h-24 bg-gradient-to-t from-black/70 to-transparent" />
              <button
                type="button"
                onClick={() => photoRef.current?.click()}
                className="absolute bottom-4 left-4 inline-flex items-center gap-2 rounded-full border border-white/25 bg-black/45 px-3.5 py-2 text-xs font-semibold text-white backdrop-blur-md transition-colors hover:border-teal hover:text-teal focus:outline-none focus:ring-2 focus:ring-violet"
              >
                <RefreshCw className="h-3.5 w-3.5" /> Replace photo
              </button>
            </>
          )}

          <input
            ref={photoRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (!f) return;
              onReplaceImage(item.id, f);
              // Let the same file be picked again after an accidental replace.
              e.target.value = "";
            }}
          />
        </div>

        <div className="flex min-h-0 flex-col gap-5 p-6 md:p-8">
          <div>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
              <StatusPill status={item.status} />
              {/* Beside the tag, where the eye lands before writing anything. */}
              <p className="text-xs font-medium text-muted-foreground">
                {copy.guidelinesPrompt}{" "}
                <button
                  type="button"
                  onClick={onOpenGuidelines}
                  className="font-semibold text-teal underline decoration-teal/40 underline-offset-4 transition-colors hover:text-foreground hover:decoration-foreground/40"
                >
                  {copy.guidelinesLink}
                </button>
              </p>
            </div>
            <h2 className="mt-3 font-display text-2xl text-foreground md:text-3xl">
              {item.momentTitle}
            </h2>
          </div>

          {mode !== "approve" && (
            /* Takes every spare pixel of the column so there is room to write. */
            <div className="flex min-h-0 flex-1 flex-col">
              <label
                htmlFor="caption-text"
                className="font-display text-[0.72rem] sm:text-[0.68rem] uppercase tracking-[0.2em] text-muted-foreground"
              >
                {fieldLabel}
              </label>
              <textarea
                id="caption-text"
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder={
                  mode === "caption"
                    ? "Write the title for this photo."
                    : "Write the corrected title; it replaces the current one."
                }
                className="mt-2 min-h-[12rem] w-full flex-1 resize-none rounded-xl border border-border bg-background/60 px-4 py-3 text-base font-medium leading-relaxed text-foreground focus:border-transparent focus:outline-none focus:ring-2 focus:ring-violet"
              />
            </div>
          )}

          {mode === "approve" && (
            /* Shown, not editable: they are signing off on this exact wording. */
            <div className="flex min-h-0 flex-1 flex-col">
              <span className="font-display text-[0.72rem] sm:text-[0.68rem] uppercase tracking-[0.2em] text-muted-foreground">
                Title
              </span>
              <div className="glass-scrollbar mt-2 min-h-[12rem] flex-1 overflow-y-auto rounded-xl border border-border bg-background/40 px-4 py-3 text-base font-medium leading-relaxed text-foreground">
                {item.caption}
              </div>
            </div>
          )}

          {/* Who acted, and how to reach them: name and mobile number together. */}
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label
                htmlFor="caption-by"
                className="font-display text-[0.72rem] sm:text-[0.68rem] uppercase tracking-[0.2em] text-muted-foreground"
              >
                {byLabel} <span className="text-[#ff9b6a]">*</span>
              </label>
              <input
                id="caption-by"
                value={by}
                onChange={(e) => setBy(e.target.value)}
                placeholder="Your full name"
                className="mt-2 w-full rounded-xl border border-border bg-background/60 px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-transparent focus:outline-none focus:ring-2 focus:ring-violet"
              />
            </div>
            <div>
              <label
                htmlFor="caption-by-phone"
                className="font-display text-[0.72rem] sm:text-[0.68rem] uppercase tracking-[0.2em] text-muted-foreground"
              >
                Mobile number <span className="text-[#ff9b6a]">*</span>
              </label>
              <input
                id="caption-by-phone"
                type="tel"
                inputMode="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="Your mobile number"
                className="mt-2 w-full rounded-xl border border-border bg-background/60 px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-transparent focus:outline-none focus:ring-2 focus:ring-violet"
              />
            </div>
          </div>

          <div>
            <button
              disabled={primaryDisabled}
              onClick={submit}
              className={`w-full rounded-xl py-3.5 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-40 ${
                mode === "correct"
                  ? "border border-teal text-teal transition-colors hover:bg-teal hover:text-[#10281f]"
                  : "spectrum-fill"
              }`}
            >
              {primaryLabel}
            </button>
            {mode === "approve" && (
              <p className="mt-3 text-xs text-muted-foreground">
                Approving locks this title. It can't be edited afterwards.
              </p>
            )}
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
}

/* ---------------- Spectrum team upload ---------------- */

function AddImageModal({
  open,
  onClose,
  onAdd,
}: {
  open: boolean;
  onClose: () => void;
  onAdd: (input: NewCaption) => Promise<void>;
}) {
  const { institution } = usePortalMember();
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [title, setTitle] = useState("");
  const [caption, setCaption] = useState("");
  const [requested, setRequested] = useState<"needs-approval" | "needs-correction">(
    "needs-approval",
  );
  const [preview, setPreview] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const reset = () => {
    setTitle("");
    setCaption("");
    if (preview) URL.revokeObjectURL(preview);
    setPreview(null);
    setFile(null);
    setError("");
    setRequested("needs-approval");
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
          className="fixed inset-0 z-[80] grid place-items-center bg-black/70 p-4 backdrop-blur-md"
        >
          <motion.div
            initial={{ scale: 0.95, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.96, opacity: 0 }}
            transition={{ type: "spring", stiffness: 260, damping: 26 }}
            onClick={(e) => e.stopPropagation()}
            className="spectrum-border glass relative w-full max-w-lg space-y-4 rounded-3xl bg-surface p-6"
          >
            <button
              onClick={onClose}
              aria-label="Close"
              className="absolute right-4 top-4 text-foreground/80 hover:text-foreground"
            >
              <X className="h-5 w-5" />
            </button>
            <h2 className="font-display text-2xl text-foreground">Add Image</h2>
            <p className="text-xs font-medium text-muted-foreground">
              Spectrum team upload · {institution.name}
            </p>

            <button
              onClick={() => fileRef.current?.click()}
              className="flex w-full items-center justify-center gap-3 overflow-hidden rounded-xl border border-dashed border-violet/70 py-6 text-sm font-medium text-muted-foreground transition-colors hover:border-teal hover:text-teal"
            >
              {preview ? (
                <img src={preview} alt="" className="h-28 w-full object-cover" />
              ) : (
                <>
                  <ImagePlus className="h-4 w-4" /> Choose an image
                </>
              )}
            </button>
            <input
              ref={fileRef}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) {
                  setFile(f);
                  setPreview(URL.createObjectURL(f));
                }
              }}
            />

            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Moment name"
              className="w-full rounded-xl border border-border bg-background/60 px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-violet"
            />
            <textarea
              value={caption}
              onChange={(e) => setCaption(e.target.value)}
              rows={3}
              placeholder="Draft title"
              className="w-full resize-none rounded-xl border border-border bg-background/60 px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-violet"
            />

            <div className="flex gap-3">
              {(["needs-approval", "needs-correction"] as const).map((r) => (
                <button
                  key={r}
                  onClick={() => setRequested(r)}
                  className={`spectrum-border flex-1 rounded-full px-4 py-2 text-xs font-semibold transition-colors ${
                    requested === r ? "bg-violet text-foreground" : "text-foreground"
                  }`}
                >
                  {captionStatusLabel[r]}
                </button>
              ))}
            </div>

            <button
              disabled={busy || !title.trim() || !caption.trim() || (hasApi && !file)}
              onClick={async () => {
                setBusy(true);
                setError("");
                try {
                  await onAdd({ file, title: title.trim(), caption: caption.trim(), requested });
                  reset();
                } catch (err) {
                  setError(err instanceof Error ? err.message : "Upload failed");
                } finally {
                  setBusy(false);
                }
              }}
              className="spectrum-fill w-full rounded-xl py-3.5 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-40"
            >
              Add to Workspace
            </button>
            {error && (
              <p role="alert" className="text-center text-xs font-medium text-[#ff9b6a]">
                {error}
              </p>
            )}
            {!hasApi && (
              <p className="text-center text-xs text-muted-foreground">
                Demo upload — nothing is stored; a refresh resets the list.{" "}
                <Link to="/" className="text-teal">
                  Back to site
                </Link>
              </p>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
