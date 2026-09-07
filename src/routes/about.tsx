import { createFileRoute, Link } from "@tanstack/react-router";
import { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ArrowLeft, ChevronLeft, ChevronRight, Plus } from "lucide-react";
import { Orb } from "@/components/spectrum/orb";
import { GlassChips } from "@/components/spectrum/glass-chips";
import { IMG, pick } from "@/lib/spectrum-data";

export const Route = createFileRoute("/about")({
  head: () => ({
    meta: [
      { title: "About Us — Spectrum" },
      {
        name: "description",
        content:
          "Established in 1980, Spectrum has spent nearly five decades photographing the institutions of the NCR — from film to digital, all in-house.",
      },
      { property: "og:title", content: "About Us — Spectrum" },
      {
        property: "og:description",
        content:
          "Nearly five decades of experience, precision, and trust in institutional photography.",
      },
    ],
  }),
  component: AboutPage,
});

const capabilities = [
  "Photography",
  "Mediagraphy",
  "Videography",
  "Cinematography",
  "Graphic Design",
  "Promotional Films",
  "Media Services",
  "ID Card Production",
] as const;

/**
 * Placeholder imagery, each verified by eye rather than by search term, and
 * chosen dark: on this canvas a white-backed photo is the brightest thing on
 * the page and pulls the eye off the copy. A classic compact camera lit in the
 * site's own magenta/teal on black; the gallery's confetti finale; and film
 * rolls with pinned prints for the in-house production story.
 */
const story = [
  {
    title: "Our Evolution",
    body: "From black-and-white to colour film, and now advanced digital imaging — we've embraced every evolution in photography while staying true to its fundamentals: experience, precision, creativity, and attention to detail.",
    image: IMG("1516724562728-afc824a36e84", 900, 680),
    alt: "A classic compact camera lit in magenta and teal against black",
  },
  {
    title: "Institutional Expertise",
    body: "Having worked extensively with the top schools, colleges, and educational institutions across the NCR, we stand among the most experienced and dependable names in institutional photography.",
    image: IMG(pick(10), 900, 680), // the gallery's finale crowd — the one pool shot with real annual-day energy
    alt: "A crowd under confetti at a school annual-day finale",
  },
  {
    title: "Complete In-House Craft",
    body: "Our production facility at Saket uses the finest photo printing and binding equipment from Fuji and Noritsu, Japan. Every step — photographing, designing, printing, and binding — is handled in-house, with no outsourcing, so we can guarantee your timelines, your quality, and the complete privacy of your data.",
    image: IMG("1500051638674-ff996a0ec29e", 900, 680),
    alt: "Film rolls and printed photographs pinned on a board",
  },
];

/**
 * Real, named institutions — so the photo is deliberately one generic campus
 * image reused across every card rather than anything scraped that might be
 * someone else's marketing photography. Spectrum's own archive from these
 * relationships is the right long-term source here.
 */
const CAMPUS = [
  IMG("1562774053-701939374585", 400, 400), // campus building
  IMG("1427504494785-3a9ca7044f45", 400, 400), // library aisle
  IMG("1509062522246-3755977927d7", 400, 400), // classroom
];
/** Rotated so no frame of three shows identical circles. */
const campusFor = (i: number): string => CAMPUS[i % CAMPUS.length]!;
const tieUps = [
  { name: "Amity Group of Institutions", years: "30+" },
  { name: "K.R. Mangalam Group of Institutions", years: "20+" },
  { name: "St. Andrews Group of Schools", years: "4+" },
  { name: "DPS International – Gurugram", years: "3+" },
  { name: "Bal Bharati Public School – Noida", years: "15+" },
  { name: "G.D. Goenka Public School – Gurugram", years: "15+" },
  { name: "G.D. Goenka Global School – Noida", years: "3+" },
  { name: "ASN Sr. Secondary School – New Delhi", years: "15+" },
  { name: "Colonel's Central Academy – Gurugram", years: "15+" },
  { name: "Mount Olympus School – Gurugram", years: "7+" },
  { name: "GBN Sr. Sec. School – Faridabad", years: "15+" },
  { name: "Universal Public School – New Delhi", years: "15+" },
  { name: "Balwant Rai Mehta School – New Delhi", years: "10+" },
];

/** Carried over verbatim from the retired How It Works page. */
const faqs = [
  {
    q: "How soon are photos available after the event?",
    a: "Your private gallery goes live within 48 hours of the event wrapping. Large multi-day fests can take up to 72 hours for the full set.",
  },
  {
    q: "How are the final files delivered?",
    a: "Instantly after checkout, over WhatsApp or email — whichever you choose. You receive full-resolution JPEGs with no watermark and no expiry on the link.",
  },
  {
    q: "What does it cost?",
    a: "Individual photos start at ₹29 each. The full album bundle for an event is ₹299 — usually the better value once you want more than ten photos.",
  },
  {
    q: "Can our institution book a coverage date?",
    a: "Yes. Reach out through the contact page with your event date and venue, and we'll confirm a crew and a coverage plan.",
  },
];

const reveal = {
  initial: { opacity: 0, y: 22 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-60px" },
  transition: { duration: 0.55 },
} as const;

function AboutPage() {
  // One panel open at a time, first open by default — the behaviour the
  // original page had; this pass is a visual refresh only.
  const [openFaq, setOpenFaq] = useState<number | null>(0);
  return (
    <div className="grain relative min-h-screen overflow-x-clip pb-24 pt-28">
      <Orb
        className="right-[-12%] top-[38%]"
        colors={["#FFC93C", "#2FBF8F"]}
        size={520}
        opacity={0.08}
        delay={2}
      />

      <div className="relative z-10 mx-auto max-w-5xl px-6">
        <Link
          to="/"
          className="inline-flex items-center gap-2 text-sm font-medium text-muted-foreground transition-colors hover:text-teal"
        >
          <ArrowLeft className="h-4 w-4" /> Home
        </Link>

        <h1 className="sr-only">About Us</h1>
      </div>

      {/* 1 — capabilities: the selling points, so they lead the page at near full width */}
      <section className="relative z-10 mx-auto mt-10 max-w-[90rem] px-6 md:px-12">
        <Orb
          className="left-1/2 top-[-60%] -translate-x-1/2"
          colors={["#7C4DE0", "#D6339A"]}
          size={560}
          opacity={0.1}
        />
        <div className="relative z-10">
          <GlassChips items={capabilities} label="Capabilities" size="lg" />
        </div>
      </section>

      <div className="relative z-10 mx-auto max-w-5xl px-6">
        {/* 2 — Who We Are */}
        <section className="mt-20">
          <motion.p
            {...reveal}
            className="mx-auto max-w-5xl text-center font-display text-3xl leading-snug text-foreground md:text-5xl"
          >
            Established in 1980 — Nearly <span className="spectrum-text">Five Decades</span> of
            Experience, Precision, and Trust.
          </motion.p>

          <div className="mt-16 space-y-14">
            {story.map((s, i) => (
              <motion.article
                key={s.title}
                {...reveal}
                className={`grid items-center gap-8 md:grid-cols-2 ${
                  i % 2 === 1 ? "md:[&>figure]:order-first" : ""
                }`}
              >
                <div>
                  <h3 className="font-display text-2xl font-semibold text-foreground md:text-3xl">
                    {s.title}
                  </h3>
                  <p className="mt-3 text-sm font-medium leading-relaxed text-muted-foreground md:text-base">
                    {s.body}
                  </p>
                </div>
                <figure className="spectrum-border overflow-hidden rounded-3xl">
                  <img
                    src={s.image}
                    alt={s.alt}
                    loading="lazy"
                    draggable={false}
                    className="h-64 w-full object-cover md:h-72"
                  />
                </figure>
              </motion.article>
            ))}
          </div>

          <motion.p
            {...reveal}
            className="mx-auto mt-16 max-w-4xl text-center font-display text-2xl leading-snug text-foreground md:text-3xl"
          >
            <span className="spectrum-text">Technology</span> has changed.{" "}
            <span className="spectrum-text">Photography</span> has evolved. Our{" "}
            <span className="spectrum-text">commitment</span> to quality remains constant.
          </motion.p>
        </section>

        {/* 3 — Our Tie-Ups */}
        <section className="mt-28">
          <motion.h2
            {...reveal}
            className="text-center font-display text-3xl font-semibold text-foreground md:text-4xl"
          >
            Our Tie-Ups
          </motion.h2>
          <motion.p
            {...reveal}
            className="mt-3 text-center text-base font-medium text-muted-foreground"
          >
            Decades-long relationships with the institutions we&apos;re proud to call partners.
          </motion.p>
        </section>
      </div>

      <TieUpRow />

      {/* 4 — FAQs */}
      <div className="relative z-10 mx-auto max-w-5xl px-6">
        <section className="mt-24">
          <motion.h2
            {...reveal}
            className="text-center font-display text-3xl font-semibold text-foreground md:text-4xl"
          >
            FAQs
          </motion.h2>
          <div className="mx-auto mt-10 max-w-3xl space-y-4">
            {faqs.map((f, i) => (
              <FaqPanel
                key={f.q}
                q={f.q}
                a={f.a}
                open={openFaq === i}
                onToggle={() => setOpenFaq(openFaq === i ? null : i)}
              />
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}

/**
 * The row breaks out of the column so it can run edge to edge like the homepage
 * institution row. `overflow-x: auto` also clips vertically, so the top padding
 * reserves room for the badge that pokes above each oval.
 *
 * Exactly three cards fill a frame, which leaves no natural peek at a fourth —
 * so the cue that ten more exist lives below the row: chevrons that step one
 * card at a time and a live "1–3 of 13" counter. An edge fade was rejected
 * because it would dim the third card's badge, which sits right at the edge.
 */
function TieUpRow() {
  const ref = useRef<HTMLUListElement>(null);
  const [first, setFirst] = useState(0);
  const [atEnd, setAtEnd] = useState(false);

  const slot = useCallback(() => {
    const ul = ref.current;
    const items = ul?.querySelectorAll<HTMLLIElement>("li");
    if (!ul || !items || items.length < 2) return 1;
    return items[1]!.offsetLeft - items[0]!.offsetLeft;
  }, []);
  const sync = useCallback(() => {
    const ul = ref.current;
    if (!ul) return;
    setFirst(Math.round(ul.scrollLeft / slot()));
    setAtEnd(ul.scrollLeft + ul.clientWidth >= ul.scrollWidth - 4);
  }, [slot]);
  useEffect(() => {
    sync();
    window.addEventListener("resize", sync);
    return () => window.removeEventListener("resize", sync);
  }, [sync]);
  const step = (dir: 1 | -1) => ref.current?.scrollBy({ left: dir * slot(), behavior: "smooth" });

  const visible = Math.min(3, tieUps.length - first);
  const label = `${first + 1}–${first + visible} of ${tieUps.length}`;

  return (
    <div className="relative z-10">
      <ul
        ref={ref}
        onScroll={sync}
        aria-label="Institutions we work with"
        className="no-scrollbar mt-10 flex snap-x snap-mandatory gap-5 overflow-x-auto px-6 pb-8 pt-8 md:px-12"
      >
        {tieUps.map((t, i) => (
          <li key={t.name} className="shrink-0 snap-center pr-12">
            {/*
              The one deliberate departure from dark-on-dark: the oval is filled
              with the site's own warm-white so each partnership reads as a small
              point of light on the page. Charcoal text for contrast inside.
            */}
            <div
              /* Exactly three per frame at any width: a third of the row minus the
                 badge overhang (li pr-12) and the gap (gap-5), measured from the left padding only so
                 the fourth card starts exactly at the viewport edge rather than peeking in. Narrow screens get a fixed width. */
              className="spectrum-border group relative flex min-h-[10.6rem] w-[19rem] items-center rounded-full py-6 pl-9 pr-28 transition-all duration-400 hover:-translate-y-1.5 hover:shadow-[0_18px_44px_-16px_rgba(139,92,246,0.55)] md:w-[calc((100vw-3rem)/3-4.25rem)]"
              style={{ backgroundColor: "#F6F4F1" }}
            >
              {/* On the right edge, sized so three-plus cards share a frame; the oval is
                  tall enough that it pokes above only. `z-[2]` lifts it over the oval's
                  own hairline, which `spectrum-border` paints on a z-index:1 ::before —
                  without it the hairline draws straight across the photo. */}
              <span className="spectrum-border spectrum-border-thick absolute -right-12 -top-5 z-[2] block h-[9.6rem] w-[9.6rem] rounded-full bg-[#221F29] p-[3px] group-hover:before:[animation-duration:3s]">
                <img
                  src={campusFor(i)}
                  alt=""
                  loading="lazy"
                  draggable={false}
                  className="h-full w-full rounded-full object-cover"
                />
              </span>
              <div>
                <p className="font-display text-lg font-semibold leading-snug text-[#1C1A22] md:text-xl">
                  {t.name}
                </p>
                <p className="mt-2 text-base font-medium text-[#1C1A22]/70">
                  Tied up for {t.years} years
                </p>
              </div>
            </div>
          </li>
        ))}
      </ul>

      <div className="mt-2 flex items-center justify-center gap-5">
        <button
          type="button"
          aria-label="Previous institutions"
          onClick={() => step(-1)}
          disabled={first === 0}
          className="spectrum-border glass grid h-11 w-11 place-items-center rounded-full text-foreground transition-all hover:-translate-y-0.5 disabled:cursor-default disabled:opacity-35 disabled:hover:translate-y-0"
        >
          <ChevronLeft className="h-5 w-5" />
        </button>
        <span
          aria-live="polite"
          className="min-w-[6.5rem] text-center font-display text-sm tracking-[0.12em] text-muted-foreground"
        >
          {label}
        </span>
        <button
          type="button"
          aria-label="More institutions"
          onClick={() => step(1)}
          disabled={atEnd}
          className="spectrum-border glass grid h-11 w-11 place-items-center rounded-full text-foreground transition-all hover:-translate-y-0.5 disabled:cursor-default disabled:opacity-35 disabled:hover:translate-y-0"
        >
          <ChevronRight className="h-5 w-5" />
        </button>
      </div>
    </div>
  );
}

function FaqPanel({
  q,
  a,
  open,
  onToggle,
}: {
  q: string;
  a: string;
  open: boolean;
  onToggle: () => void;
}) {
  const [hover, setHover] = useState(false);
  // The gradient hairline appears on hover while collapsed and stays lit while
  // open — so the class is driven by state rather than a CSS :hover rule.
  const lit = open || hover;
  return (
    <motion.div
      {...reveal}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      className={`glass overflow-hidden rounded-2xl ${lit ? "spectrum-border" : ""}`}
    >
      <button
        type="button"
        aria-expanded={open}
        onClick={onToggle}
        className="flex w-full items-center justify-between gap-4 px-6 py-5 text-left font-display text-base text-foreground md:text-lg"
      >
        {q}
        <motion.span
          animate={{ rotate: open ? 45 : 0 }}
          transition={{ type: "spring", stiffness: 320, damping: 24 }}
          className="spectrum-fill grid h-7 w-7 shrink-0 place-items-center rounded-full"
        >
          <Plus className="h-4 w-4" />
        </motion.span>
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            key="answer"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.32, ease: [0.4, 0, 0.2, 1] }}
            className="overflow-hidden"
          >
            <p className="px-6 pb-6 text-sm font-medium leading-relaxed text-muted-foreground md:text-base">
              {a}
            </p>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
