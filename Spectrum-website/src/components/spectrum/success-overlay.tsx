import { Link } from "@tanstack/react-router";
import { motion } from "motion/react";
import type { GalleryCopy } from "@/lib/data/defaults";
import type { Order } from "@/lib/data/orders";

export function SuccessOverlay({
  onClose,
  copy,
  order,
}: {
  onClose: () => void;
  copy: GalleryCopy;
  /** The paid order; null in demo mode. */
  order: Order | null;
}) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="fixed inset-0 z-[90] grid place-items-center overflow-hidden bg-background px-6 text-center"
    >
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(120% 80% at 15% 20%, rgba(247,194,31,0.14), transparent 60%), radial-gradient(120% 90% at 85% 25%, rgba(185,76,158,0.13), transparent 62%), radial-gradient(130% 90% at 50% 105%, rgba(139,92,246,0.14), transparent 65%), radial-gradient(100% 70% at 50% 50%, rgba(47,191,143,0.08), transparent 70%)",
        }}
      />
      {[0, 2.4].map((d) => (
        <span
          key={d}
          aria-hidden
          className="pointer-events-none absolute h-[140vmax] w-[140vmax] rounded-full"
          style={{
            background:
              "radial-gradient(circle, rgba(247,194,31,0.05), rgba(139,92,246,0.05) 45%, transparent 72%)",
            animation: `burst-pulse 9s ease-out ${d}s infinite`,
          }}
        />
      ))}

      <div className="relative">
        <div className="spectrum-fill mx-auto grid h-20 w-20 place-items-center rounded-full">
          <svg viewBox="0 0 52 52" className="h-10 w-10">
            <path
              d="M14 27l8 8 16-17"
              fill="none"
              stroke="#fff"
              strokeWidth="4"
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeDasharray="48"
              strokeDashoffset="48"
              style={{ animation: "draw-check 0.8s ease-out 0.25s forwards" }}
            />
          </svg>
        </div>
        <h2 className="mt-8 font-display text-3xl text-foreground md:text-4xl">
          {copy.successTitle}
        </h2>
        <p className="mx-auto mt-4 max-w-md text-sm font-medium text-foreground/90">
          {order?.deliverVia === "email" ? copy.successBodyEmail : copy.successBodyWhatsapp}
        </p>
        <p className="mt-3 text-xs text-muted-foreground">{copy.successNote}</p>
        <Link
          to="/events"
          onClick={onClose}
          className="mx-auto mt-6 block w-fit border-b border-transparent text-sm text-foreground transition-colors hover:border-teal"
        >
          {copy.successBack}
        </Link>
      </div>
    </motion.div>
  );
}
