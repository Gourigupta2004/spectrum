import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { motion } from "motion/react";
import { Lock, Check } from "lucide-react";
import { Orb } from "@/components/spectrum/orb";
import { CheckoutModal } from "@/components/spectrum/checkout-modal";
import { SuccessOverlay } from "@/components/spectrum/success-overlay";
import { useSelection } from "@/components/spectrum/selection-context";
import { BUNDLE_PRICE, bundleSavings, galleryEvent, galleryPhotos } from "@/lib/spectrum-data";

/**
 * The watermark is flat translucent type, deliberately with no outline stroke:
 * a stroke in the same translucent colour compounds with the fill where they
 * overlap and reads as an opaque border around every letter — the opposite of
 * a watermark. Weight comes from `font-black` and size alone. The photos
 * themselves are not blurred; this mark is the only preview signal.
 */

export const Route = createFileRoute("/events/$slug")({
  head: () => ({
    meta: [
      { title: "Annual Day 2025 Gallery — Delhi Public School | Spectrum" },
      {
        name: "description",
        content:
          "Browse every photo from Annual Day 2025 at Delhi Public School. Select the ones you love and get full-resolution files instantly.",
      },
      { property: "og:title", content: "Annual Day 2025 Gallery — Spectrum" },
      {
        property: "og:description",
        content: "Select your photos from Annual Day 2025 and own your memories.",
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

  const chosen = useMemo(() => galleryPhotos.filter((m) => selected.includes(m.id)), [selected]);
  const price = bundle ? BUNDLE_PRICE : chosen.length * galleryEvent.pricePerPhoto;

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
            {galleryEvent.date} · {galleryEvent.photos} photos
          </p>
        </div>

        <div
          id="gallery-grid"
          /* Deterrents only: blocks the right-click "save image as" path and drops
             the grid out of print/print-to-PDF. The translucent watermark is the
             real signal that these are previews. */
          onContextMenu={(e) => e.preventDefault()}
          className="no-capture mt-10 grid select-none grid-cols-2 gap-4 md:grid-cols-3"
        >
          {galleryPhotos.map((m, i) => {
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
                  className="undraggable absolute inset-0 h-full w-full object-cover transition-transform duration-700 group-hover:scale-[1.04]"
                />
                <span className="pointer-events-none absolute inset-0 z-[4] grid place-items-center p-3">
                  <span className="rotate-[-20deg] text-center text-2xl font-black uppercase tracking-[0.18em] text-white/50 antialiased md:text-4xl lg:text-5xl">
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
                </span>

                {/* Above the watermark (z-4): the watermark is now large enough to
                    bury this affordance, and it only shows on hover anyway. */}
                <span className="pointer-events-none absolute inset-0 z-[5] grid place-items-center opacity-0 transition-opacity duration-300 group-hover:opacity-100">
                  <span className="spectrum-border glass rounded-full px-4 py-2 text-xs text-foreground">
                    {isSel ? "Selected" : "Select This Photo"}
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
              : `${selected.length} photo${selected.length === 1 ? "" : "s"} selected · ₹${price}`}
          </p>
          <button
            onClick={() => {
              setBundle(true);
              setSelected(galleryPhotos.map((m) => m.id));
            }}
            className="spectrum-border rounded-full px-4 py-2 text-xs text-foreground"
          >
            Full Album Bundle —{bundleSavings > 0 ? ` Save ${bundleSavings}% ·` : ""} ₹
            {BUNDLE_PRICE} for all {galleryEvent.photos} photos
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
        pricePerPhoto={galleryEvent.pricePerPhoto}
        albumSize={galleryEvent.photos}
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
