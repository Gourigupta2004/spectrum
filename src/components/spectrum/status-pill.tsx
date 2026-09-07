import { Lock, PencilLine } from "lucide-react";
import { captionStatusLabel, type CaptionStatus } from "@/lib/caption-data";

export function StatusPill({
  status,
  className = "",
}: {
  status: CaptionStatus;
  className?: string;
}) {
  const base =
    "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[0.68rem] font-semibold uppercase tracking-[0.12em]";

  // Locked: the only solid pill on the board, so it reads as final at a glance.
  if (status === "approved") {
    return (
      <span className={`${base} bg-teal text-[#10281f] ${className}`}>
        <Lock className="h-3.5 w-3.5" />
        {captionStatusLabel[status]}
      </span>
    );
  }

  // Corrected is still in flight (Spectrum reviews it next), so it is outlined
  // like the other pending states rather than filled like Approved.
  if (status === "corrected") {
    return (
      <span
        className={`${base} border border-teal bg-[#221f29]/85 text-teal backdrop-blur-sm ${className}`}
      >
        <PencilLine className="h-3.5 w-3.5" />
        {captionStatusLabel[status]}
      </span>
    );
  }

  // The institution still owes us the text.
  if (status === "needs-caption") {
    return (
      <span
        className={`${base} border border-[#ffc93c] bg-[#221f29]/85 text-[#ffd978] backdrop-blur-sm ${className}`}
      >
        {captionStatusLabel[status]}
      </span>
    );
  }

  if (status === "needs-correction") {
    return (
      <span
        className={`${base} border border-[#e8503a] bg-[#221f29]/85 text-[#ff9b6a] backdrop-blur-sm ${className}`}
      >
        {captionStatusLabel[status]}
      </span>
    );
  }

  return (
    <span
      className={`${base} border border-violet bg-[#221f29]/85 text-[#c4b1ff] backdrop-blur-sm ${className}`}
    >
      {captionStatusLabel[status]}
    </span>
  );
}
