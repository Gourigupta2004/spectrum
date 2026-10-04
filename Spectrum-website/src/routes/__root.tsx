import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  Outlet,
  Link,
  createRootRouteWithContext,
  useRouter,
  useRouterState,
  HeadContent,
  Scripts,
} from "@tanstack/react-router";
import { useEffect, useState, type ReactNode } from "react";

import appCss from "../styles.css?url";
import { reportLovableError } from "../lib/lovable-error-reporting";
import { SpectrumNav } from "@/components/spectrum/nav";
import { Footer } from "@/components/spectrum/footer";
import { SelectionProvider } from "@/components/spectrum/selection-context";
import { IntroProvider, useIntro } from "@/components/spectrum/intro-context";
import { MusicProvider } from "@/components/spectrum/session-music";

import { BrandIntro, INTRO_EASE, INTRO_FADE_MS } from "@/components/spectrum/brand-intro";
import { getSite, seoMeta } from "@/lib/data/site";
import { useSite } from "@/lib/use-site";

export function NotFoundComponent() {
  const { copy } = useSite();
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="max-w-md text-center">
        <h1 className="text-7xl font-bold text-foreground">404</h1>
        <h2 className="mt-4 text-xl font-semibold text-foreground">{copy.notFoundTitle}</h2>
        <p className="mt-2 text-sm text-muted-foreground">{copy.notFoundBody}</p>
        <div className="mt-6">
          <Link
            to="/"
            className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            {copy.notFoundCta}
          </Link>
        </div>
      </div>
    </div>
  );
}

export function ErrorComponent({ error, reset }: { error: Error; reset: () => void }) {
  console.error(error);
  const router = useRouter();
  const { copy } = useSite();
  useEffect(() => {
    reportLovableError(error, { boundary: "tanstack_root_error_component" });
  }, [error]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="max-w-md text-center">
        <h1 className="text-xl font-semibold tracking-tight text-foreground">{copy.errorTitle}</h1>
        <p className="mt-2 text-sm text-muted-foreground">{copy.errorBody}</p>
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          <button
            onClick={() => {
              router.invalidate();
              reset();
            }}
            className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            {copy.errorRetry}
          </button>
          <a
            href="/"
            className="inline-flex items-center justify-center rounded-md border border-input bg-background px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-accent"
          >
            {copy.notFoundCta}
          </a>
        </div>
      </div>
    </div>
  );
}

export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  loader: () => getSite(),
  staleTime: 5 * 60_000,
  head: ({ loaderData }) => ({
    meta: [
      { charSet: "utf-8" },
      { name: "viewport", content: "width=device-width, initial-scale=1" },
      ...seoMeta(loaderData?.seo),
      { name: "author", content: "Spectrum" },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
      { name: "twitter:site", content: "@Lovable" },
    ],
    links: [
      {
        rel: "stylesheet",
        href: appCss,
      },
      { rel: "icon", href: loaderData?.favicon || "/favicon.png" },
      { rel: "preconnect", href: "https://fonts.googleapis.com" },
      { rel: "preconnect", href: "https://fonts.gstatic.com", crossOrigin: "anonymous" },
      {
        rel: "stylesheet",
        href: "https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;500;600;700&family=DM+Sans:wght@400;500;700&display=swap",
      },
    ],
  }),
  shellComponent: RootShell,
  component: RootComponent,
  notFoundComponent: NotFoundComponent,
  errorComponent: ErrorComponent,
});

function RootShell({ children }: { children: ReactNode }) {
  return (
    /* Paint the base colour from the first byte: without it the browser shows its
       default white canvas until the stylesheet lands, flashing white ahead of the
       dark intro. Inline so it applies before any stylesheet is fetched. */
    <html lang="en" style={{ backgroundColor: "#221F29" }}>
      <head>
        <HeadContent />
      </head>
      <body>
        {children}
        <Scripts />
      </body>
    </html>
  );
}

function SiteShell() {
  const { contentHidden } = useIntro();
  return (
    <>
      <BrandIntro key="brand-intro" />
      {/*
        Opacity only, deliberately: `transform`/`filter` here would make this a
        containing block for fixed positioning and unpin the fixed nav. The
        dissolve's depth (scale + blur) lives on the intro overlay instead.
        Duration and easing are imported from BrandIntro rather than
        re-typed here — a mismatch between the two is what made the reveal
        read as two separate, uncoordinated snaps instead of one cross-fade.
      */}
      <div
        style={{
          opacity: contentHidden ? 0 : 1,
          pointerEvents: contentHidden ? "none" : "auto",
          transition: `opacity ${INTRO_FADE_MS}ms cubic-bezier(${INTRO_EASE.join(",")}) 100ms`,
        }}
      >
        <SpectrumNav />
        {/* Required: nested routes render here. Removing <Outlet /> breaks all child routes. */}
        <Outlet />
        <Footer />
      </div>
    </>
  );
}

function RootComponent() {
  const { queryClient } = Route.useRouteContext();
  const isHome = useRouterState({ select: (s) => s.location.pathname === "/" });
  /*
   * Decided once per document load and never revisited: the brand intro belongs
   * to a session that *starts* on the homepage. Arriving on "/" from another
   * page is client-side navigation, so this stays whatever it was when the
   * document first rendered — no intro on the way back from Events or Contact,
   * and none at all for a session that began elsewhere. The value is the same
   * on the server and at hydration, so the shells never mismatch.
   */
  const [withIntro] = useState(isHome);

  return (
    <QueryClientProvider client={queryClient}>
      <IntroProvider initialContentHidden={withIntro}>
        <MusicProvider>
          <SelectionProvider>{withIntro ? <SiteShell /> : <PlainShell />}</SelectionProvider>
        </MusicProvider>
      </IntroProvider>
    </QueryClientProvider>
  );
}

function PlainShell() {
  return (
    <>
      <SpectrumNav />
      {/* Required: nested routes render here. Removing <Outlet /> breaks all child routes. */}
      <Outlet />
      <Footer />
    </>
  );
}
