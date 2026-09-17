import { createFileRoute, Link } from "@tanstack/react-router";
import { motion } from "motion/react";
import { Download } from "lucide-react";
import { Orb } from "@/components/spectrum/orb";
import { galleryCopy } from "@/lib/data/defaults";
import { ApiError } from "@/lib/api";
import { getDownload } from "@/lib/data/orders";
import { fill } from "@/lib/text";

export const Route = createFileRoute("/downloads/$token")({
  // Private to the buyer: never render it on the server or let it be indexed.
  ssr: false,
  head: () => ({
    meta: [{ title: "Your photos — Spectrum" }, { name: "robots", content: "noindex" }],
  }),
  loader: ({ params }) => getDownload(params.token),
  errorComponent: MissingDownload,
  component: DownloadPage,
});

function DownloadPage() {
  const data = Route.useLoaderData();
  const copy = galleryCopy;

  return (
    <div className="grain relative min-h-screen overflow-x-clip pb-24 pt-28">
      <Orb
        className="right-[-6%] top-6"
        colors={["#2fbf8f", "#8b5cf6"]}
        size={520}
        opacity={0.09}
      />
      <div className="relative z-10 mx-auto max-w-6xl px-6">
        <p className="text-[0.72rem] sm:text-[0.68rem] uppercase tracking-[0.22em] text-teal">
          Order {data.publicId}
        </p>
        <h1 className="mt-2 font-display text-4xl text-foreground md:text-5xl">
          {copy.downloadTitle}
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          {fill(copy.downloadSubtitle, {
            event: data.event.name,
            institution: data.event.institution,
          })}
          {" · "}
          {data.items.length} photos
        </p>

        {data.zipUrl && (
          <a
            href={data.zipUrl}
            className="spectrum-fill mt-8 inline-flex items-center gap-2 rounded-full px-6 py-3 text-sm font-semibold"
          >
            <Download className="h-4 w-4" /> {copy.downloadAll}
          </a>
        )}

        {data.preparing ? (
          <p className="mt-10 text-sm text-muted-foreground">
            Your photos are being prepared. Refresh this page in a minute.
          </p>
        ) : (
          <div className="mt-10 grid grid-cols-2 gap-4 md:grid-cols-4">
            {data.items.map((item, i) => (
              <motion.a
                key={item.id}
                href={item.url}
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.35, delay: Math.min(i, 12) * 0.03 }}
                className="spectrum-border group relative block aspect-[4/5] overflow-hidden rounded-2xl"
              >
                {item.thumb && (
                  <img
                    src={item.thumb}
                    alt={item.title}
                    loading="lazy"
                    className="absolute inset-0 h-full w-full object-cover transition-transform duration-700 group-hover:scale-105"
                  />
                )}
                <span className="absolute inset-x-0 bottom-0 flex items-center justify-between gap-2 bg-gradient-to-t from-[#1C1A22] to-transparent p-3">
                  <span className="truncate font-display text-sm text-foreground">
                    {item.title}
                  </span>
                  <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-black/50 px-2.5 py-1 text-[0.7rem] sm:text-[0.65rem] font-semibold text-foreground">
                    <Download className="h-3 w-3" /> {copy.downloadOne}
                  </span>
                </span>
              </motion.a>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function MissingDownload({ error }: { error: Error }) {
  const invalid = error instanceof ApiError && error.status === 404;
  return (
    <div className="grid min-h-screen place-items-center px-6 text-center">
      <div>
        <p className="text-sm text-muted-foreground">
          {invalid
            ? galleryCopy.downloadMissing
            : "Could not load your photos right now. Please try again in a moment."}
        </p>
        <Link to="/events" className="mt-6 inline-block text-sm text-teal">
          {galleryCopy.successBack}
        </Link>
      </div>
    </div>
  );
}
