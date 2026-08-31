import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { motion } from "motion/react";
import { Lock, Check } from "lucide-react";
import { Orb } from "@/components/spectrum/orb";
import { CheckoutModal } from "@/components/spectrum/checkout-modal";
import { SuccessOverlay } from "@/components/spectrum/success-overlay";
import { useSelection } from "@/components/spectrum/selection-context";
import { BUNDLE_PRICE, galleryEvent, moments } from "@/lib/spectrum-data";

/**
 * Watermark weight. `font-black` is already CSS weight 900 — the heaviest the
 * face goes — so extra boldness has to come from glyph size plus an outline
 * stroke, which thickens each stem beyond what any font-weight can.
 */
const WATERMARK_STROKE = "0.045em";

/**
 * Preview blur for gallery tiles. This is a deterrent, not protection: the
 * full-resolution file is still what the browser fetched, so anyone who opens
 * devtools can drop the filter. Real protection is serving a pre-blurred,
 * watermark-baked derivative and keeping the clean file behind the purchase.
 */
const PREVIEW_BLUR = "blur-[3px]";

export const Route = createFileRoute("/events/$slug")({
  head: () => ({
    meta: [
      { title: "Annual Day 2025 Gallery — Delhi Public School | Spectrum" },
      {
        name: "description",
        content:
          "Browse 18 captured moments from Annual Day 2025 at Delhi Public School. Select the moments you love and get full-resolution photos instantly.",
      },
      { property: "og:title", content: "Annual Day 2025 Gallery — Spectrum" },
      {
        property: "og:description",
        content: "Select your moments from Annual Day 2025 and own your memories.",
      },
    ],
  }),
  component: GalleryPage,
});

function GalleryPage() {
  const [selected, setSelected] = useState<string[]>([]);
  const [bundle, setBundle] = useState(false);
  const [open, setOpen] = useState(false);
  const [paid, setPaid] = useState(false);
  const { setCount, setOpenCheckout } = useSelection();

  const chosen = useMemo(() => moments.filter((m) => selected.includes(m.id)), [selected]);
  const photoCount = chosen.reduce((s, m) => s + m.photos, 0);
  const price = bundle ? BUNDLE_PRICE : chosen.length * galleryEvent.pricePerMoment;

  useEffect(() => setCount(selected.length), [selected.length, setCount]);
  useEffect(() => setOpenCheckout(() => setOpen(true)), [setOpenCheckout]);
  useEffect(() => () => setCount(0), [setCount]);

  useEffect(() => {
    const block = (e: Event) => e.preventDefault();
    const el = document.getElementById("gallery-grid");
    el?.addEventListener("contextmenu", block);
    return () => el?.removeEventListener("contextmenu", block);
  }, []);

  const toggle = (id: string) => {
    setBundle(false);
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));
  };

  return (
    <div className="grain relative min-h-screen overflow-x-clip pb-40 pt-28">
      <Orb
        className="right-[-6%] top-6"
        colors={["#2fbf8f", "#8b5cf6"]}
        size={520}
        opacity={0.09}
      />
      <div className="relative z-10 mx-auto max-w-6xl px-6">
        <Link
          to="/events"
          className="text-xs text-muted-foreground transition-colors hover:text-teal"
        >
          ← All Events
        </Link>

        <div className="mt-6">
          <p className="text-[0.68rem] uppercase tracking-[0.22em] text-teal">
            {galleryEvent.institution}
          </p>
          <h1 className="mt-2 font-display text-4xl text-foreground md:text-5xl">
            {galleryEvent.name}
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            {galleryEvent.date} · {galleryEvent.photos} photos · {moments.length} moments
          </p>
        </div>

        <div
          id="gallery-grid"
          /* Deterrents only — see PREVIEW_BLUR. Blocks the right-click "save
             image as" path and drops the grid out of print/print-to-PDF. */
          onContextMenu={(e) => e.preventDefault()}
          className="no-capture mt-10 grid select-none grid-cols-2 gap-4 md:grid-cols-3"
        >
          {moments.map((m, i) => {
            const isSel = selected.includes(m.id);
            return (
              <motion.button
                key={m.id}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-40px" }}
                transition={{ duration: 0.45, delay: (i % 6) * 0.05 }}
                onClick={() => toggle(m.id)}
                className={`group relative aspect-[4/5] overflow-hidden rounded-2xl text-left ${
                  isSel ? "spectrum-border spectrum-border-thick" : ""
                }`}
              >
                <img
                  src={m.image}
                  alt={m.title}
                  loading="lazy"
                  draggable={false}
                  /* Blurred so the moment is still recognisable but the frame is
                     not worth taking; the scale is overscan, so the blur's soft
                     edge is clipped by the tile rather than showing a halo. */
                  className={`undraggable absolute inset-0 h-full w-full scale-[1.08] object-cover transition-transform duration-700 group-hover:scale-[1.12] ${PREVIEW_BLUR}`}
                />
                <span className="pointer-events-none absolute inset-0 z-[4] grid place-items-center p-3">
                  <span
                    style={{ WebkitTextStroke: `${WATERMARK_STROKE} currentColor` }}
                    className="rotate-[-20deg] text-center text-2xl font-black uppercase tracking-[0.18em] text-white antialiased md:text-4xl lg:text-5xl"
                  >
                    Preview Only
                  </span>
                </span>


                <span className="spectrum-fill absolute right-3 top-3 z-[3] grid h-7 w-7 place-items-center rounded-full">
                  <Lock className="h-3.5 w-3.5" />
                </span>

                {isSel && (
                  <span className="absolute left-3 top-3 z-[3] grid h-7 w-7 place-items-center rounded-full bg-teal">
                    <Check className="h-4 w-4 text-[#14231d]" />
                  </span>
                )}

                {/* shimmer */}
                <span className="pointer-events-none absolute inset-0 overflow-hidden">
                  <span
                    className="absolute inset-y-0 -left-1/3 w-1/3 opacity-0 group-hover:opacity-100"
                    style={{
                      background:
                        "linear-gradient(90deg, transparent, rgba(247,194,31,0.25), rgba(139,92,246,0.28), transparent)",
                      animation: "shimmer-sweep 1.1s ease-out",
                    }}
                  />
                </span>

                <span className="pointer-events-none absolute inset-x-0 bottom-0 z-[2] bg-gradient-to-t from-[#1C1A22] via-[#1C1A22]/60 to-transparent p-4">
                  <span className="block font-display text-sm text-foreground">{m.title}</span>
                  <span className="mt-0.5 block text-[0.6rem] uppercase tracking-[0.16em] text-teal">
                    {m.photos} photos in this moment
                  </span>
                </span>

                {/* Above the watermark (z-4): the watermark is now large enough to
                    bury this affordance, and it only shows on hover anyway. */}
                <span className="pointer-events-none absolute inset-0 z-[5] grid place-items-center opacity-0 transition-opacity duration-300 group-hover:opacity-100">
                  <span className="spectrum-border glass rounded-full px-4 py-2 text-xs text-foreground">
                    {isSel ? "Selected" : "Select This Moment"}
                  </span>
                </span>
              </motion.button>
            );
          })}
        </div>
      </div>

      {/* STICKY BAR */}
      <div className="fixed inset-x-0 bottom-0 z-40 bg-surface/95 backdrop-blur-xl">
        <div className="spectrum-hairline w-full" />
        <div className="mx-auto flex max-w-6xl flex-col items-center gap-3 px-6 py-4 text-center md:flex-row md:justify-between md:text-left">
          <p className="text-sm text-foreground">
            {bundle
              ? `Full album selected · ${galleryEvent.photos} photos · ₹${BUNDLE_PRICE}`
              : `${selected.length} moment${selected.length === 1 ? "" : "s"} selected · ${photoCount} photos · ₹${price}`}
          </p>
          <button
            onClick={() => {
              setBundle(true);
              setSelected(moments.map((m) => m.id));
            }}
            className="spectrum-border rounded-full px-4 py-2 text-xs text-foreground"
          >
            Full Album Bundle — Save 43% · ₹{BUNDLE_PRICE} for all {galleryEvent.photos} photos
          </button>
          <button
            disabled={selected.length === 0}
            onClick={() => setOpen(true)}
            className="spectrum-fill rounded-full px-6 py-3 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-40"
          >
            Pay &amp; Get Photos →
          </button>
        </div>
      </div>

      <CheckoutModal
        open={open}
        onClose={() => setOpen(false)}
        onPaid={() => {
          setOpen(false);
          setPaid(true);
        }}
        selected={chosen}
        bundle={bundle}
        total={price}
      />

      {paid && <SuccessOverlay onClose={() => setPaid(false)} />}
    </div>
  );
}
