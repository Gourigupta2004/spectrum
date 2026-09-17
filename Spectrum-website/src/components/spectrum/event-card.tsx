import { Link } from "@tanstack/react-router";
import { motion } from "motion/react";
import type { SpectrumEvent } from "@/lib/spectrum-data";

export function EventCard({
  event,
  index = 0,
  photosLabel = "photos",
  pricePrefix = "From ₹",
}: {
  event: SpectrumEvent;
  index?: number;
  photosLabel?: string;
  pricePrefix?: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 26 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 0.55, delay: index * 0.07 }}
    >
      <Link
        to="/events/$slug"
        params={{ slug: event.slug }}
        className="spectrum-border group relative block aspect-[3/4] overflow-hidden rounded-2xl transition-transform duration-500 hover:-translate-y-1.5"
      >
        {event.image && (
          <img
            src={event.image}
            alt={event.name}
            loading="lazy"
            className="absolute inset-0 h-full w-full object-cover transition-transform duration-700 group-hover:scale-105"
          />
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-[#1C1A22] via-[#1C1A22]/40 to-transparent" />
        <div className="absolute inset-x-0 bottom-0 z-[2] p-5">
          <p className="text-[0.72rem] sm:text-[0.68rem] uppercase tracking-[0.2em] text-teal">
            {event.institution}
          </p>
          <h3 className="mt-1.5 font-display text-xl leading-snug text-foreground">{event.name}</h3>
          <p className="mt-1 text-xs text-muted-foreground">
            {event.date} · {event.photos} {photosLabel}
          </p>
          <span className="spectrum-border mt-3 inline-flex rounded-full px-3 py-1 text-xs text-foreground">
            {pricePrefix}
            {event.pricePerPhoto}
          </span>
        </div>
      </Link>
    </motion.div>
  );
}
