import { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { useIntro } from "./intro-context";

const INTRO_WEBM = "/spr-intro.webm";
const INTRO_MP4 = "/spr-intro.mp4";

/** Stage background: a touch deeper than the site base (#221F29). */
const STAGE_BG = "#1B1922";

/**
 * Position of the mark is non-negotiable, so the cut is bounded by where the S
 * is still centred rather than by where the landing flare has fully decayed.
 * Measured centroid holds at -0.4% of frame width through 2.30s and is still
 * only -0.58% at 2.43s, then falls away fast (-1.9% at 2.45s, -9.2% by 2.65s)
 * as the mark clears room for the wordmark. 2.42s is therefore the latest frame
 * that is still dead centre; it buys a modest drop in flare (frame luma 11 -> 10)
 * for no visible shift. Anything later trades centring for brightness, which is
 * the wrong trade here.
 */
const CUT_AT = 2.42;

/**
 * The sequence after the cut:
 *
 *   S lands and is held — alive, not frozen: the glow behind it swells while
 *   the mark itself stays put (a dead stop with nothing moving is what used to
 *   break the transition; a mark that never gets to simply *be there* is what
 *   kept it from landing)
 *     -> S dissolves, alone, against the solid stage
 *       -> opaque beat: the site's own base tone, held still for a breath
 *         -> the cloud reveal: colour and translucency arrive together and the
 *            colour lingers into the tail, so the last of the frame dissolves
 *            with it rather than after it
 *
 * Every hand-off overlaps rather than cuts.
 */
const S_HOLD = 0.5; // s — the mark at full presence while its glow swells
const S_FADE = 1.3; // s — the mark's own dissolve, on the shared easing
const S_END = S_HOLD + S_FADE;
const HOLD_IN = 0.5; // s — the beat crossfades in under the S's back half...
const HOLD_LEAD = 0.1; // s — ...and is fully present this long before the S is gone
/**
 * Gap between the S clearing and the cloud block starting. Sized so the phase
 * between the S going and the homepage arriving splits roughly 30% opaque beat,
 * 70% cloud: the first cloud takes ~0.35s after mounting to become perceptible,
 * so the stillness the eye sees is HOLD + ~0.35s against a cloud reveal of
 * FADE - ~0.35s. One slow breath runs the length of it so it never sits dead.
 */
const HOLD = 2.1; // over the 30/70 sizing so the anniversary line can enter gently and still be read
const REVEAL_AT = S_END + HOLD; // s — the cloud reveal below begins here
/**
 * The anniversary line lives entirely inside the beat: it only starts once the
 * S has completely gone and the frame is solid, and it is fully out before the
 * first cloud mounts — never mid-crossfade on either side.
 */
const TAGLINE_IN = S_END + 0.1;
const TAGLINE_OUT = REVEAL_AT - 0.05;
/**
 * The site's background hue, one shade darker — oklch(0.235 0.034 305) against
 * the token's oklch(0.242 0.017 305). At the token's own chroma this tone reads
 * as plain black on screen; doubling the chroma keeps the lightness in the same
 * family while making the violet legible, so the beat reads as the site's own
 * surface rather than a black frame.
 */
const HOLD_TONE = "#221A2B";
const FADE = 4.8; // s — slow, fog-dissipating dissolve into the homepage
const HARD_FALLBACK = 4600; // ms safety net if the video never reports progress

/**
 * The overlay's own fade is keyframed below rather than eased, so that it dwells
 * in the translucent band instead of rushing through it — a single ease-in-out
 * is fastest exactly where both layers are visible, which is the part worth
 * seeing. This curve is the homepage's side of that cross-fade: near-linear with
 * softened ends, roughly the inverse of the overlay's. Exported with the
 * duration so __root.tsx stays on the same clock instead of re-declaring one.
 */
export const INTRO_EASE = [0.35, 0.3, 0.6, 0.85] as const;
export const INTRO_FADE_MS = FADE * 1000;

/**
 * The video's near-black background is not quite 0 (the poster frame's glow
 * measures RGB 8,7,5). Under `mix-blend-mode: screen` that lifts into a visible
 * banded disc over the stage colour, so crush anything below ~8/255 to true
 * black — screen over true black is a no-op — while leaving the mark untouched.
 */
const BLACK_CRUSH = "contrast(1.14) brightness(0.98) saturate(1.06)";

/** Feather the frame edge so stray bloom never terminates on a hard rectangle. */
const EDGE_MASK =
  "radial-gradient(ellipse 92% 92% at 50% 50%, #000 68%, rgba(0,0,0,0.55) 86%, transparent 100%)";

/**
 * Colour fog that reads as cloud — soft masses with body, and dark gaps between
 * them — rather than as shapes or as a tint.
 *
 * Two earlier passes bracketed the target. Three ellipses cut off at 62% with
 * no blur gave six ovals with findable edges. Five wide gradients falling off
 * to 88%, oversized and blurred 40px, went the other way: everything smeared
 * into one screen-wide colour wash, so thinning the frame read as the whole
 * screen tinting rather than as clouds parting. This sits between: three
 * masses per layer, each with a solid body and a soft shoulder, moderate blur
 * (enough to erase any oval edge, not enough to merge the masses), and real
 * gaps — so the homepage appears through the gaps and the thinning masses.
 */
type Fog = {
  delay: number;
  duration: number;
  peak: number;
  background: string;
  drift: { x: [string, string]; y: [string, string]; scale: [number, number] };
};
/** A cloud mass: solid centre, soft shoulder, gone by ~74% — body without an edge. */
const mass = (size: string, at: string, rgb: string, a: number): string =>
  `radial-gradient(ellipse ${size} at ${at}, rgba(${rgb},${a}) 0%, rgba(${rgb},${(a * 0.7).toFixed(2)}) 30%, rgba(${rgb},${(a * 0.25).toFixed(2)}) 55%, transparent 74%)`;
const FOG: Fog[] = [
  {
    // warm
    delay: 0,
    duration: 3.9,
    peak: 0.95,
    background: [
      mass("58% 44%", "22% 30%", "255,201,60", 0.95),
      mass("50% 40%", "76% 22%", "214,51,154", 0.88),
      mass("54% 38%", "50% 78%", "255,138,61", 0.82),
    ].join(","),
    drift: { x: ["-3%", "2.5%"], y: ["1.5%", "-2%"], scale: [1.04, 1.18] },
  },
  {
    // cool
    delay: 0.5,
    duration: 3.8,
    peak: 0.9,
    background: [
      mass("58% 46%", "80% 70%", "124,77,224", 0.95),
      mass("52% 42%", "14% 76%", "47,191,143", 0.85),
      mass("46% 36%", "58% 12%", "61,139,255", 0.78),
    ].join(","),
    drift: { x: ["3%", "-2.5%"], y: ["-1%", "2%"], scale: [1.06, 1.2] },
  },
  {
    // mixed
    delay: 1.0,
    duration: 3.6,
    peak: 0.85,
    background: [
      mass("52% 42%", "34% 56%", "232,80,58", 0.82),
      mass("48% 38%", "72% 46%", "37,224,176", 0.78),
      mass("44% 34%", "50% 20%", "214,51,154", 0.7),
    ].join(","),
    drift: { x: ["0%", "2%"], y: ["2%", "-1.5%"], scale: [1.03, 1.2] },
  },
];

const CHARGE_GLOW =
  "radial-gradient(circle, rgba(255,201,60,0.30), rgba(214,51,154,0.18) 45%, transparent 70%)";

type Phase = "video" | "fading" | "revealing" | "done";

/** `requestVideoFrameCallback` lands the cut within a frame; Firefox falls back to timeupdate. */
type VideoWithRVFC = HTMLVideoElement & {
  requestVideoFrameCallback?: (cb: (now: number, meta: { mediaTime: number }) => void) => number;
  cancelVideoFrameCallback?: (handle: number) => void;
};

export function BrandIntro() {
  const { setContentHidden } = useIntro();
  const [phase, setPhase] = useState<Phase>("video");
  const [showSkip, setShowSkip] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);
  const closedRef = useRef(false);
  const fadeRef = useRef(FADE);
  const timersRef = useRef<number[]>([]);

  const startClosing = useCallback(
    (quick: boolean) => {
      if (closedRef.current) return;
      closedRef.current = true;

      const v = videoRef.current;
      if (v) {
        v.pause();
        if (!quick) {
          // Always seek, never just "if we overshot". The cut fires on the first
          // frame past CUT_AT, which lands anywhere in a ~60ms window, and the S
          // travels ~19.5px per frame here as it clears room for the wordmark —
          // so tolerating any overshoot visibly decentres the mark on some
          // loads. Seeking pins every run to the same frame.
          try {
            v.currentTime = CUT_AT;
          } catch {
            /* seeking unavailable — the frame we stopped on is close enough */
          }
        }
      }

      fadeRef.current = quick ? 0.4 : FADE;
      if (quick) {
        // Skip / reduced motion: one short dissolve, no beat.
        setContentHidden(false);
        setPhase("revealing");
        timersRef.current.push(
          window.setTimeout(() => setPhase("done"), fadeRef.current * 1000 + 80),
        );
        return;
      }
      // The mark starts dissolving on the freeze frame, so nothing is ever idle.
      // The cloud reveal — untouched — simply begins after the beat.
      setPhase("fading");
      timersRef.current.push(
        window.setTimeout(() => {
          setContentHidden(false); // homepage begins easing in underneath, on the same clock
          setPhase("revealing");
        }, REVEAL_AT * 1000),
        window.setTimeout(() => setPhase("done"), (REVEAL_AT + FADE) * 1000 + 80),
      );
    },
    [setContentHidden],
  );

  useEffect(() => {
    const v = videoRef.current;
    if (v) v.play().catch(() => {});
    timersRef.current.push(
      window.setTimeout(() => setShowSkip(true), 700),
      window.setTimeout(() => startClosing(false), HARD_FALLBACK),
    );
    const reduced =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) startClosing(true);
    const timers = timersRef.current;
    return () => timers.forEach(window.clearTimeout);
  }, [startClosing]);

  // Frame-accurate cut so the freeze lands on the intended frame rather than up
  // to 250ms late, which at this point in the clip is a visibly different frame.
  useEffect(() => {
    const v = videoRef.current as VideoWithRVFC | null;
    if (!v || typeof v.requestVideoFrameCallback !== "function") return;
    let handle = 0;
    const tick = (_now: number, meta: { mediaTime: number }) => {
      if (meta.mediaTime >= CUT_AT) return startClosing(false);
      handle = v.requestVideoFrameCallback!(tick);
    };
    handle = v.requestVideoFrameCallback(tick);
    return () => v.cancelVideoFrameCallback?.(handle);
  }, [startClosing]);

  if (phase === "done") return null;

  const fading = phase === "fading";
  const revealing = phase === "revealing";
  const ending = fading || revealing; // anything after the cut
  const fade = fadeRef.current;
  const slowFade = fade >= 1; // the quick/reduced-motion path skips the fog entirely

  return (
    <motion.div
      aria-hidden
      className="grain fixed inset-0 z-[80] overflow-hidden"
      style={{
        backgroundColor: STAGE_BG,
        pointerEvents: ending ? "none" : "auto",
        willChange: "opacity",
      }}
      /* A plain opaque-to-transparent fade of the whole screen: no scale, no
         blur. Depth here came across as the screen warping rather than clearing,
         so the atmosphere is left entirely to the colour fog below. */
      initial={{ opacity: 1 }}
      animate={
        revealing
          ? // The frame thins from the reveal's first frame, in step with the first
            // cloud's rise, so colour and translucency arrive together and the
            // homepage shows through both — a flat frame that colour "pops" onto
            // reads as a scene change. Then a long steady translucent dwell and a
            // decelerating landing on 0. (The old slow start was for the S to
            // linger; the S now dissolves on its own before this begins.)
            { opacity: [1, 0.74, 0.5, 0.3, 0.12, 0] }
          : { opacity: 1 }
      }
      transition={
        revealing
          ? {
              duration: fade,
              times: [0, 0.22, 0.48, 0.72, 0.9, 1],
              ease: ["easeInOut", "linear", "linear", "linear", "easeOut"],
            }
          : { duration: fade }
      }
    >
      {/*
        The opaque beat. Sits behind the mark and crossfades in under its last
        stretch, so by the time the S is gone the frame is already fully present —
        there is no moment to cut to. It stays as the overlay's surface through
        the reveal, so the clouds bloom through it and the whole overlay hands
        off into the homepage's identical base tone. The inner layer is the
        breath: a few percent of darkening and back, so the hold reads as the
        surface resting rather than a frozen loading frame. Site-wide grain
        continues over all of it via the overlay's own `grain`.
      */}
      {ending && slowFade && (
        <motion.div
          aria-hidden
          className="absolute inset-0"
          style={{ backgroundColor: HOLD_TONE }}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: S_END - HOLD_LEAD - HOLD_IN, duration: HOLD_IN, ease: INTRO_EASE }}
        >
          <motion.div
            className="absolute inset-0 bg-black"
            initial={{ opacity: 0 }}
            animate={{ opacity: [0, 0.035, 0] }}
            transition={{
              delay: S_END - 0.15,
              duration: HOLD + 0.5,
              times: [0, 0.5, 1],
              ease: "easeInOut",
            }}
          />
          {/* Centred by a static wrapper: Motion writes `transform` inline, so a
              Tailwind translate on the animated element would be clobbered. */}
          {/* Lifted a little above centre (padding on the static wrapper, so it
              cannot be clobbered by Motion's inline transform on the children). */}
          <div className="absolute inset-0 grid place-items-center px-6 pb-[12vh]">
            {/*
              The entrance is the point: each line rises ~56px as it resolves from
              a soft blur, and the second line follows the first by ~120ms — the
              stagger is what makes "rising in" legible as a gesture rather than a
              fade. Both lines share one duration and delay; the second simply
              holds at zero for its first 7% so the two exit together.
            */}
            <p className="text-center font-display text-[clamp(1.9rem,5.6vw,4.4rem)] font-semibold leading-[1.1] tracking-[-0.01em] text-foreground [text-shadow:0_0_48px_rgba(255,255,255,0.14)]">
              <motion.span
                className="spectrum-text block"
                initial={{ opacity: 0, y: 40, filter: "blur(8px)" }}
                animate={{
                  opacity: [0, 1, 1, 0],
                  y: [40, 0, 0, 0], // exits in place: a fade, not a lift
                  filter: ["blur(8px)", "blur(0px)", "blur(0px)", "blur(0px)"],
                }}
                transition={{
                  delay: TAGLINE_IN,
                  duration: TAGLINE_OUT - TAGLINE_IN,
                  // A slow-start ease over ~0.6s: the line surfaces rather than fires.
                  times: [0, 0.3, 0.82, 1],
                  ease: ["easeInOut", "linear", "easeInOut"],
                }}
              >
                Five Decades
              </motion.span>
              <motion.span
                className="block"
                initial={{ opacity: 0, y: 40, filter: "blur(8px)" }}
                animate={{
                  opacity: [0, 0, 1, 1, 0],
                  y: [40, 40, 0, 0, 0],
                  filter: ["blur(8px)", "blur(8px)", "blur(0px)", "blur(0px)", "blur(0px)"],
                }}
                transition={{
                  delay: TAGLINE_IN,
                  duration: TAGLINE_OUT - TAGLINE_IN,
                  times: [0, 0.07, 0.37, 0.82, 1],
                  ease: ["linear", "easeInOut", "linear", "easeInOut"],
                }}
              >
                of Capturing Moments
              </motion.span>
            </p>
          </div>
        </motion.div>
      )}

      {/*
        No poster: the poster JPEG is a mid-tumble flare frame while the video
        opens on near-black, so painting it first flashed a mismatched frame and
        double-composited its glow under `screen`. The stage colour is the
        intended backdrop for the pre-roll instead.
      */}
      <motion.video
        ref={videoRef}
        className="absolute inset-0 h-full w-full object-cover"
        autoPlay
        muted
        playsInline
        preload="auto"
        style={{
          mixBlendMode: "screen",
          filter: BLACK_CRUSH,
          maskImage: EDGE_MASK,
          WebkitMaskImage: EDGE_MASK,
        }}
        initial={{ opacity: 0 }}
        animate={{ opacity: ending ? 0 : 1 }}
        transition={
          ending
            ? slowFade
              ? { delay: S_HOLD, duration: S_FADE, ease: INTRO_EASE }
              : { duration: fade, ease: INTRO_EASE }
            : { duration: 0.6, ease: "easeInOut" }
        }
        onError={() => startClosing(true)}
        onEnded={() => startClosing(false)}
        onTimeUpdate={(e) => {
          if (e.currentTarget.currentTime >= CUT_AT) startClosing(false);
        }}
      >
        <source src={INTRO_WEBM} type="video/webm" />
        <source src={INTRO_MP4} type="video/mp4" />
      </motion.video>

      {/*
        A tight glow behind the mark. It never scales — an expanding one reads as
        exactly the ring artefact this pass set out to remove.
      */}
      {fading && (
        <motion.div
          className="pointer-events-none absolute left-1/2 top-1/2 rounded-full"
          style={{
            width: 440,
            height: 440,
            marginLeft: -220,
            marginTop: -220,
            mixBlendMode: "screen",
            background: CHARGE_GLOW,
            filter: "blur(44px)", // diffuse enough that it never reads as a disc
          }}
          /* The life inside the hold: swells while the mark sits still, holds
             through the start of the dissolve, then clears as the mark does. */
          initial={{ opacity: 0 }}
          animate={{ opacity: [0, 0.9, 0.9, 0] }}
          transition={{ duration: S_END, times: [0, 0.28, 0.5, 1], ease: "easeInOut" }}
        />
      )}

      <AnimatePresence>
        {revealing && slowFade && (
          <motion.div key="fog" className="pointer-events-none absolute inset-0">
            {FOG.map((f, i) => (
              <motion.div
                key={i}
                // Slightly oversized so the blur's soft edge and the drift stay off-screen.
                className="absolute -inset-[6%]"
                style={{
                  background: f.background,
                  mixBlendMode: "screen",
                  filter: "blur(22px)",
                  willChange: "opacity, transform",
                }}
                initial={{
                  opacity: 0,
                  x: f.drift.x[0],
                  y: f.drift.y[0],
                  scale: f.drift.scale[0],
                }}
                animate={{
                  // Long rise so colour seeps in with the thinning frame; a high
                  // shoulder so it is still there as the last of the frame goes.
                  opacity: [0, f.peak, f.peak * 0.85, 0],
                  x: f.drift.x[1],
                  y: f.drift.y[1],
                  scale: f.drift.scale[1],
                }}
                transition={{
                  duration: f.duration,
                  delay: f.delay,
                  ease: "easeInOut",
                  times: [0, 0.4, 0.74, 1],
                }}
              />
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {showSkip && !ending && (
          <motion.button
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => startClosing(true)}
            className="absolute bottom-6 right-6 text-xs font-medium uppercase tracking-[0.2em] text-white/55 transition-colors hover:text-white/90"
          >
            Skip
          </motion.button>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
