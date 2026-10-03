import { Link, useRouterState } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { useSelection } from "./selection-context";
import { useIntro } from "./intro-context";
import { useSite } from "@/lib/use-site";

type NavLink = { label: string; to: "/events" | "/about" | "/contact" | "/portal" };

export function SpectrumNav() {
  const [scrolled, setScrolled] = useState(false);
  const [menu, setMenu] = useState(false);
  const { count, openCheckout } = useSelection();
  const { navLogoVisible } = useIntro();
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const site = useSite();
  const links: NavLink[] = [
    { label: site.copy.navEvents, to: "/events" },
    { label: site.copy.navAbout, to: "/about" },
    { label: site.copy.navContact, to: "/contact" },
    { label: site.copy.navPortal, to: "/portal" },
  ];

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <>
      {/* The bar never dims or shrinks while scrolling: once the page has moved
          it gains its glass border and stays at full presence in either direction. */}
      <motion.nav
        initial={{ y: -24, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ type: "spring", stiffness: 260, damping: 26 }}
        className="fixed inset-x-0 top-4 z-50 flex justify-center px-4"
      >
        <div
          className={`flex items-center gap-6 rounded-full px-4 py-2.5 transition-all duration-500 md:gap-9 md:px-6 ${
            scrolled ? "glass spectrum-border shadow-2xl" : ""
          }`}
        >
          {/* The mark is only 14px wide; the link is padded out to a full-height
              target so it can actually be tapped. */}
          <Link
            to="/"
            className="-mx-1 -my-2 flex h-10 shrink-0 items-center px-1"
            aria-label="Spectrum home"
          >
            {navLogoVisible && (
              <>
                <motion.img
                  layoutId="spectrum-navlogo"
                  transition={{ duration: 0.7, ease: [0.4, 0, 0.2, 1] }}
                  src={site.logoLight}
                  alt="Spectrum"
                  className="hidden h-6 w-auto md:block"
                  draggable={false}
                />
                <img
                  src={site.logoMark}
                  alt="Spectrum"
                  className="h-6 w-auto md:hidden"
                  draggable={false}
                />
              </>
            )}
          </Link>

          <div className="hidden items-center gap-8 md:flex">
            {links.map((l) => {
              const active = pathname === l.to || pathname.startsWith(`${l.to}/`);
              return (
                <Link
                  key={l.to}
                  to={l.to}
                  className="group relative font-display text-[0.78rem] font-semibold uppercase tracking-[0.2em] text-foreground transition-colors hover:text-foreground"
                >
                  {l.label}
                  <span
                    className={`spectrum-hairline absolute -bottom-1.5 left-0 w-full origin-left transition-transform duration-300 ${
                      active ? "scale-x-100" : "scale-x-0 group-hover:scale-x-100"
                    }`}
                  />
                </Link>
              );
            })}
          </div>

          {/* Padded to a full 44px touch target: the three dots alone were four
              pixels tall, which is nothing to aim at on a phone. */}
          <button
            aria-label="Open menu"
            onClick={() => setMenu(true)}
            className="-my-2 flex h-11 items-center gap-1 px-2 md:hidden"
          >
            {[0, 1, 2].map((i) => (
              <span key={i} className="spectrum-fill h-1 w-1 rounded-full" />
            ))}
          </button>

          {count > 0 && (
            <button
              onClick={openCheckout}
              aria-label={`${count} photos selected`}
              className="spectrum-fill flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold"
            >
              {count}
            </button>
          )}
        </div>
      </motion.nav>

      <AnimatePresence>
        {menu && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[70] flex flex-col items-center justify-center gap-10 bg-surface/95 backdrop-blur-2xl"
          >
            <button
              onClick={() => setMenu(false)}
              aria-label="Close menu"
              className="absolute right-6 top-6 text-3xl leading-none text-foreground"
            >
              ×
            </button>
            {links.map((l) => (
              <Link
                key={l.to}
                to={l.to}
                onClick={() => setMenu(false)}
                className="group relative font-display text-3xl font-semibold text-foreground"
              >
                {l.label}
                <span className="spectrum-hairline absolute -bottom-2 left-0 w-full scale-x-0 transition-transform duration-300 group-active:scale-x-100" />
              </Link>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
