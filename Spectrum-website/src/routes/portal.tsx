import { createFileRoute, Outlet, useNavigate } from "@tanstack/react-router";
import { useState, type FormEvent, type ReactNode } from "react";
import { motion } from "motion/react";
import { LogOut } from "lucide-react";
import { Orb } from "@/components/spectrum/orb";
import { hasApi } from "@/lib/api";
import { getPortalCopy } from "@/lib/data/pages";
import {
  clearAccess,
  signIn,
  signOut,
  usePortalAccess,
  usePortalMember,
  useSignedIn,
  verifyAccess,
} from "@/lib/portal-session";
import { useSite } from "@/lib/use-site";

export const Route = createFileRoute("/portal")({
  head: () => ({
    meta: [
      { title: "Institution Portal — Spectrum Workspace" },
      {
        name: "description",
        content:
          "Institution sign-in for the Spectrum workspace — review event photo titles and name students in class photos.",
      },
      { property: "og:title", content: "Institution Portal — Spectrum" },
      {
        property: "og:description",
        content: "Review Spectrum event photo titles and build labelled class rosters.",
      },
      // Invitation-only: keep it out of search results.
      { name: "robots", content: "noindex" },
    ],
  }),
  // Signed-in state lives in the browser, so the portal renders client-side only.
  ssr: false,
  loader: () => getPortalCopy(),
  staleTime: 5 * 60_000,
  component: PortalLayout,
});

function PortalLayout() {
  const signedIn = useSignedIn();
  const access = usePortalAccess();
  const { institution } = usePortalMember();
  const copy = Route.useLoaderData();
  const navigate = useNavigate();

  if (!signedIn) {
    // Step one is the email that unlocks the portal; step two the issued login.
    return access ? (
      <LoginScreen onLogin={() => navigate({ to: "/portal/workspace" })} />
    ) : (
      <AccessScreen />
    );
  }

  return (
    <div className="grain relative min-h-screen overflow-x-clip pb-28 pt-28">
      <Orb
        className="right-[-10%] top-24"
        colors={["#7c4de0", "#2fbf8f"]}
        size={520}
        opacity={0.08}
      />

      <div className="relative z-10 mx-auto max-w-6xl px-6">
        <div className="spectrum-border glass flex flex-wrap items-center justify-between gap-4 rounded-2xl px-5 py-4">
          <div>
            <p className="font-display text-[0.72rem] sm:text-[0.68rem] uppercase tracking-[0.24em] text-muted-foreground">
              {copy.signedInAs}
            </p>
            <p className="font-display text-lg font-semibold text-foreground">{institution.name}</p>
          </div>
          <button
            onClick={() => {
              signOut();
              navigate({ to: "/" });
            }}
            className="inline-flex items-center gap-2 rounded-full border border-violet/70 px-4 py-2 text-xs font-semibold text-foreground transition-colors hover:border-teal hover:text-teal"
          >
            <LogOut className="h-3.5 w-3.5" /> {copy.signOut}
          </button>
        </div>

        <div className="mt-10">
          <Outlet />
        </div>
      </div>
    </div>
  );
}

/* ---------------- Shared card ---------------- */

const inputClass =
  "w-full rounded-xl border border-border bg-background/60 px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-transparent focus:outline-none focus:ring-2 focus:ring-violet";

function Card({ children }: { children: ReactNode }) {
  const site = useSite();
  return (
    <div className="grain relative grid min-h-screen place-items-center overflow-x-clip px-4 py-28">
      <Orb
        className="left-[-10%] top-16"
        colors={["#7c4de0", "#d6339a"]}
        size={520}
        opacity={0.1}
      />
      <Orb
        className="right-[-8%] bottom-10"
        colors={["#2fbf8f", "#ffc93c"]}
        size={460}
        opacity={0.08}
      />

      <motion.div
        initial={{ opacity: 0, y: 18, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ type: "spring", stiffness: 240, damping: 26 }}
        className="spectrum-border glass relative z-10 w-full max-w-md overflow-hidden rounded-3xl bg-surface p-8"
      >
        <img src={site.logoLight} alt="Spectrum" className="h-7 w-auto" draggable={false} />
        {children}
      </motion.div>
    </div>
  );
}

/* ---------------- Step one: institution email ---------------- */

function AccessScreen() {
  const copy = Route.useLoaderData();
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      await verifyAccess(email);
      // Verifying swaps this screen for the sign-in one, so this component is
      // already gone: clearing `busy` here would be a state update on an
      // unmounted component. Only the failure path stays on screen.
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : copy.accessError);
      setBusy(false);
    }
  };

  return (
    <Card>
      <p className="mt-6 font-display text-xs uppercase tracking-[0.24em] text-muted-foreground">
        {copy.accessEyebrow}
      </p>
      <h1 className="mt-2 font-display text-3xl text-foreground">{copy.accessTitle}</h1>
      <p className="mt-1 text-sm font-medium text-muted-foreground">{copy.accessSubtitle}</p>

      <form className="mt-7 space-y-4" onSubmit={submit}>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="email"
          inputMode="email"
          required
          autoFocus
          placeholder={copy.accessPlaceholder}
          className={inputClass}
        />
        <button
          type="submit"
          disabled={busy}
          className="spectrum-fill w-full rounded-xl py-3.5 text-sm font-semibold disabled:opacity-60"
        >
          {busy ? "Checking…" : copy.accessButton}
        </button>
      </form>
      {error && (
        <p role="alert" className="mt-4 text-center text-xs font-medium text-[#ff9b6a]">
          {error}
        </p>
      )}
      {!hasApi && (
        <p className="mt-4 text-center text-xs text-muted-foreground">
          Demo access — any email address unlocks the demo institution.
        </p>
      )}
    </Card>
  );
}

/* ---------------- Step two: issued credentials ---------------- */

function LoginScreen({ onLogin }: { onLogin: () => void }) {
  const copy = Route.useLoaderData();
  const access = usePortalAccess();
  const [username, setUsername] = useState(hasApi ? "" : "dps-newdelhi");
  const [password, setPassword] = useState(hasApi ? "" : "demo");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      await signIn(username.trim(), password);
      onLogin(); // navigates away — same reason this screen never clears `busy`
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : copy.loginError);
      setBusy(false);
    }
  };

  // Personalised to the institution the email belongs to: this screen is theirs.
  const institution = access?.institution;

  return (
    <Card>
      <p className="mt-6 font-display text-xs uppercase tracking-[0.24em] text-muted-foreground">
        {copy.loginEyebrow}
      </p>
      <h1 className="mt-2 font-display text-3xl text-foreground">
        {institution?.name || copy.loginTitle}
      </h1>
      <p className="mt-1 text-sm font-medium text-muted-foreground">
        {institution?.city ? `${institution.city} · ${copy.loginSubtitle}` : copy.loginSubtitle}
      </p>

      <form className="mt-7 space-y-4" onSubmit={submit}>
        <input
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          autoComplete="username"
          required
          placeholder={copy.loginIdPlaceholder}
          className={inputClass}
        />
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
          required
          placeholder={copy.loginPasswordPlaceholder}
          className={inputClass}
        />
        <button
          type="submit"
          disabled={busy}
          className="spectrum-fill w-full rounded-xl py-3.5 text-sm font-semibold disabled:opacity-60"
        >
          {busy ? "Signing in…" : copy.loginButton}
        </button>
      </form>
      {error && (
        <p role="alert" className="mt-4 text-center text-xs font-medium text-[#ff9b6a]">
          {error}
        </p>
      )}
      <p className="mt-5 text-center text-xs text-muted-foreground">
        {access?.email}{" "}
        <button
          type="button"
          onClick={clearAccess}
          className="font-medium text-teal transition-colors hover:text-foreground"
        >
          · {copy.accessChange}
        </button>
      </p>
      {!hasApi && (
        <p className="mt-3 text-center text-xs text-muted-foreground">
          Demo access — no real authentication is performed.
        </p>
      )}
    </Card>
  );
}
