import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ImagePlus, LogOut, Plus, RefreshCw, X } from "lucide-react";
import { Orb } from "@/components/spectrum/orb";
import { StatusPill } from "@/components/spectrum/status-pill";
import {
  captionItems as seedItems,
  captionStatusLabel,
  portalInstitution,
  todayLabel,
  type CaptionItem,
  type CaptionStatus,
} from "@/lib/caption-data";

export const Route = createFileRoute("/portal")({
  head: () => ({
    meta: [
      { title: "Institution Portal — Spectrum Caption Workspace" },
      {
        name: "description",
        content:
          "Institution sign-in for the Spectrum caption workspace — review, approve and correct event photo captions.",
      },
      { property: "og:title", content: "Institution Portal — Spectrum" },
      {
        property: "og:description",
        content: "Review, approve and correct Spectrum event photo captions.",
      },
    ],
  }),
  component: PortalPage,
});

const tabs: ("All" | CaptionStatus)[] = [
  "All",
  "needs-caption",
  "needs-approval",
  "needs-correction",
  "final-approval",
  "approved",
  "corrected",
];

function PortalPage() {
  const [signedIn, setSignedIn] = useState(false);
  return signedIn ? (
    <Workspace onSignOut={() => setSignedIn(false)} />
  ) : (
    <LoginScreen onLogin={() => setSignedIn(true)} />
  );
}

/* ---------------- Login (decorative) ---------------- */

function LoginScreen({ onLogin }: { onLogin: () => void }) {
  return (
    <div className="grain relative grid min-h-screen place-items-center overflow-x-clip px-4 py-28">
      <Orb className="left-[-10%] top-16" colors={["#7c4de0", "#d6339a"]} size={520} opacity={0.1} />
      <Orb className="right-[-8%] bottom-10" colors={["#2fbf8f", "#ffc93c"]} size={460} opacity={0.08} />

      <motion.div
        initial={{ opacity: 0, y: 18, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ type: "spring", stiffness: 240, damping: 26 }}
        className="spectrum-border glass relative z-10 w-full max-w-md overflow-hidden rounded-3xl bg-surface p-8"
      >
        <img
          src="/spectrum-logo-light.png"
          alt="Spectrum"
          className="h-7 w-auto"
          draggable={false}
        />
        <p className="mt-6 font-display text-xs uppercase tracking-[0.24em] text-muted-foreground">
          Institution Login
        </p>
        <h1 className="mt-2 font-display text-3xl text-foreground">
          {portalInstitution.name}
        </h1>
        <p className="mt-1 text-sm font-medium text-muted-foreground">
          {portalInstitution.city} · Caption Workspace
        </p>

        <form
          className="mt-7 space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            onLogin();
          }}
        >
          <input
            placeholder="Institution ID"
            defaultValue="dps-newdelhi"
            className="w-full rounded-xl border border-border bg-background/60 px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-transparent focus:outline-none focus:ring-2 focus:ring-violet"
          />
          <input
            type="password"
            placeholder="Password"
            defaultValue="demo"
            className="w-full rounded-xl border border-border bg-background/60 px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-transparent focus:outline-none focus:ring-2 focus:ring-violet"
          />
          <button type="submit" className="spectrum-fill w-full rounded-xl py-3.5 text-sm font-semibold">
            Log In →
          </button>
        </form>
        <p className="mt-4 text-center text-xs text-muted-foreground">
          Demo access — no real authentication is performed.
        </p>
      </motion.div>
    </div>
  );
}

/* ---------------- Workspace ---------------- */

function Workspace({ onSignOut }: { onSignOut: () => void }) {
  const navigate = useNavigate();
  const [items, setItems] = useState<CaptionItem[]>(seedItems);
  const [tab, setTab] = useState<(typeof tabs)[number]>("All");
  const [openId, setOpenId] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);

  const list = useMemo(
    () => (tab === "All" ? items : items.filter((i) => i.status === tab)),
    [items, tab],
  );
  const active = items.find((i) => i.id === openId) ?? null;

  const replaceImage = (id: string, image: string) => {
    const previous = items.find((i) => i.id === id)?.image;
    setItems((prev) => prev.map((i) => (i.id === id ? { ...i, image } : i)));
    // Only a URL we minted is ours to release, and only once nothing points at
    // it any more. Revoking when the editor closed broke the photo on reopen:
    // the item outlives the editor, so a fresh <img> re-resolved a dead URL.
    if (previous?.startsWith("blob:")) URL.revokeObjectURL(previous);
  };

  const resolve = (id: string, status: CaptionStatus, caption: string, by: string) =>
    setItems((prev) =>
      prev.map((i) =>
        i.id === id ? { ...i, status, caption, actionBy: by, updatedAt: todayLabel() } : i,
      ),
    );

  return (
    <div className="grain relative min-h-screen overflow-x-clip pb-24 pt-28">
      <Orb className="right-[-10%] top-24" colors={["#7c4de0", "#2fbf8f"]} size={520} opacity={0.08} />

      <div className="relative z-10 mx-auto max-w-6xl px-6">
        {/* institution header */}
        <div className="spectrum-border glass flex flex-wrap items-center justify-between gap-4 rounded-2xl px-5 py-4">
          <div>
            <p className="font-display text-[0.68rem] uppercase tracking-[0.24em] text-muted-foreground">
              Signed in as
            </p>
            <p className="font-display text-lg font-semibold text-foreground">
              {portalInstitution.name}
            </p>
          </div>
          <button
            onClick={() => {
              onSignOut();
              navigate({ to: "/" });
            }}
            className="inline-flex items-center gap-2 rounded-full border border-violet/70 px-4 py-2 text-xs font-semibold text-foreground transition-colors hover:border-teal hover:text-teal"
          >
            <LogOut className="h-3.5 w-3.5" /> Sign Out
          </button>
        </div>

        <div className="mt-10 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="font-display text-4xl text-foreground md:text-5xl">
              Caption Workspace
            </h1>
            <p className="mt-2 text-sm font-medium text-muted-foreground">
              {portalInstitution.event} · {items.length} images awaiting your review
            </p>
          </div>
          <button
            onClick={() => setAdding(true)}
            className="spectrum-fill inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-xs font-semibold"
          >
            <Plus className="h-4 w-4" /> Add Image
          </button>
        </div>

        {/* status tabs */}
        <div className="no-scrollbar mt-8 flex gap-3 overflow-x-auto pb-2">
          {tabs.map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`spectrum-border shrink-0 rounded-full px-5 py-2 text-xs font-semibold transition-colors ${
                tab === t ? "bg-violet text-foreground" : "text-foreground"
              }`}
            >
              {t === "All" ? "All" : captionStatusLabel[t]}
            </button>
          ))}
        </div>

        {/* grid */}
        <div className="mt-8 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {list.map((item) => (
            <motion.button
              key={item.id}
              layout
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              onClick={() => setOpenId(item.id)}
              className="spectrum-border group overflow-hidden rounded-2xl bg-surface text-left transition-transform hover:-translate-y-1"
            >
              <div className="relative aspect-[4/3] overflow-hidden">
                <img
                  src={item.image}
                  alt={item.momentTitle}
                  loading="lazy"
                  draggable={false}
                  className="h-full w-full object-cover transition-transform duration-700 group-hover:scale-105"
                />
                <div className="absolute inset-x-0 bottom-0 h-20 bg-gradient-to-t from-black/70 to-transparent" />
                <StatusPill status={item.status} className="absolute left-3 top-3" />
              </div>
              <div className="p-4">
                <p className="font-display text-base font-semibold text-foreground">
                  {item.momentTitle}
                </p>
                {item.caption ? (
                  <p className="mt-1 line-clamp-2 text-xs font-medium text-muted-foreground">
                    {item.caption}
                  </p>
                ) : (
                  <p className="mt-1 text-xs font-medium italic text-muted-foreground/70">
                    No caption yet
                  </p>
                )}
                <p className="mt-3 text-[0.68rem] uppercase tracking-[0.14em] text-muted-foreground">
                  Updated {item.updatedAt}
                </p>
              </div>
            </motion.button>
          ))}
        </div>

        {list.length === 0 && (
          <p className="mt-16 text-center text-sm text-muted-foreground">
            No images in this status yet.
          </p>
        )}
      </div>

      <CaptionEditor
        item={active}
        onClose={() => setOpenId(null)}
        onResolve={resolve}
        onReplaceImage={replaceImage}
      />
      <AddImageModal
        open={adding}
        onClose={() => setAdding(false)}
        onAdd={(item) => {
          setItems((prev) => [item, ...prev]);
          setAdding(false);
        }}
      />
    </div>
  );
}

/* ---------------- Caption editor overlay ---------------- */

function CaptionEditor({
  item,
  onClose,
  onResolve,
  onReplaceImage,
}: {
  item: CaptionItem | null;
  onClose: () => void;
  onResolve: (id: string, status: CaptionStatus, caption: string, by: string) => void;
  onReplaceImage: (id: string, image: string) => void;
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
}: {
  item: CaptionItem;
  onClose: () => void;
  onResolve: (id: string, status: CaptionStatus, caption: string, by: string) => void;
  onReplaceImage: (id: string, image: string) => void;
}) {
  // Left blank on purpose: the current caption is already on the card in the
  // listing, so pre-filling it only invited an accidental edit. Blank now means
  // "no correction offered", which is what gates the two actions below.
  const [caption, setCaption] = useState("");
  const [by, setBy] = useState(item.actionBy ?? "");
  const photoRef = useRef<HTMLInputElement>(null);
  const hasCorrection = caption.trim().length > 0;
  const canAct = by.trim().length > 1;
  /*
   * Driven by the live status rather than `requested`: `requested` records what
   * Spectrum first asked and never changes, so once an item is actioned it would
   * keep offering the same controls.
   *   caption — no text exists yet; the institution writes it, nothing to approve
   *   final   — sign-off only; correcting is not on offer at this stage
   *   review  — the original flow: blank box approves, typed box corrects
   */
  const mode =
    item.status === "needs-caption"
      ? "caption"
      : item.status === "final-approval"
        ? "final"
        : "review";

  return (
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
        className="spectrum-border glass relative grid max-h-[88vh] w-full max-w-4xl overflow-y-auto rounded-3xl bg-surface md:grid-cols-2"
      >
        <button
          onClick={onClose}
          aria-label="Close"
          className="absolute right-4 top-4 z-10 text-foreground/80 transition-colors hover:text-foreground"
        >
          <X className="h-5 w-5" />
        </button>

        <div className="group relative min-h-52 md:min-h-full">
          <img
            src={item.image}
            alt={item.momentTitle}
            draggable={false}
            className="h-full max-h-[40vh] w-full object-cover md:max-h-none"
          />

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

          <input
            ref={photoRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (!f) return;
              onReplaceImage(item.id, URL.createObjectURL(f));
              // Let the same file be picked again after an accidental replace.
              e.target.value = "";
            }}
          />
        </div>

        <div className="space-y-5 p-6">
          <div>
            <StatusPill status={item.status} />
            <h2 className="mt-3 font-display text-2xl text-foreground">{item.momentTitle}</h2>
            <p className="mt-1 text-xs font-medium text-muted-foreground">
              Spectrum requested: {captionStatusLabel[item.requested]}
            </p>
          </div>

          <div>
            <label className="font-display text-[0.68rem] uppercase tracking-[0.2em] text-muted-foreground">
              {mode === "caption"
                ? "Caption"
                : mode === "final"
                  ? "Final Caption"
                  : "Corrected Caption"}
            </label>
            {mode === "final" ? (
              /* Shown, not editable: they are signing off on this exact wording,
                 so it has to be in front of them — but there is no correction on
                 offer here, and an input would imply otherwise. */
              <p className="mt-2 rounded-xl border border-border bg-background/40 px-4 py-3 text-sm font-medium text-foreground">
                {item.caption}
              </p>
            ) : (
              <textarea
                value={caption}
                onChange={(e) => setCaption(e.target.value)}
                placeholder={
                  mode === "caption"
                    ? "Write the caption for this photo."
                    : "Type a correction for the caption or leave blank to approve the current one."
                }
                rows={4}
                className="mt-2 w-full resize-none rounded-xl border border-border bg-background/60 px-4 py-3 text-sm font-medium text-foreground focus:border-transparent focus:outline-none focus:ring-2 focus:ring-violet"
              />
            )}
          </div>

          <div>
            <label className="font-display text-[0.68rem] uppercase tracking-[0.2em] text-muted-foreground">
              {mode === "caption"
                ? "Caption written by"
                : mode === "final"
                  ? "Approved by"
                  : "Approved / Corrected by"}{" "}
              <span className="text-[#ff9b6a]">*</span>
            </label>
            <input
              value={by}
              onChange={(e) => setBy(e.target.value)}
              placeholder="Your full name"
              className="mt-2 w-full rounded-xl border border-border bg-background/60 px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-transparent focus:outline-none focus:ring-2 focus:ring-violet"
            />
          </div>

          <div className="flex flex-wrap gap-3">
            {/* Sign-off only — deliberately no correction control here. */}
            {mode === "final" && (
              <button
                disabled={!canAct}
                onClick={() => {
                  onResolve(item.id, "approved", item.caption, by.trim());
                  onClose();
                }}
                className="spectrum-fill flex-1 rounded-xl py-3 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-40"
              >
                Approve Caption
              </button>
            )}

            {/* First caption for this photo — there is nothing to approve yet. */}
            {mode === "caption" && (
              <button
                disabled={!canAct || !hasCorrection}
                onClick={() => {
                  onResolve(item.id, "corrected", caption.trim(), by.trim());
                  onClose();
                }}
                className="spectrum-fill flex-1 rounded-xl py-3 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-40"
              >
                Save Caption
              </button>
            )}

            {mode === "review" && (
              <>
                {item.requested === "needs-approval" && !hasCorrection && (
                  <button
                    disabled={!canAct}
                    onClick={() => {
                      onResolve(item.id, "approved", item.caption, by.trim());
                      onClose();
                    }}
                    className="spectrum-fill flex-1 rounded-xl py-3 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    Approve Caption
                  </button>
                )}
                <button
                  disabled={!canAct || !hasCorrection}
                  onClick={() => {
                    onResolve(item.id, "corrected", caption.trim(), by.trim());
                    onClose();
                  }}
                  className="flex-1 rounded-xl border border-teal py-3 text-sm font-semibold text-teal transition-colors hover:bg-teal hover:text-[#10281f] disabled:cursor-not-allowed disabled:opacity-40"
                >
                  Save Correction
                </button>
              </>
            )}
          </div>

          {!canAct && (
            <p className="text-xs text-muted-foreground">
              {mode === "caption"
                ? "Enter your name to save this caption."
                : mode === "final"
                  ? "Enter your name to approve this caption."
                  : "Enter your name to approve or submit a correction."}
            </p>
          )}
          {canAct && !hasCorrection && mode === "caption" && (
            <p className="text-xs text-muted-foreground">Write a caption to save it.</p>
          )}
          {canAct && !hasCorrection && mode === "review" && item.requested !== "needs-approval" && (
            <p className="text-xs text-muted-foreground">Type a corrected caption to save it.</p>
          )}
          <p className="text-xs text-muted-foreground">
            Last updated {item.updatedAt}
            {item.actionBy ? ` · by ${item.actionBy}` : ""}
          </p>
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
  onAdd: (item: CaptionItem) => void;
}) {
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
    setPreview(null);
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
              Spectrum team upload · {portalInstitution.name}
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
                if (f) setPreview(URL.createObjectURL(f));
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
              placeholder="Draft caption"
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
              disabled={!title.trim() || !caption.trim()}
              onClick={() => {
                onAdd({
                  id: `c-${Date.now()}`,
                  momentTitle: title.trim(),
                  image: preview ?? seedItems[0]!.image,
                  caption: caption.trim(),
                  requested,
                  status: requested,
                  updatedAt: todayLabel(),
                });
                reset();
              }}
              className="spectrum-fill w-full rounded-xl py-3.5 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-40"
            >
              Add to Workspace
            </button>
            <p className="text-center text-xs text-muted-foreground">
              Demo upload — nothing is stored; a refresh resets the list.{" "}
              <Link to="/" className="text-teal">
                Back to site
              </Link>
            </p>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
