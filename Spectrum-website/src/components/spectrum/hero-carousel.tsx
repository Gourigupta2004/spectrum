import { useCallback, useEffect, useRef, useState } from "react";
import type { HeroSlide } from "@/lib/data/pages";

/**
 * The coverflow geometry, which cannot be one set of numbers.
 *
 * Desktop has room for a deep stack: narrow cards, a wide spread and three
 * neighbours falling away on each side. Reused as-is on a phone that stack runs
 * straight off both edges — the second and third cards sit entirely outside the
 * viewport and the ones that remain are sliced by the screen edge, which reads
 * as a broken layout rather than a carousel.
 *
 * So a phone gets its own proportions: one neighbour each side, a card wide
 * enough to be the subject of the screen, a tighter spread and a gentler tilt.
 * The neighbours then peek in from both sides and nothing is cut off.
 */
type Geometry = {
  /** Card width, as a CSS length. */
  card: string;
  /** Distance between neighbours, as a fraction of the card's width. */
  spread: number;
  /** How many cards stay visible on each side of the active one. */
  depth: number;
  /** Degrees each step is turned away from the viewer. */
  tilt: number;
  /** How much each step shrinks, and how much it dims. */
  shrink: number;
  fade: number;
};

const PHONE: Geometry = { card: "62vw", spread: 0.46, depth: 1, tilt: 17, shrink: 0.1, fade: 0.1 };
const WIDE: Geometry = {
  card: "clamp(180px,22vw,300px)",
  spread: 0.58,
  depth: 3,
  tilt: 26,
  shrink: 0.13,
  fade: 0.12,
};

/**
 * Matched on mount rather than during render: the homepage is server rendered,
 * and the server has no viewport. The intro overlay covers this area for its
 * whole run, so the first-paint correction is never seen.
 */
function useGeometry(): Geometry {
  const [geometry, setGeometry] = useState<Geometry>(WIDE);
  useEffect(() => {
    const query = window.matchMedia("(max-width: 639px)");
    const apply = () => setGeometry(query.matches ? PHONE : WIDE);
    apply();
    query.addEventListener("change", apply);
    return () => query.removeEventListener("change", apply);
  }, []);
  return geometry;
}

export function HeroCarousel({ slides: heroSlides }: { slides: HeroSlide[] }) {
  const geometry = useGeometry();
  const [active, setActive] = useState(() => Math.min(2, Math.max(0, heroSlides.length - 1)));
  const [paused, setPaused] = useState(false);
  const drag = useRef<{ x: number; moved: boolean } | null>(null);

  const go = useCallback(
    (dir: number) => {
      if (!heroSlides.length) return;
      setActive((a) => (a + dir + heroSlides.length) % heroSlides.length);
    },
    [heroSlides.length],
  );

  useEffect(() => {
    if (paused || heroSlides.length < 2) return;
    const t = setInterval(() => go(1), 3600);
    return () => clearInterval(t);
  }, [go, paused, heroSlides.length]);

  const onDown = (x: number) => {
    drag.current = { x, moved: false };
    setPaused(true);
  };
  const onMove = (x: number) => {
    if (!drag.current || drag.current.moved) return;
    const dx = x - drag.current.x;
    if (Math.abs(dx) > 44) {
      go(dx < 0 ? 1 : -1);
      drag.current.moved = true;
    }
  };
  const onUp = () => {
    drag.current = null;
    setTimeout(() => setPaused(false), 1200);
  };

  return (
    <div
      className="relative h-[38vh] w-full select-none sm:h-[42vh] md:h-[46vh]"
      style={{ perspective: "1600px" }}
      onMouseDown={(e) => onDown(e.clientX)}
      onMouseMove={(e) => onMove(e.clientX)}
      onMouseUp={onUp}
      onMouseLeave={onUp}
      onTouchStart={(e) => onDown(e.touches[0]!.clientX)}
      onTouchMove={(e) => onMove(e.touches[0]!.clientX)}
      onTouchEnd={onUp}
    >
      {heroSlides.map((s, i) => {
        const n = heroSlides.length;
        let offset = i - active;
        if (offset > n / 2) offset -= n;
        if (offset < -n / 2) offset += n;
        const abs = Math.abs(offset);
        const hidden = abs > geometry.depth;
        return (
          <button
            key={s.id}
            onClick={() => setActive(i)}
            aria-label={s.caption}
            tabIndex={hidden ? -1 : 0}
            className="absolute left-1/2 top-1/2 h-full rounded-2xl transition-all duration-700 ease-out"
            style={{
              width: geometry.card,
              transform: `translate(-50%,-50%) translateX(${offset * geometry.spread * 100}%) scale(${
                1 - abs * geometry.shrink
              }) rotateY(${offset * -geometry.tilt}deg)`,
              opacity: hidden ? 0 : 1 - abs * geometry.fade,
              zIndex: 20 - abs,
              pointerEvents: hidden ? "none" : "auto",
            }}
          >
            <span className="spectrum-border absolute inset-0 block overflow-hidden rounded-2xl shadow-[0_30px_70px_-20px_rgba(0,0,0,0.85)]">
              {s.src && (
                <img
                  src={s.src}
                  alt={s.caption}
                  draggable={false}
                  className="undraggable h-full w-full rounded-2xl object-cover"
                />
              )}
              {abs === 0 && (
                <span className="absolute inset-x-0 bottom-0 z-[2] bg-gradient-to-t from-[#1C1A22] to-transparent p-3 text-left font-display text-[0.8rem] font-semibold text-foreground sm:p-4 sm:text-sm">
                  {s.caption}
                </span>
              )}
            </span>
          </button>
        );
      })}
    </div>
  );
}
