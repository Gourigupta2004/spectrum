import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { motion, useInView } from "motion/react";
import { Search } from "lucide-react";
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

  const [query, setQuery] = useState("");

  // Always the institution's own event listing, even when it has a single
  // event: the listing is where the institution's name, filters and event card
  // live, so landing straight inside a gallery skipped the context.
  const onInstitution = (id: string) => navigate({ to: "/events", search: { institution: id } });

  const onSearch = (e: FormEvent) => {
    e.preventDefault();
    const q = query.trim();
    navigate({ to: "/events", search: q ? { q } : {} });
  };

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

        <div className="relative z-10 mt-6 w-full">
          <HeroCarousel slides={heroSlides} />
        </div>
      </section>

      {/* SEARCH + INSTITUTIONS */}
      <section className="relative mx-auto max-w-5xl px-6 py-14 sm:py-20">
        <form
          role="search"
          onSubmit={onSearch}
          className="spectrum-border glass mx-auto flex max-w-xl items-center gap-2 rounded-full p-1.5"
        >
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={copy.searchPlaceholder}
            aria-label={copy.searchPlaceholder}
            autoComplete="off"
            enterKeyHint="search"
            className="min-w-0 flex-1 bg-transparent px-4 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none [&::-webkit-search-cancel-button]:hidden"
          />
          <button
            type="submit"
            aria-label="Search"
            className="spectrum-fill grid h-10 w-10 shrink-0 place-items-center rounded-full"
          >
            <Search className="h-4 w-4" />
          </button>
        </form>

        <h2 className="mt-12 text-center font-display text-xs font-semibold uppercase tracking-[0.28em] text-foreground/80 sm:mt-16">
          {copy.institutionsHeading}
        </h2>
        {/* Scrolls on a phone and centres once they all fit. The row is bled to
            the screen edges with a matching scroll padding, so a half-visible
            circle reads as "there is more this way" rather than as a clipped
            layout, and the first one still lines up with the copy above it. */}
        <div className="no-scrollbar -mx-6 mt-8 flex snap-x snap-mandatory gap-6 overflow-x-auto px-6 pb-2 [scroll-padding-left:1.5rem] sm:gap-8 md:mx-0 md:justify-center md:px-1">
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
              onClick={() => navigate({ to: "/events" })}
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
