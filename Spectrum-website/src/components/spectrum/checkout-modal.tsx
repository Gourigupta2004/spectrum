import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { MessageCircle, Mail, Play, X } from "lucide-react";
import type { Photo, SpectrumEvent, Video } from "@/lib/spectrum-data";
import type { GalleryCopy } from "@/lib/data/defaults";
import { hasApi } from "@/lib/api";
import { payForPhotos, type Order } from "@/lib/data/orders";
import { fill } from "@/lib/text";

const inputClass =
  "w-full rounded-xl border border-border bg-background/60 px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-transparent focus:outline-none focus:ring-2 focus:ring-violet";

const newKey = () =>
  typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`;

export function CheckoutModal({
  open,
  onClose,
  onPaid,
  event,
  copy,
  selected,
  selectedVideos,
  bundle,
  total,
  pricePerPhoto,
  pricePerVideo,
  bundlePrice,
  albumSize,
}: {
  open: boolean;
  onClose: () => void;
  /** Receives the paid order, or null in demo mode. */
  onPaid: (order: Order | null) => void;
  event: SpectrumEvent;
  copy: GalleryCopy;
  selected: Photo[];
  selectedVideos: Video[];
  bundle: boolean;
  total: number;
  pricePerPhoto: number;
  pricePerVideo: number;
  bundlePrice: number;
  /** Every photo in the event — what the bundle buys. Videos are always priced on top. */
  albumSize: number;
}) {
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);

  // One key per distinct basket, so a double click or retry never creates two orders.
  const basket =
    (bundle ? "bundle" : selected.map((p) => p.id).join(",")) +
    "|" +
    selectedVideos.map((v) => v.id).join(",");
  const idempotencyKey = useMemo(() => newKey(), [basket, event.slug, open, attempt]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    if (!open) setError("");
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  const pay = async () => {
    if (!hasApi) {
      onPaid(null);
      return;
    }
    setError("");
    if (!name.trim()) return setError(copy.namePlaceholder);
    // Files go wherever something is filled in: WhatsApp, email, or both.
    if (phone.trim() && phone.replace(/\D/g, "").length < 10)
      return setError(copy.whatsappPlaceholder);
    if (email.trim() && !email.includes("@")) return setError(copy.emailPlaceholder);
    if (!phone.trim() && !email.trim()) return setError(copy.contactRequired);
    setBusy(true);
    try {
      const order = await payForPhotos(
        {
          eventSlug: event.slug,
          photoIds: bundle ? [] : selected.map((p) => p.id),
          videoIds: selectedVideos.map((v) => v.id),
          bundle,
          name: name.trim(),
          phone: phone.trim(),
          email: email.trim(),
          deliverVia: phone.trim() ? "whatsapp" : "email",
          idempotencyKey,
        },
        `${event.name} · ${event.institution}`,
      );
      if (order) onPaid(order);
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : copy.checkoutError);
      setAttempt((n) => n + 1);
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
          className="fixed inset-0 z-[80] grid place-items-center bg-black/70 p-4 backdrop-blur-md"
          onClick={busy ? undefined : onClose}
        >
          <motion.div
            initial={{ scale: 0.94, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.96, opacity: 0 }}
            transition={{ type: "spring", stiffness: 260, damping: 26 }}
            onClick={(e) => e.stopPropagation()}
            className="spectrum-border glass relative grid w-full max-w-3xl gap-0 overflow-hidden rounded-3xl bg-surface md:grid-cols-2"
          >
            <button
              onClick={onClose}
              aria-label="Close"
              className="absolute right-4 top-4 z-10 text-foreground/80 transition-colors hover:text-foreground"
            >
              <X className="h-5 w-5" />
            </button>

            <div className="border-b border-border p-6 md:border-b-0 md:border-r">
              <h3 className="font-display text-lg text-foreground">{copy.summaryHeading}</h3>
              <div className="no-scrollbar mt-4 max-h-56 space-y-3 overflow-y-auto pr-1">
                {bundle ? (
                  <div className="flex items-center justify-between gap-3 text-sm text-foreground">
                    <span>{fill(copy.bundleLine, { photos: albumSize })}</span>
                    <span>₹{bundlePrice}</span>
                  </div>
                ) : (
                  selected.map((m) => (
                    <div key={m.id} className="flex items-center gap-3">
                      <img
                        src={m.thumb || m.image}
                        alt=""
                        className="h-11 w-11 rounded-lg object-cover"
                        draggable={false}
                      />
                      <p className="min-w-0 flex-1 truncate text-sm text-foreground">{m.title}</p>
                      <span className="text-sm text-foreground">₹{pricePerPhoto}</span>
                    </div>
                  ))
                )}
                {selectedVideos.map((v) => (
                  <div key={v.id} className="flex items-center gap-3">
                    <span className="relative h-11 w-11 shrink-0 overflow-hidden rounded-lg bg-secondary">
                      {(v.thumb || v.image) && (
                        <img
                          src={v.thumb || v.image}
                          alt=""
                          className="h-full w-full object-cover"
                          draggable={false}
                        />
                      )}
                      <span className="absolute inset-0 grid place-items-center bg-black/30">
                        <Play className="h-4 w-4 fill-current text-foreground" />
                      </span>
                    </span>
                    <p className="min-w-0 flex-1 truncate text-sm text-foreground">{v.title}</p>
                    <span className="text-sm text-foreground">₹{pricePerVideo}</span>
                  </div>
                ))}
              </div>
              <div className="spectrum-hairline my-4" />
              <div className="flex items-center justify-between font-display text-lg text-foreground">
                <span>{copy.totalLabel}</span>
                <span className="spectrum-text">₹{total}</span>
              </div>
            </div>

            <div className="space-y-4 p-6">
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                autoComplete="name"
                placeholder={copy.namePlaceholder}
                className={inputClass}
              />
              <div className="relative">
                <MessageCircle className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-teal" />
                <input
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  type="tel"
                  autoComplete="tel"
                  placeholder={copy.whatsappPlaceholder}
                  className={`${inputClass} pl-11`}
                />
                <p className="mt-1.5 px-1 text-[0.7rem] text-muted-foreground">
                  {copy.whatsappHint}
                </p>
              </div>
              <div className="relative">
                <Mail className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-teal" />
                <input
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  type="email"
                  autoComplete="email"
                  placeholder={copy.emailPlaceholder}
                  className={`${inputClass} pl-11`}
                />
                <p className="mt-1.5 px-1 text-[0.7rem] text-muted-foreground">{copy.emailHint}</p>
              </div>

              <button
                onClick={pay}
                disabled={busy}
                className="spectrum-fill w-full rounded-xl py-3.5 text-sm font-semibold disabled:cursor-wait disabled:opacity-70"
              >
                {busy ? "Opening payment…" : fill(copy.payButton, { total })}
              </button>
              {error && (
                <p role="alert" className="text-center text-xs font-medium text-[#ff9b6a]">
                  {error}
                </p>
              )}
              {!hasApi && (
                <p className="text-center text-xs text-muted-foreground">
                  Demo checkout — no payment is processed.
                </p>
              )}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
