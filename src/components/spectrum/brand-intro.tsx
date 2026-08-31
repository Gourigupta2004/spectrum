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
 * There is deliberately no hold. The clip still freezes on the hero frame — the
 * mark is meant to sit still there, and letting it keep drifting looked wrong —
 * but the fade and the colour both start on that same frame, so the screen is
 * never idle. What used to break the transition was the second of dead air
 * between the freeze and the fade, not the freeze itself.
 */
const FADE = 3.3; // s — slow, fog-dissipating dissolve into the homepage
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
 * Colour fog, as full-bleed layers rather than discrete blobs.
 *
 * The previous version positioned circular divs (a 620px bloom scaling to 1.7x,
 * plus five 520-680px discs) which read as hard-edged expanding rings mid-fade.
 * Each layer here paints several very wide, very soft ellipses spread to every
 * corner of the viewport; because they overlap inside one element they merge
 * into continuous drifting colour with no circular boundary anywhere, and they
 * cover the whole screen instead of clustering around the centre.
 */
const FOG: { delay: number; duration: number; peak: number; background: string }[] = [
  {
    delay: 0.1,
    duration: 1.8,
    peak: 0.7,
    background: [
      "radial-gradient(ellipse 62% 52% at 12% 18%, rgba(255,201,60,0.9), transparent 62%)",
      "radial-gradient(ellipse 56% 48% at 88% 24%, rgba(214,51,154,0.8), transparent 62%)",
      "radial-gradient(ellipse 64% 52% at 44% 94%, rgba(47,191,143,0.75), transparent 62%)",
    ].join(","),
  },
  {
    delay: 0.45,
    duration: 1.8,
    peak: 0.66,
    background: [
      "radial-gradient(ellipse 58% 50% at 92% 74%, rgba(124,77,224,0.85), transparent 62%)",
      "radial-gradient(ellipse 54% 46% at 6% 78%, rgba(232,80,58,0.78), transparent 62%)",
      "radial-gradient(ellipse 50% 44% at 64% 6%, rgba(61,139,255,0.7), transparent 62%)",
    ].join(","),
  },
  {
    delay: 0.8,
    duration: 1.7,
    peak: 0.6,
    background: [
      "radial-gradient(ellipse 60% 50% at 28% 58%, rgba(255,138,61,0.8), transparent 62%)",
      "radial-gradient(ellipse 52% 46% at 78% 46%, rgba(37,224,176,0.7), transparent 62%)",
      "radial-gradient(ellipse 48% 42% at 50% 22%, rgba(214,51,154,0.62), transparent 62%)",
    ].join(","),
  },
];

const CHARGE_GLOW =
  "radial-gradient(circle, rgba(255,201,60,0.30), rgba(214,51,154,0.18) 45%, transparent 70%)";

type Phase = "video" | "exiting" | "done";

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
      // Straight into the dissolve — the colour and the fade start on the same
      // frame the clip freezes, so there is no gap where nothing is moving.
      setContentHidden(false); // homepage begins easing in underneath, on the same clock
      setPhase("exiting");
      timersRef.current.push(
        window.setTimeout(() => setPhase("done"), fadeRef.current * 1000 + 80),
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

  const exiting = phase === "exiting";
  const fade = fadeRef.current;
  const slowFade = fade >= 1; // the quick/reduced-motion path skips the fog entirely

  return (
    <motion.div
      aria-hidden
      className="grain fixed inset-0 z-[80] overflow-hidden"
      style={{
        backgroundColor: STAGE_BG,
        pointerEvents: exiting ? "none" : "auto",
        willChange: "opacity",
      }}
      /* A plain opaque-to-transparent fade of the whole screen: no scale, no
         blur. Depth here came across as the screen warping rather than clearing,
         so the atmosphere is left entirely to the colour fog below. */
      initial={{ opacity: 1 }}
      animate={
        exiting
          ? // Opaque -> translucent -> transparent, held apart so each reads as its
            // own stage: a brisk drop into translucency, a long steady dwell there
            // (0.70 -> 0.42 across 42% of the fade, where the homepage and the mark
            // are both clearly visible at once), then a decelerating landing on 0.
            { opacity: [1, 0.8, 0.45, 0.2, 0] }
          : { opacity: 1 }
      }
      transition={
        exiting
          ? {
              duration: fade,
              times: [0, 0.24, 0.62, 0.84, 1],
              ease: ["easeOut", "linear", "linear", "easeOut"],
            }
          : { duration: fade }
      }
    >
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
        animate={{ opacity: 1 }}
        transition={{ duration: 0.6, ease: "easeInOut" }}
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
      {exiting && (
        <motion.div
          className="pointer-events-none absolute left-1/2 top-1/2 rounded-full"
          style={{
            width: 320,
            height: 320,
            marginLeft: -160,
            marginTop: -160,
            mixBlendMode: "screen",
            background: CHARGE_GLOW,
            filter: "blur(24px)",
          }}
          /* Rises with the mark as the clip slows, then clears early so the fog
             carries the rest — never a beat where it simply sits at one value. */
          initial={{ opacity: 0 }}
          animate={{ opacity: [0, 0.85, 0] }}
          transition={{ duration: fade * 0.55, times: [0, 0.35, 1], ease: "easeInOut" }}
        />
      )}

      <AnimatePresence>
        {exiting && slowFade && (
          <motion.div key="fog" className="pointer-events-none absolute inset-0">
            {FOG.map((f, i) => (
              <motion.div
                key={i}
                className="absolute inset-0"
                style={{ background: f.background, mixBlendMode: "screen" }}
                initial={{ opacity: 0, scale: 1 }}
                animate={{ opacity: [0, f.peak, f.peak * 0.78, 0], scale: 1.08 }}
                transition={{
                  duration: f.duration,
                  delay: f.delay,
                  ease: "easeInOut",
                  times: [0, 0.35, 0.7, 1],
                }}
              />
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {showSkip && !exiting && (
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
