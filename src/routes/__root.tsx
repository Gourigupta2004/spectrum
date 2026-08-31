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
import { useEffect, type ReactNode } from "react";

import appCss from "../styles.css?url";
import { reportLovableError } from "../lib/lovable-error-reporting";
import { SpectrumNav } from "@/components/spectrum/nav";
import { Footer } from "@/components/spectrum/footer";
import { SelectionProvider } from "@/components/spectrum/selection-context";
import { IntroProvider, useIntro } from "@/components/spectrum/intro-context";

import { BrandIntro, INTRO_EASE, INTRO_FADE_MS } from "@/components/spectrum/brand-intro";

function NotFoundComponent() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="max-w-md text-center">
        <h1 className="text-7xl font-bold text-foreground">404</h1>
        <h2 className="mt-4 text-xl font-semibold text-foreground">Page not found</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          The page you're looking for doesn't exist or has been moved.
        </p>
        <div className="mt-6">
          <Link
            to="/"
            className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            Go home
          </Link>
        </div>
      </div>
    </div>
  );
}

function ErrorComponent({ error, reset }: { error: Error; reset: () => void }) {
  console.error(error);
  const router = useRouter();
  useEffect(() => {
    reportLovableError(error, { boundary: "tanstack_root_error_component" });
  }, [error]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="max-w-md text-center">
        <h1 className="text-xl font-semibold tracking-tight text-foreground">
          This page didn't load
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Something went wrong on our end. You can try refreshing or head back home.
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          <button
            onClick={() => {
              router.invalidate();
              reset();
            }}
            className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            Try again
          </button>
          <a
            href="/"
            className="inline-flex items-center justify-center rounded-md border border-input bg-background px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-accent"
          >
            Go home
          </a>
        </div>
      </div>
    </div>
  );
}

export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  head: () => ({
    meta: [
      { charSet: "utf-8" },
      { name: "viewport", content: "width=device-width, initial-scale=1" },
      { title: "Spectrum — Every Moment, Yours Forever" },
      { name: "description", content: "Spectrum captures school and college events across India." },
      { name: "author", content: "Spectrum" },
      { property: "og:title", content: "Spectrum — Every Moment, Yours Forever" },
      { property: "og:description", content: "Premium school and college event photography." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
      { name: "twitter:site", content: "@Lovable" },
    ],
    links: [
      {
        rel: "stylesheet",
        href: appCss,
      },
      { rel: "icon", type: "image/png", href: "/favicon.png" },
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

  return (
    <QueryClientProvider client={queryClient}>
      <IntroProvider initialContentHidden={isHome}>
        <SelectionProvider>{isHome ? <SiteShell /> : <PlainShell />}</SelectionProvider>
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
