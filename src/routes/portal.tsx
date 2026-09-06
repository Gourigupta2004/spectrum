import { createFileRoute, Outlet, useNavigate } from "@tanstack/react-router";
import { motion } from "motion/react";
import { LogOut } from "lucide-react";
import { Orb } from "@/components/spectrum/orb";
import { portalInstitution } from "@/lib/caption-data";
import { sessionStore, useStore } from "@/lib/portal-store";

export const Route = createFileRoute("/portal")({
  head: () => ({
    meta: [
      { title: "Institution Portal — Spectrum Workspace" },
      {
        name: "description",
        content:
          "Institution sign-in for the Spectrum workspace — review event photo captions and name students in class photos.",
      },
      { property: "og:title", content: "Institution Portal — Spectrum" },
      {
        property: "og:description",
        content: "Review Spectrum event captions and build labelled class rosters.",
      },
    ],
  }),
  component: PortalLayout,
});

function PortalLayout() {
  const signedIn = useStore(sessionStore);
  const navigate = useNavigate();

  if (!signedIn) {
    return (
      <LoginScreen
        onLogin={() => {
          sessionStore.set(true);
          navigate({ to: "/portal/workspace" });
        }}
      />
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
            <p className="font-display text-[0.68rem] uppercase tracking-[0.24em] text-muted-foreground">
              Signed in as
            </p>
            <p className="font-display text-lg font-semibold text-foreground">
              {portalInstitution.name}
            </p>
          </div>
          <button
            onClick={() => {
              sessionStore.set(false);
              navigate({ to: "/" });
            }}
            className="inline-flex items-center gap-2 rounded-full border border-violet/70 px-4 py-2 text-xs font-semibold text-foreground transition-colors hover:border-teal hover:text-teal"
          >
            <LogOut className="h-3.5 w-3.5" /> Sign Out
          </button>
        </div>

        <div className="mt-10">
          <Outlet />
        </div>
      </div>
    </div>
  );
}

/* ---------------- Login (decorative) ---------------- */

function LoginScreen({ onLogin }: { onLogin: () => void }) {
  return (
    <div className="grain relative grid min-h-screen place-items-center overflow-x-clip px-4 py-28">
      <Orb className="left-[-10%] top-16" colors={["#7c4de0", "#d6339a"]} size={520} opacity={0.1} />
      <Orb className="right-[-8%] bottom-10" colors={["#2fbf8f", "#ffc93c"]} size={460} opacity={0.08} />

      <motion.div
        initial={{ opacity: 0, y: 18, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ type: "spring", stiffness: 240, damping: 26 }}
        className="spectrum-border glass relative z-10 w-full max-w-md overflow-hidden rounded-3xl bg-surface p-8"
      >
        <img
          src="/spectrum-logo-light.png"
          alt="Spectrum"
          className="h-7 w-auto"
          draggable={false}
        />
        <p className="mt-6 font-display text-xs uppercase tracking-[0.24em] text-muted-foreground">
          Institution Login
        </p>
        <h1 className="mt-2 font-display text-3xl text-foreground">
          {portalInstitution.name}
        </h1>
        <p className="mt-1 text-sm font-medium text-muted-foreground">
          {portalInstitution.city} · Institution Workspace
        </p>

        <form
          className="mt-7 space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            onLogin();
          }}
        >
          <input
            placeholder="Institution ID"
            defaultValue="dps-newdelhi"
            className="w-full rounded-xl border border-border bg-background/60 px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-transparent focus:outline-none focus:ring-2 focus:ring-violet"
          />
          <input
            type="password"
            placeholder="Password"
            defaultValue="demo"
            className="w-full rounded-xl border border-border bg-background/60 px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-transparent focus:outline-none focus:ring-2 focus:ring-violet"
          />
          <button type="submit" className="spectrum-fill w-full rounded-xl py-3.5 text-sm font-semibold">
            Log In →
          </button>
        </form>
        <p className="mt-4 text-center text-xs text-muted-foreground">
          Demo access — no real authentication is performed.
        </p>
      </motion.div>
    </div>
  );
}
