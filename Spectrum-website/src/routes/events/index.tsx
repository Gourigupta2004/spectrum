import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { Search, X } from "lucide-react";
import { EventCard } from "@/components/spectrum/event-card";
import { Orb } from "@/components/spectrum/orb";
import { Highlight } from "@/components/spectrum/highlight";
import { getEvents } from "@/lib/data/events";
import { seoMeta } from "@/lib/data/site";
import type { Institution, SpectrumEvent } from "@/lib/spectrum-data";

type Search = { institution?: string; q?: string };

export const Route = createFileRoute("/events/")({
  validateSearch: (search: Record<string, unknown>): Search => {
    const out: Search = {};
    if (typeof search["institution"] === "string") out.institution = search["institution"];
    if (typeof search["q"] === "string" && search["q"].trim()) out.q = search["q"].trim();
    return out;
  },
  loader: () => getEvents(),
  staleTime: 60_000,
  head: ({ loaderData }) => ({ meta: seoMeta(loaderData?.seo) }),
  component: EventsPage,
});

const norm = (s: string) =>
  s
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .trim();

/** Every word of the query has to appear somewhere in the event or its institution. */
function matches(query: string, e: SpectrumEvent, inst: Institution | undefined): boolean {
  const words = norm(query).split(" ").filter(Boolean);
  if (!words.length) return true;
  const hay = norm(
    [e.name, e.institution, e.date, inst?.short ?? "", inst?.city ?? "", ...e.tags].join(" "),
  );
  return words.every((w) => hay.includes(w));
}

function EventsPage() {
  const { institution, q } = Route.useSearch();
  const { copy, types, events, institutions } = Route.useLoaderData();
  // "All"/"Recent"/"Popular" are fixed; between them one chip per institution
  // type, straight from the admin (type: prefix keeps ids from colliding).
  const filters = [
    { key: "All", label: copy.filterAll },
    ...types.map((t) => ({ key: `type:${t.id}`, label: t.label })),
    { key: "Recent", label: copy.filterRecent },
    { key: "Popular", label: copy.filterPopular },
  ];
  const [filter, setFilter] = useState("All");
  const [inst, setInst] = useState<string | undefined>(institution);
  const [query, setQuery] = useState(q ?? "");
  // The URL is the source of truth when it changes (a new search from the
  // homepage, back/forward); typing here refines locally without rewriting it.
  useEffect(() => setQuery(q ?? ""), [q]);
  useEffect(() => setInst(institution), [institution]);

  const instObj = institutions.find((i) => i.id === inst);
  const byId = new Map(institutions.map((i) => [i.id, i]));

  const list = events.filter((e) => {
    if (inst && e.institutionId !== inst) return false;
    if (!matches(query, e, byId.get(e.institutionId))) return false;
    const type = e.institutionType ?? byId.get(e.institutionId)?.type;
    if (filter.startsWith("type:")) return type === filter.slice("type:".length);
    if (filter === "Recent") return e.tags.includes("recent");
    if (filter === "Popular") return e.tags.includes("popular");
    return true;
  });

  return (
    <div className="grain relative min-h-screen overflow-x-clip pb-24 pt-28">
      <Orb
        className="left-[-8%] top-10"
        colors={["#f7c21f", "#e8503a"]}
        size={520}
        opacity={0.09}
      />
      <div className="relative z-10 mx-auto max-w-6xl px-6">
        <Link
          to="/"
          className="-my-1 inline-flex min-h-11 items-center text-xs text-muted-foreground transition-colors hover:text-teal"
        >
          ← {copy.backLabel}
        </Link>

        <motion.h1
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-6 font-display text-4xl text-foreground md:text-5xl"
        >
          <Highlight text={copy.title} />
        </motion.h1>

        <div className="mt-8 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          {/* Bled to the screen edges on a phone so a chip scrolling past the
              edge reads as "more this way" instead of as a clipped row. */}
          <div className="no-scrollbar -mx-6 flex gap-3 overflow-x-auto px-6 pb-2 md:mx-0 md:px-0 md:pb-0">
            {filters.map((f) => (
              <button
                key={f.key}
                onClick={() => {
                  setFilter(f.key);
                  if (f.key === "All") setInst(undefined);
                }}
                className={`spectrum-border shrink-0 rounded-full px-5 py-2 text-xs transition-colors ${
                  filter === f.key && !(f.key === "All" && inst)
                    ? "bg-violet text-foreground"
                    : "text-foreground"
                }`}
              >
                {f.label}
              </button>
            ))}
            {instObj && (
              <button
                onClick={() => setInst(undefined)}
                className="spectrum-border shrink-0 rounded-full bg-violet px-5 py-2 text-xs text-foreground"
              >
                {instObj.name} ×
              </button>
            )}
          </div>

          <form
            role="search"
            onSubmit={(e) => e.preventDefault()}
            className="spectrum-border glass flex items-center gap-2 rounded-full p-1 md:w-72 md:shrink-0"
          >
            <Search className="ml-3 h-4 w-4 shrink-0 text-muted-foreground" />
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={copy.searchPlaceholder}
              aria-label={copy.searchPlaceholder}
              autoComplete="off"
              className="min-w-0 flex-1 bg-transparent py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none [&::-webkit-search-cancel-button]:hidden"
            />
            {query && (
              <button
                type="button"
                onClick={() => setQuery("")}
                aria-label="Clear search"
                className="mr-1 grid h-7 w-7 shrink-0 place-items-center rounded-full text-muted-foreground transition-colors hover:bg-white/10 hover:text-foreground"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </form>
        </div>

        <div className="mt-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {list.map((e, i) => (
            <EventCard
              key={e.slug}
              event={e}
              index={i}
              photosLabel={copy.photosLabel}
              pricePrefix={copy.pricePrefix}
            />
          ))}
        </div>
        {list.length === 0 && (
          <p className="mt-16 text-center text-sm text-muted-foreground">
            {query.trim() ? copy.searchEmpty.replace("{query}", query.trim()) : copy.emptyState}
          </p>
        )}
      </div>
    </div>
  );
}
