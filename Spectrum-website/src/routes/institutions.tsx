import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { motion } from "motion/react";
import { Orb } from "@/components/spectrum/orb";
import { Highlight } from "@/components/spectrum/highlight";
import { getEvents } from "@/lib/data/events";
import { seoMeta } from "@/lib/data/site";
import { fill } from "@/lib/text";

/**
 * Step one of the funnel: pick your institution, then land on its events.
 * The type chips (Schools, Colleges, …) come from the admin's institution
 * types, so new types appear here on their own.
 */
export const Route = createFileRoute("/institutions")({
  loader: () => getEvents(),
  staleTime: 60_000,
  head: ({ loaderData }) => ({ meta: seoMeta(loaderData?.seo) }),
  component: InstitutionsPage,
});

function InstitutionsPage() {
  const navigate = useNavigate();
  const { copy, types, institutions } = Route.useLoaderData();
  const [filter, setFilter] = useState("All");

  const chips = [
    { key: "All", label: copy.filterAll },
    ...types.map((t) => ({ key: t.id, label: t.label })),
  ];
  const list = institutions.filter((i) => filter === "All" || i.type === filter);

  return (
    <div className="grain relative min-h-screen overflow-x-clip pb-24 pt-28">
      <Orb
        className="left-[-8%] top-10"
        colors={["#7C4DE0", "#2FBF8F"]}
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
          className="mt-6 text-center font-display text-4xl text-foreground md:text-5xl"
        >
          <Highlight text={copy.browseTitle} />
        </motion.h1>
        <p className="mx-auto mt-3 max-w-xl text-center text-sm font-medium text-muted-foreground md:text-base">
          {copy.browseSubtitle}
        </p>

        <div className="no-scrollbar -mx-6 mt-8 flex justify-start gap-3 overflow-x-auto px-6 pb-2 sm:justify-center md:mx-0 md:px-0">
          {chips.map((c) => (
            <button
              key={c.key}
              onClick={() => setFilter(c.key)}
              className={`spectrum-border shrink-0 rounded-full px-5 py-2 text-xs transition-colors ${
                filter === c.key ? "bg-violet text-foreground" : "text-foreground"
              }`}
            >
              {c.label}
            </button>
          ))}
        </div>

        <div className="mt-12 grid grid-cols-2 gap-x-6 gap-y-10 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
          {list.map((inst, i) => (
            <motion.button
              key={inst.id}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35, delay: Math.min(i, 14) * 0.04 }}
              onClick={() => navigate({ to: "/events", search: { institution: inst.id } })}
              className="group flex flex-col items-center gap-3 text-center"
            >
              <span className="spectrum-border spectrum-border-thick relative block h-28 w-28 rounded-full p-[3px] transition-all duration-400 group-hover:-translate-y-1 group-hover:shadow-[0_16px_40px_-14px_rgba(139,92,246,0.7)] sm:h-32 sm:w-32">
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
              <span className="line-clamp-2 font-display text-[0.72rem] uppercase leading-[1.25] tracking-[0.1em] text-foreground">
                {inst.short}
              </span>
              {typeof inst.eventCount === "number" && inst.eventCount > 0 && (
                <span className="-mt-2 text-[0.68rem] text-muted-foreground">
                  {fill(copy.browseEventsTemplate, { count: inst.eventCount })}
                </span>
              )}
            </motion.button>
          ))}
        </div>
        {list.length === 0 && (
          <p className="mt-16 text-center text-sm text-muted-foreground">{copy.emptyState}</p>
        )}
      </div>
    </div>
  );
}
