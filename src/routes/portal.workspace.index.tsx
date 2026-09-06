import { createFileRoute, Link } from "@tanstack/react-router";
import { motion } from "motion/react";
import { Camera, IdCard } from "lucide-react";
import { captionStore, namesStore, useStore } from "@/lib/portal-store";
import { totalStudents } from "@/lib/student-data";

export const Route = createFileRoute("/portal/workspace/")({
  head: () => ({
    meta: [
      { title: "Institution Workspace — Spectrum" },
      {
        name: "description",
        content:
          "Choose between reviewing event photo captions and naming students in class photos.",
      },
      { property: "og:title", content: "Institution Workspace — Spectrum" },
      {
        property: "og:description",
        content: "Review event captions or build a labelled class roster.",
      },
    ],
  }),
  component: WorkspaceBranch,
});

function WorkspaceBranch() {
  const items = useStore(captionStore);
  const names = useStore(namesStore);

  const pending = items.filter(
    (i) => i.status !== "approved" && i.status !== "corrected",
  ).length;
  const named = Object.values(names).filter((n) => n.trim().length > 0).length;
  const complete = named >= totalStudents;

  return (
    <div>
      <h1 className="font-display text-4xl text-foreground md:text-5xl">
        What would you like to work on?
      </h1>
      <p className="mt-2 text-sm font-medium text-muted-foreground">
        Two workspaces, one institution account.
      </p>

      <div className="mt-10 grid gap-6 md:grid-cols-2">
        <BranchCard
          to="/portal/workspace/events"
          icon={<Camera className="h-7 w-7 text-foreground" />}
          title="Events"
          copy="Review and correct photo captions for event moments."
          index={0}
          badge={
            <span className="inline-flex rounded-full border border-[#e8503a] px-3 py-1 text-[0.68rem] font-semibold uppercase tracking-[0.12em] text-[#ff9b6a]">
              {pending} pending
            </span>
          }
        />
        <BranchCard
          to="/portal/workspace/students"
          icon={<IdCard className="h-7 w-7 text-foreground" />}
          title="Students"
          copy="Identify students in class photos and export a labeled roster."
          index={1}
          badge={
            <span
              className={`inline-flex rounded-full border px-3 py-1 text-[0.68rem] font-semibold uppercase tracking-[0.12em] ${
                complete
                  ? "border-teal text-teal"
                  : "border-border text-muted-foreground"
              }`}
            >
              {named} / {totalStudents} named
            </span>
          }
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
  index,
}: {
  to: "/portal/workspace/events" | "/portal/workspace/students";
  icon: React.ReactNode;
  title: string;
  copy: string;
  badge: React.ReactNode;
  index: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 22 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: index * 0.08 }}
    >
      <Link
        to={to}
        className="spectrum-border group block h-full rounded-2xl bg-surface p-8 transition-transform duration-500 hover:-translate-y-1.5"
      >
        <span className="spectrum-border spectrum-border-thick grid h-16 w-16 place-items-center rounded-full">
          {icon}
        </span>
        <h2 className="mt-6 font-display text-2xl text-foreground">{title}</h2>
        <p className="mt-2 max-w-sm text-sm font-medium text-muted-foreground">{copy}</p>
        <div className="mt-5">{badge}</div>
      </Link>
    </motion.div>
  );
}
