import { useMatch } from "@tanstack/react-router";
import { portalCopy, type PortalCopy } from "./data/defaults";

/** Portal wording, loaded once by the /portal layout route. */
export function usePortalCopy(): PortalCopy {
  const match = useMatch({ from: "/portal", shouldThrow: false });
  return (match?.loaderData as PortalCopy | undefined) ?? portalCopy;
}
