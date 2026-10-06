import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { motion, useInView } from "motion/react";
import { ChevronLeft, ChevronRight, Search } from "lucide-react";
import { HeroCarousel } from "@/components/spectrum/hero-carousel";
import { EventCard } from "@/components/spectrum/event-card";
import { Orb } from "@/components/spectrum/orb";
import { GlassChips } from "@/components/spectrum/glass-chips";
import { Highlight } from "@/components/spectrum/highlight";
import { getHome } from "@/lib/data/pages";
import { seoMeta } from "@/lib/data/site";

export const Route = createFileRoute("/")({
  loader: () => getHome(),
  staleTime: 60_000,
  head: ({ loaderData }) => ({ meta: seoMeta(loaderData?.seo) }),
  component: Home,
});

function Counter({ to, suffix = "" }: { to: number; suffix?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: "-80px" });
  const [n, setN] = useState(0);

  useEffect(() => {
    if (!inView) return;
    const start = performance.now();
    const dur = 1600;
    let raf = 0;
    const tick = (t: number) => {
      const p = Math.min((t - start) / dur, 1);
      setN(Math.round(to * (1 - Math.pow(1 - p, 3))));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [inView, to]);

  return (
    <span ref={ref} className="spectrum-text font-display text-5xl md:text-6xl">
      {n.toLocaleString("en-IN")}
      {suffix}
    </span>
  );
}

function Home() {
  const navigate = useNavigate();
  const { copy, heroSlides, stats, services, institutions, events } = Route.useLoaderData();

  // Always the institution's own event listing, even when it has a single
  // event: the listing is where the institution's name, filters and event card
  // live, so landing straight inside a gallery skipped the context.
  const onInstitution = (id: string) => navigate({ to: "/events", search: { institution: id } });

  // Chevrons flank the institutions row whenever more icons hide beyond an
  // edge — a visible "scroll this way" marker that also scrolls on click.
  const instRow = useRef<HTMLDivElement>(null);
  const [instHint, setInstHint] = useState({ left: false, right: false });
  useEffect(() => {
    const el = instRow.current;
    if (!el) return;
    const update = () =>
      setInstHint({
        left: el.scrollLeft > 8,
        right: el.scrollLeft + el.clientWidth < el.scrollWidth - 8,
      });
    update();
    el.addEventListener("scroll", update, { passive: true });
    // Re-measure whenever the scroller or its track changes size (viewport
    // resizes, web fonts and images landing), not just on mount — a mount-time
    // measurement can miss the overflow and leave the right chevron hidden.
    const ro = new ResizeObserver(update);
    ro.observe(el);
    if (el.firstElementChild) ro.observe(el.firstElementChild);
    return () => {
      el.removeEventListener("scroll", update);
      ro.disconnect();
    };
  }, [institutions.length]);
  const nudgeInstitutions = (dir: 1 | -1) =>
    instRow.current?.scrollBy({ left: dir * 320, behavior: "smooth" });

  return (
    <div className="grain relative overflow-x-clip">
      {/* HERO */}
      <section className="relative flex h-svh w-full flex-col items-center justify-center overflow-hidden px-4">
        <Orb className="left-1/2 top-[12%] -translate-x-1/2" size={720} opacity={0.12} />
        <Orb
          className="right-[-10%] top-[45%]"
          colors={["#2fbf8f", "#8b5cf6"]}
          size={520}
          opacity={0.09}
          delay={6}
        />
        <motion.div
          initial={{ opacity: 0, y: 22 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8 }}
          className="relative z-10 text-center"
        >
          <h1 className="font-display text-[clamp(2.2rem,6vw,4.6rem)] leading-[1.05] text-foreground">
            <Highlight text={copy.heroTitle} />
          </h1>
          <p className="mx-auto mt-4 max-w-xl text-sm font-medium text-foreground/85 md:text-base">
            {copy.heroSubtitle}
          </p>
        </motion.div>

        <div className="relative z-10 mt-9 w-full">
          <HeroCarousel slides={heroSlides} />
        </div>
      </section>

      {/* SEARCH + INSTITUTIONS */}
      <section className="relative mx-auto max-w-5xl px-6 py-14 sm:py-20">
        {/* Styled like the old search bar, but it is step one of the funnel:
            it opens the institutions page where the icons are filtered and chosen. */}
        <Link
          to="/institutions"
          className="spectrum-border glass mx-auto flex max-w-xl items-center gap-2 rounded-full p-1.5"
        >
          <span className="min-w-0 flex-1 truncate px-4 py-2.5 text-sm text-muted-foreground">
            {copy.searchPlaceholder}
          </span>
          <span className="spectrum-fill grid h-10 w-10 shrink-0 place-items-center rounded-full">
            <Search className="h-4 w-4" />
          </span>
        </Link>

        <h2 className="mt-12 text-center font-display text-xs font-semibold uppercase tracking-[0.28em] text-foreground/80 sm:mt-16">
          {copy.institutionsHeading}
        </h2>
        {/* One horizontally scrollable row at every size. The icons sit on an
            inner w-max track with mx-auto: it centres itself while everything
            fits and otherwise starts at the left edge and scrolls — centring
            the scroller itself would push the leftmost circles past the edge
            where no scroll can reach them. On phones the row is bled to the
            screen edges with matching scroll padding, so a half-visible circle
            reads as "there is more this way"; from sm up the chevrons live in
            reserved side gutters with clear air between them and the icons:
            the edge fade stays fully transparent under the whole button plus a
            buffer, so a scrolling icon has melted away completely before it
            could slide beneath a marker, and the resting row starts a gap
            beyond it. */}
        <div className="relative mt-8">
          {instHint.left && (
            <button
              onClick={() => nudgeInstitutions(-1)}
              aria-label="Scroll institutions left"
              className="spectrum-border glass absolute left-0 top-7 z-10 hidden h-10 w-10 place-items-center rounded-full text-foreground transition-all hover:-translate-y-0.5 sm:grid"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
          )}
          {instHint.right && (
            <button
              onClick={() => nudgeInstitutions(1)}
              aria-label="Scroll institutions right"
              className="spectrum-border glass absolute right-0 top-7 z-10 hidden h-10 w-10 place-items-center rounded-full text-foreground transition-all hover:-translate-y-0.5 sm:grid"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          )}
          <div
            ref={instRow}
            className="no-scrollbar -mx-6 snap-x snap-mandatory overflow-x-auto px-6 pb-2 [scroll-padding-left:1.5rem] sm:mx-0 sm:px-[4.75rem] sm:[scroll-padding-left:4.75rem] sm:[mask-image:linear-gradient(to_right,transparent_3rem,#000_4.75rem,#000_calc(100%-4.75rem),transparent_calc(100%-3rem))]"
          >
            <div className="mx-auto flex w-max gap-6 sm:gap-8">
              {institutions.map((inst) => (
                <button
                  key={inst.id}
                  onClick={() => onInstitution(inst.id)}
                  className="group flex w-24 shrink-0 snap-start flex-col items-center gap-3 sm:w-28 sm:snap-center"
                >
                  <span className="spectrum-border spectrum-border-thick relative block h-20 w-20 rounded-full p-[3px] transition-all duration-400 group-hover:-translate-y-1 group-hover:shadow-[0_16px_40px_-14px_rgba(139,92,246,0.7)] sm:h-24 sm:w-24">
                    {inst.image ? (
                      <img
                        src={inst.image}
                        alt={inst.name}
                        loading="lazy"
                        className="h-full w-full rounded-full object-cover"
                      />
                    ) : (
                      <span className="block h-full w-full rounded-full bg-surface" />
                    )}
                  </span>
                  {/* Two lines reserved either way, so names of different lengths
                  keep the circles on one baseline instead of stepping. */}
                  <span className="line-clamp-2 min-h-[2.1rem] font-display text-[0.7rem] uppercase leading-[1.25] tracking-[0.1em] text-foreground sm:min-h-0 sm:text-[0.65rem] sm:tracking-[0.14em]">
                    {inst.short}
                  </span>
                </button>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* STATS */}
      <section className="relative overflow-hidden py-20">
        <Orb
          className="left-[10%] top-0"
          colors={["#f5973b", "#e8503a"]}
          size={480}
          opacity={0.1}
        />
        <div className="relative z-10 mx-auto grid max-w-5xl gap-12 px-6 text-center md:grid-cols-3">
          {stats.map((s) => (
            <div key={s.label}>
              <Counter to={s.to} suffix={s.suffix} />
              <p className="mt-2 text-sm font-medium text-foreground/85">{s.label}</p>
            </div>
          ))}
        </div>
      </section>

      {/* OUR SERVICES */}
      <section id="services" className="relative scroll-mt-24 overflow-hidden py-20">
        <Orb
          className="left-1/2 top-0 -translate-x-1/2"
          colors={["#7c4de0", "#2fbf8f"]}
          size={520}
          opacity={0.1}
        />
        <div className="relative z-10 mx-auto max-w-5xl px-6 text-center">
          <h2 className="font-display text-3xl font-semibold text-foreground md:text-4xl">
            <Highlight text={copy.servicesHeading} />
          </h2>
          <p className="mt-3 text-sm font-medium text-muted-foreground md:text-base">
            {copy.servicesSubtitle}
          </p>
          <div className="mt-12">
            <GlassChips items={services} label="Services" />
          </div>
        </div>
      </section>

      {/* FEATURED */}
      <section className="relative overflow-hidden py-20">
        <Orb
          className="right-[5%] top-[6%]"
          colors={["#8b5cf6", "#b94c9e"]}
          size={560}
          opacity={0.1}
          delay={3}
        />
        <div className="relative z-10 mx-auto max-w-6xl px-6">
          <h2 className="font-display text-3xl font-semibold text-foreground md:text-4xl">
            <Highlight text={copy.featuredHeading} />
          </h2>
          <div className="mt-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {events.map((e, i) => (
              <EventCard key={e.slug} event={e} index={i} />
            ))}
          </div>
          <div className="mt-12 text-center">
            <button
              onClick={() => navigate({ to: "/institutions" })}
              className="spectrum-fill rounded-full px-8 py-3.5 text-sm font-semibold"
            >
              {copy.featuredCta}
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
