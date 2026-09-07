import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { MessageCircle, Mail, X } from "lucide-react";
import { BUNDLE_PRICE, type Photo } from "@/lib/spectrum-data";

export function CheckoutModal({
  open,
  onClose,
  onPaid,
  selected,
  bundle,
  total,
  pricePerPhoto,
  albumSize,
}: {
  open: boolean;
  onClose: () => void;
  onPaid: () => void;
  selected: Photo[];
  bundle: boolean;
  total: number;
  pricePerPhoto: number;
  /** Every photo in the event — what the bundle buys. */
  albumSize: number;
}) {
  const [whatsapp, setWhatsapp] = useState(true);

  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-[80] grid place-items-center bg-black/70 p-4 backdrop-blur-md"
          onClick={onClose}
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
              <h3 className="font-display text-lg text-foreground">Order Summary</h3>
              <div className="no-scrollbar mt-4 max-h-56 space-y-3 overflow-y-auto pr-1">
                {bundle ? (
                  <div className="flex items-center justify-between gap-3 text-sm text-foreground">
                    <span>Full Album Bundle — all {albumSize} photos</span>
                    <span>₹{BUNDLE_PRICE}</span>
                  </div>
                ) : (
                  selected.map((m) => (
                    <div key={m.id} className="flex items-center gap-3">
                      <img
                        src={m.image}
                        alt=""
                        className="h-11 w-11 rounded-lg object-cover"
                        draggable={false}
                      />
                      <p className="min-w-0 flex-1 truncate text-sm text-foreground">{m.title}</p>
                      <span className="text-sm text-foreground">₹{pricePerPhoto}</span>
                    </div>
                  ))
                )}
              </div>
              <div className="spectrum-hairline my-4" />
              <div className="flex items-center justify-between font-display text-lg text-foreground">
                <span>Total</span>
                <span className="spectrum-text">₹{total}</span>
              </div>
            </div>

            <div className="space-y-4 p-6">
              <input
                placeholder="Your Name"
                className="w-full rounded-xl border border-border bg-background/60 px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-transparent focus:outline-none focus:ring-2 focus:ring-violet"
              />
              <div className="relative">
                <MessageCircle className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-teal" />
                <input
                  placeholder="WhatsApp Number"
                  className="w-full rounded-xl border border-border bg-background/60 py-3 pl-11 pr-4 text-sm text-foreground placeholder:text-muted-foreground focus:border-transparent focus:outline-none focus:ring-2 focus:ring-violet"
                />
              </div>
              <div className="relative">
                <Mail className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-teal" />
                <input
                  placeholder="Email Address"
                  className="w-full rounded-xl border border-border bg-background/60 py-3 pl-11 pr-4 text-sm text-foreground placeholder:text-muted-foreground focus:border-transparent focus:outline-none focus:ring-2 focus:ring-violet"
                />
              </div>

              <div className="flex items-center justify-between text-sm text-foreground">
                <span>Deliver via {whatsapp ? "WhatsApp" : "Email"}</span>
                <button
                  onClick={() => setWhatsapp((v) => !v)}
                  aria-label="Toggle delivery method"
                  className={`relative h-6 w-11 rounded-full transition-colors ${
                    whatsapp ? "bg-violet" : "bg-secondary"
                  }`}
                >
                  <span
                    className={`absolute top-0.5 h-5 w-5 rounded-full bg-foreground transition-all ${
                      whatsapp ? "left-[1.4rem]" : "left-0.5"
                    }`}
                  />
                </button>
              </div>

              <button
                onClick={onPaid}
                className="spectrum-fill w-full rounded-xl py-3.5 text-sm font-semibold"
              >
                Pay ₹{total} with Razorpay →
              </button>
              <p className="text-center text-xs text-muted-foreground">
                Demo checkout — no payment is processed.
              </p>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
