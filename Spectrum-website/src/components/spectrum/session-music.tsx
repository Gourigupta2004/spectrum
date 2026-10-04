import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { INTRO_FADE_MS } from "./brand-intro";
import { useIntro } from "./intro-context";
import { useSite } from "@/lib/use-site";

/** Background level: present enough to colour the room, never competing. */
const BG_VOLUME = 0.35;
const FADE_IN_MS = 2500;
/** The asked-for breath between the page being there and the music arriving. */
const START_GAP_MS = 1000;
const MUTED_KEY = "spectrum-music-muted";

type MusicCtx = {
  /** A track is configured and (possibly) playing — the nav shows the toggle. */
  available: boolean;
  muted: boolean;
  toggle: () => void;
};

const Ctx = createContext<MusicCtx>({ available: false, muted: false, toggle: () => {} });

/**
 * The session soundtrack: one soft loop for the whole visit. It starts a beat
 * after the page is truly "there" — on an intro session, after the intro has
 * fully dissolved (so it never talks over the intro sting); elsewhere, a second
 * after landing. Browsers gate audible playback behind the first interaction,
 * so a blocked start quietly retries on the first tap, click or key.
 */
export function MusicProvider({ children }: { children: ReactNode }) {
  const site = useSite();
  const { contentHidden } = useIntro();
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [audioUrl, setAudioUrl] = useState("");
  const armedRef = useRef(false); // the start moment has arrived
  const mutedRef = useRef(false);
  const [muted, setMuted] = useState(false);
  const [available, setAvailable] = useState(false);
  // Whether this session opened with the intro: decided once, at mount.
  const introSessionRef = useRef<boolean | null>(null);
  if (introSessionRef.current === null) introSessionRef.current = contentHidden;

  const fadeTo = useCallback((target: number, ms: number) => {
    const a = audioRef.current;
    if (!a) return;
    const from = a.volume;
    const started = performance.now();
    const step = () => {
      if (!audioRef.current) return;
      const t = Math.min(1, (performance.now() - started) / ms);
      a.volume = from + (target - from) * t;
      if (t < 1) requestAnimationFrame(step);
      else if (target === 0) a.pause();
    };
    requestAnimationFrame(step);
  }, []);

  const tryStart = useCallback(() => {
    const a = audioRef.current;
    if (!a || !armedRef.current || mutedRef.current) return;
    if (!a.paused) return;
    a.volume = 0;
    a.play()
      .then(() => fadeTo(BG_VOLUME, FADE_IN_MS))
      .catch(() => {
        /* blocked — the gesture listener below will retry */
      });
  }, [fadeTo]);

  // Load the loop (as a blob, so every server serves it seekably) once per session.
  useEffect(() => {
    if (!site.sessionAudio) return;
    let cancelled = false;
    let url = "";
    try {
      mutedRef.current = localStorage.getItem(MUTED_KEY) === "1";
      setMuted(mutedRef.current);
    } catch {
      /* storage unavailable — default to sound on */
    }
    fetch(site.sessionAudio)
      .then((r) => (r.ok ? r.blob() : Promise.reject(new Error(String(r.status)))))
      .then((blob) => {
        if (cancelled) return;
        url = URL.createObjectURL(blob);
        setAudioUrl(url);
        setAvailable(true);
      })
      .catch(() => {
        /* no soundtrack is a quiet failure, never a broken page */
      });
    return () => {
      cancelled = true;
      audioRef.current?.pause();
      if (url) URL.revokeObjectURL(url);
    };
  }, [site.sessionAudio, tryStart]);

  // Arm the start: a second after the intro has fully dissolved, or a second
  // after landing when there is no intro.
  useEffect(() => {
    if (introSessionRef.current && contentHidden) return; // intro still playing
    const wait = (introSessionRef.current ? INTRO_FADE_MS : 0) + START_GAP_MS;
    const timer = window.setTimeout(() => {
      armedRef.current = true;
      tryStart();
    }, wait);
    return () => window.clearTimeout(timer);
  }, [contentHidden, tryStart]);

  // Autoplay fallback: the first real interaction unlocks audio.
  useEffect(() => {
    const onGesture = () => tryStart();
    window.addEventListener("pointerdown", onGesture);
    window.addEventListener("keydown", onGesture);
    return () => {
      window.removeEventListener("pointerdown", onGesture);
      window.removeEventListener("keydown", onGesture);
    };
  }, [tryStart]);

  // Courtesy: go quiet while the tab is in the background.
  useEffect(() => {
    const onVisibility = () => {
      const a = audioRef.current;
      if (!a) return;
      if (document.hidden) a.pause();
      else if (armedRef.current && !mutedRef.current) {
        a.play()
          .then(() => (a.volume = BG_VOLUME))
          .catch(() => {});
      }
    };
    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
  }, []);

  const toggle = useCallback(() => {
    mutedRef.current = !mutedRef.current;
    setMuted(mutedRef.current);
    try {
      localStorage.setItem(MUTED_KEY, mutedRef.current ? "1" : "0");
    } catch {
      /* preference just won't persist */
    }
    if (mutedRef.current) fadeTo(0, 600);
    else tryStart();
  }, [fadeTo, tryStart]);

  // The element mounts once the blob is ready and tries to start right away
  // (covers the case where the start moment arrived before the file did).
  useEffect(() => {
    if (audioUrl) tryStart();
  }, [audioUrl, tryStart]);

  const value = useMemo<MusicCtx>(() => ({ available, muted, toggle }), [available, muted, toggle]);
  return (
    <Ctx.Provider value={value}>
      {children}
      {audioUrl && (
        <audio ref={audioRef} src={audioUrl} loop preload="auto" data-session-music aria-hidden />
      )}
    </Ctx.Provider>
  );
}

export const useMusic = () => useContext(Ctx);
