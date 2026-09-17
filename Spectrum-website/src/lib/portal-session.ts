/**
 * Portal sign-in state. With the backend it holds signed tokens in localStorage
 * (the portal renders client-side only); in demo mode it is the old in-memory flag.
 *
 * Getting in is two steps. First the visitor verifies an institution email that
 * Spectrum has given access to — that unlocks the Portal link in the nav and
 * personalises the sign-in screen. Then they sign in with the credentials
 * Spectrum issued for that institution. The verified email is remembered in
 * this browser so the link stays after signing out.
 */
import { ApiError, apiFetch, hasApi } from "./api";
import { portalInstitution, portalRole } from "./caption-data";
import { createStore, sessionStore, useClientStore, useStore } from "./portal-store";

export type PortalInstitution = { id: string; name: string; city: string };

export type PortalMember = {
  id: number;
  loginId: string;
  displayName: string;
  role: "institution" | "spectrum";
  institution: PortalInstitution | null;
};

export type PortalAccess = { email: string; institution: PortalInstitution };

type Session = { access: string; refresh: string; member: PortalMember };

const KEY = "spectrum.portal";
const ACCESS_KEY = "spectrum.portal.access";
/** Per tab, not per browser: the guidelines greet a teacher once each session. */
const GUIDELINES_KEY = "spectrum.portal.guidelines";

function readJson<T>(key: string): T | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

function writeJson(key: string, value: unknown) {
  try {
    if (value) window.localStorage.setItem(key, JSON.stringify(value));
    else window.localStorage.removeItem(key);
  } catch {
    /* storage unavailable: the value just won't survive a reload */
  }
}

export const authStore = createStore<Session | null>(readJson<Session>(KEY));
export const accessStore = createStore<PortalAccess | null>(readJson<PortalAccess>(ACCESS_KEY));

export function guidelinesSeenThisSession(): boolean {
  try {
    return window.sessionStorage.getItem(GUIDELINES_KEY) === "1";
  } catch {
    return true; // storage unavailable: better silent than shown on every visit
  }
}

export function markGuidelinesSeen() {
  try {
    window.sessionStorage.setItem(GUIDELINES_KEY, "1");
  } catch {
    /* storage unavailable: the popup simply greets them again next time */
  }
}

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/** Step one: is this email on an institution's access list? Remembered on success. */
export async function verifyAccess(email: string): Promise<PortalAccess> {
  const clean = email.trim().toLowerCase();
  if (!EMAIL.test(clean)) throw new ApiError(400, "Please enter a valid email address.", "email");
  const access = hasApi
    ? await apiFetch<PortalAccess>("/api/portal/access/", {
        method: "POST",
        json: { email: clean },
      })
    : { email: clean, institution: portalInstitution };
  writeJson(ACCESS_KEY, access);
  accessStore.set(access);
  return access;
}

/** Forget the verified email (and any sign-in that came with it). */
export function clearAccess() {
  signOut();
  writeJson(ACCESS_KEY, null);
  accessStore.set(null);
}

/** Step two: sign in with the credentials issued for the verified institution. */
export async function signIn(username: string, password: string): Promise<void> {
  if (!hasApi) {
    sessionStore.set(true);
    return;
  }
  const result = await apiFetch<Session>("/api/portal/login/", {
    method: "POST",
    json: { username, password, email: accessStore.get()?.email ?? "" },
  });
  const session = { access: result.access, refresh: result.refresh, member: result.member };
  writeJson(KEY, session);
  authStore.set(session);
}

export function signOut() {
  sessionStore.set(false);
  writeJson(KEY, null);
  authStore.set(null);
}

let refreshing: Promise<boolean> | null = null;

async function refreshTokens(): Promise<boolean> {
  const session = authStore.get();
  if (!session) return false;
  refreshing ??= apiFetch<{ access: string; refresh: string }>("/api/portal/refresh/", {
    method: "POST",
    json: { refresh: session.refresh },
  })
    .then((tokens) => {
      const next = { ...session, ...tokens };
      writeJson(KEY, next);
      authStore.set(next);
      return true;
    })
    .catch((error: unknown) => {
      // Only a rejected refresh token ends the session; a network blip keeps it.
      if (error instanceof ApiError && (error.status === 401 || error.status === 403)) signOut();
      return false;
    })
    .finally(() => {
      refreshing = null;
    });
  return refreshing;
}

/** Authenticated request; refreshes an expired access token once, then signs out. */
export async function portalFetch<T>(
  path: string,
  init: Parameters<typeof apiFetch>[1] = {},
): Promise<T> {
  const session = authStore.get();
  if (!session) throw new ApiError(401, "Please sign in.");
  try {
    return await apiFetch<T>(path, { ...init, token: session.access });
  } catch (error) {
    if (!(error instanceof ApiError) || error.status !== 401) throw error;
    const refreshed = (await refreshTokens()) ? authStore.get() : null;
    if (refreshed) return apiFetch<T>(path, { ...init, token: refreshed.access });
    throw error;
  }
}

/** The verified institution email for this browser, or null before step one. */
export function usePortalAccess(): PortalAccess | null {
  return useClientStore(accessStore, null);
}

export function useSignedIn(): boolean {
  const demo = useStore(sessionStore);
  const session = useClientStore(authStore, null);
  return hasApi ? session !== null : demo;
}

export function usePortalMember(): {
  role: "institution" | "spectrum";
  institution: PortalInstitution;
} {
  const session = useStore(authStore);
  if (!hasApi || !session) return { role: portalRole, institution: portalInstitution };
  const { member } = session;
  return {
    role: member.role,
    institution: member.institution ?? { id: "", name: member.displayName, city: "" },
  };
}
