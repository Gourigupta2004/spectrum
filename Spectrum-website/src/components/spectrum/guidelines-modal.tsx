import { useEffect } from "react";
import { AnimatePresence, motion } from "motion/react";
import { BookOpen, X } from "lucide-react";
import type { Guidelines } from "@/lib/guidelines";

/** One pointer per line in the admin; blank lines are ignored. */
const pointers = (text: string): string[] =>
  text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

/**
 * A section's guidelines, in a window that takes three quarters of the screen
 * on anything larger than a phone (a phone gets nearly the whole screen, since
 * three quarters of one is too narrow to read). Closes from the cross, the
 * "got it" button, the backdrop or Escape. Sits above the caption editor so it
 * can be opened from inside it.
 */
export function GuidelinesModal({
  open,
  onClose,
  content,
}: {
  open: boolean;
  onClose: () => void;
  content: Guidelines;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const points = pointers(content.points);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
          className="fixed inset-0 z-[90] grid place-items-center bg-black/70 p-4 backdrop-blur-md"
        >
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-labelledby="guidelines-title"
            initial={{ scale: 0.95, opacity: 0, y: 12 }}
            animate={{ scale: 1, opacity: 1, y: 0 }}
            exit={{ scale: 0.96, opacity: 0 }}
            transition={{ type: "spring", stiffness: 260, damping: 26 }}
            onClick={(e) => e.stopPropagation()}
            className="spectrum-border glass relative flex h-[88svh] w-full flex-col overflow-hidden rounded-3xl bg-surface sm:h-[75vh] sm:w-[75vw]"
          >
            <button
              type="button"
              onClick={onClose}
              aria-label="Close guidelines"
              className="absolute right-4 top-4 z-10 grid h-10 w-10 place-items-center rounded-full bg-black/40 text-white/85 backdrop-blur-md transition-colors hover:text-white focus:outline-none focus:ring-2 focus:ring-violet"
            >
              <X className="h-5 w-5" />
            </button>

            <div className="glass-scrollbar min-h-0 flex-1 overflow-y-auto px-6 pb-6 pt-8 sm:px-10 sm:pb-8 sm:pt-10 md:px-14">
              <span className="spectrum-fill inline-grid h-11 w-11 place-items-center rounded-full">
                <BookOpen className="h-5 w-5" />
              </span>
              <h2
                id="guidelines-title"
                className="mt-5 font-display text-3xl text-foreground md:text-4xl"
              >
                {content.title}
              </h2>
              {content.intro && (
                <p className="mt-4 text-base font-medium leading-relaxed text-muted-foreground">
                  {content.intro}
                </p>
              )}

              {points.length > 0 && (
                <ul className="mt-8 space-y-4">
                  {points.map((point, i) => (
                    <li key={i} className="flex gap-4">
                      {/* Centred on the first line (leading-relaxed: 1.625rem). */}
                      <span
                        aria-hidden
                        className="spectrum-fill mt-[0.5625rem] h-2 w-2 shrink-0 rounded-full"
                      />
                      <span className="text-base leading-relaxed text-foreground">{point}</span>
                    </li>
                  ))}
                </ul>
              )}

              {content.outro && (
                <p className="mt-8 border-l-2 border-teal pl-4 text-2xl font-medium leading-snug text-muted-foreground">
                  {content.outro}
                </p>
              )}
            </div>

            <div className="shrink-0 border-t border-border px-6 py-4 sm:px-10 md:px-14">
              <button
                type="button"
                onClick={onClose}
                className="spectrum-fill rounded-full px-6 py-2.5 text-sm font-semibold"
              >
                {content.dismiss}
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
