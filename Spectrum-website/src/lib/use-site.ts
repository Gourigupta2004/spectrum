import { useMatch } from "@tanstack/react-router";
import { fallbackSite, type SiteData } from "./data/site";

/** Site settings loaded once by the root route (logos, nav labels, intro, error copy). */
export function useSite(): SiteData {
  const match = useMatch({ from: "__root__", shouldThrow: false });
  return (match?.loaderData as SiteData | undefined) ?? fallbackSite;
}
