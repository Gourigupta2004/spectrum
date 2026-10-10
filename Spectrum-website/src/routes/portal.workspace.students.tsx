import { createFileRoute, Outlet } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { GuidelinesModal } from "@/components/spectrum/guidelines-modal";
import { rosterGuidelines } from "@/lib/guidelines";
import { RosterGuidelinesContext } from "@/lib/roster-guidelines";
import { usePortalCopy } from "@/lib/use-portal-copy";

export const Route = createFileRoute("/portal/workspace/students")({
  component: StudentsSection,
});

/**
 * The Individual Photographs section: the class list and every class page sit
 * inside it. Its guidelines greet each visit to the section — whether it is
 * entered at the class list or straight on a class — but not every hop between
 * classes, since this layout stays mounted while the teacher moves around
 * inside it. Opened after mount, so the server render never paints the modal.
 */
function StudentsSection() {
  const copy = usePortalCopy();
  const [open, setOpen] = useState(false);
  useEffect(() => setOpen(true), []);

  return (
    <RosterGuidelinesContext.Provider value={() => setOpen(true)}>
      <Outlet />
      <GuidelinesModal
        open={open}
        onClose={() => setOpen(false)}
        content={rosterGuidelines(copy)}
      />
    </RosterGuidelinesContext.Provider>
  );
}
