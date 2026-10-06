import { createFileRoute, Link } from "@tanstack/react-router";
import { motion } from "motion/react";
import { Camera, IdCard, Users } from "lucide-react";
import { useWorkspaceSummary } from "@/lib/portal-data";
import { usePortalCopy } from "@/lib/use-portal-copy";

export const Route = createFileRoute("/portal/workspace/")({
  head: () => ({
    meta: [
      { title: "Institution Workspace — Spectrum" },
      {
        name: "description",
        content:
          "Choose between reviewing photo titles for class photographs and naming students in individual photographs.",
      },
      { property: "og:title", content: "Institution Workspace — Spectrum" },
      {
        property: "og:description",
        content: "Review photo titles or build a labelled class roster.",
      },
    ],
  }),
  component: WorkspaceBranch,
});

function WorkspaceBranch() {
  const copy = usePortalCopy();
  const { pending, named, total: totalStudents } = useWorkspaceSummary();
  const complete = totalStudents > 0 && named >= totalStudents;

  return (
    <div>
      <h1 className="font-display text-4xl text-foreground md:text-5xl">{copy.workspaceTitle}</h1>
      <p className="mt-2 text-sm font-medium text-muted-foreground">{copy.workspaceSubtitle}</p>

      {/* Two to a row at every width: Class Photographs and Individual
          Photographs are the pair a teacher chooses between, and ID Cards
          waits below rather than joining them. */}
      <div className="mt-10 grid gap-6 md:grid-cols-2">
        <BranchCard
          to="/portal/workspace/events"
          icon={<Camera className="h-7 w-7 text-foreground" />}
          title={copy.eventsCardTitle}
          copy={copy.eventsCardCopy}
          index={0}
          badge={
            <span className="inline-flex rounded-full border border-[#e8503a] px-3 py-1 text-[0.72rem] sm:text-[0.68rem] font-semibold uppercase tracking-[0.12em] text-[#ff9b6a]">
              {pending} pending
            </span>
          }
        />
        <BranchCard
          to="/portal/workspace/students"
          icon={<Users className="h-7 w-7 text-foreground" />}
          title={copy.studentsCardTitle}
          copy={copy.studentsCardCopy}
          index={1}
          badge={
            <span
              className={`inline-flex rounded-full border px-3 py-1 text-[0.72rem] sm:text-[0.68rem] font-semibold uppercase tracking-[0.12em] ${
                complete ? "border-teal text-teal" : "border-border text-muted-foreground"
              }`}
            >
              {named} / {totalStudents} named
            </span>
          }
        />
        {/* No page behind this one yet, so it is shown but cannot be opened. */}
        <BranchCard
          icon={<IdCard className="h-7 w-7 text-foreground" />}
          title={copy.idcardsCardTitle}
          copy={copy.idcardsCardCopy}
          index={2}
          ribbon={copy.idcardsCardBadge}
        />
      </div>
    </div>
  );
}

function BranchCard({
  to,
  icon,
  title,
  copy,
  badge,
  ribbon,
  index,
}: {
  /** Where the card leads. Leave out for a workspace that is announced but not built. */
  to?: "/portal/workspace/events" | "/portal/workspace/students";
  icon: React.ReactNode;
  title: string;
  copy: string;
  /** The live cards' progress pill. */
  badge?: React.ReactNode;
  /** Set instead of `badge` on a card with nothing behind it yet. */
  ribbon?: string;
  index: number;
}) {
  const body = (
    <>
      {ribbon && (
        /* Across the card's own corner, so the state is read before the title
           rather than after the description. */
        <span className="spectrum-border glass absolute right-5 top-5 rounded-full px-3 py-1.5 font-display text-[0.7rem] font-semibold uppercase tracking-[0.16em] text-foreground">
          {ribbon}
        </span>
      )}
      <span className="spectrum-border spectrum-border-thick grid h-16 w-16 place-items-center rounded-full">
        {icon}
      </span>
      <h2 className="mt-6 font-display text-2xl text-foreground">{title}</h2>
      <p className="mt-2 max-w-sm text-sm font-medium text-muted-foreground">{copy}</p>
      {badge && <div className="mt-5">{badge}</div>}
    </>
  );
  return (
    <motion.div
      initial={{ opacity: 0, y: 22 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: index * 0.08 }}
    >
      {to ? (
        <Link
          to={to}
          className="spectrum-border group relative block h-full rounded-2xl bg-surface p-8 transition-transform duration-500 hover:-translate-y-1.5"
        >
          {body}
        </Link>
      ) : (
        /* Same card, without the link, the lift or the pointer — it is
           deliberately inert, and sits well back so the two live workspaces
           read as the choices and this one as a note about what is coming. */
        <div
          aria-disabled="true"
          className="spectrum-border relative block h-full cursor-default rounded-2xl bg-surface p-8 opacity-45 saturate-50"
        >
          {body}
        </div>
      )}
    </motion.div>
  );
}
