import { motion } from "motion/react";

/**
 * Glossy glass chips: a translucent base, a two-tone brand tint rotated by
 * position, and a specular sheen across the top half with a one-pixel inner
 * light line — the gloss is what makes it read as glass rather than a tinted
 * rectangle. `glass` supplies the backdrop blur; the background is inline
 * because the utility's own background would otherwise win.
 *
 * Informational, not controls — rendered as a list, never as buttons. The hover
 * lift uses Tailwind's `translate` property, which does not collide with the
 * inline `transform` Motion writes for the staggered entrance.
 */
const TINTS: [string, string][] = [
  ["255,201,60", "255,138,61"], // amber -> orange
  ["124,77,224", "214,51,154"], // violet -> magenta
  ["47,191,143", "61,139,255"], // teal -> blue
  ["232,80,58", "214,51,154"], // red -> magenta
  ["61,139,255", "124,77,224"], // blue -> violet
  ["255,138,61", "232,80,58"], // orange -> red
];

const tint = (i: number): string => {
  const [a, b] = TINTS[i % TINTS.length]!;
  return [
    "linear-gradient(180deg, rgba(255,255,255,0.16) 0%, rgba(255,255,255,0.04) 46%, rgba(255,255,255,0) 56%)",
    `radial-gradient(120% 140% at 18% 0%, rgba(${a},0.42), transparent 62%)`,
    `radial-gradient(120% 140% at 88% 100%, rgba(${b},0.34), transparent 62%)`,
    "rgba(28,26,34,0.55)",
  ].join(", ");
};

export function GlassChips({
  items,
  label,
  size = "md",
}: {
  items: readonly string[];
  label: string;
  /** `lg` for pages where the chips are the selling point rather than a summary. */
  size?: "md" | "lg";
}) {
  const sizing =
    size === "lg"
      ? // Large from the tablet breakpoint up; on a phone eight of these stacked
        // one per row filled the first screen, so they fall back to the standard size.
        "rounded-2xl px-5 py-3 text-sm md:rounded-3xl md:px-8 md:py-5 md:text-xl"
      : "rounded-2xl px-5 py-3 text-sm md:text-base";
  return (
    <ul
      aria-label={label}
      className={`flex flex-wrap justify-center ${size === "lg" ? "gap-3 md:gap-5" : "gap-3 md:gap-4"}`}
    >
      {items.map((name, i) => (
        <motion.li
          key={name}
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-40px" }}
          transition={{ duration: 0.5, delay: i * 0.07, ease: [0.22, 1, 0.36, 1] }}
          className={`spectrum-border glass ${sizing} font-medium text-foreground shadow-[inset_0_1px_0_rgba(255,255,255,0.14),0_10px_30px_-16px_rgba(0,0,0,0.7)] transition-transform duration-300 hover:-translate-y-0.5`}
          style={{ background: tint(i) }}
        >
          {name}
        </motion.li>
      ))}
    </ul>
  );
}
