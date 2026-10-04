import { apiFetch, hasApi } from "../api";
import { siteCopy, type SiteCopy } from "./defaults";

export type Seo = { title: string; description: string; ogTitle?: string; ogDescription?: string };

export type SiteData = {
  logoLight: string;
  logoMark: string;
  favicon: string;
  introVideoWebm: string;
  introVideoMp4: string;
  /** Licensed intro sting (MP3); empty string when none is uploaded. */
  introAudio: string;
  /** Soft session-long background loop; empty string when none is uploaded. */
  sessionAudio: string;
  copy: SiteCopy;
  seo: Seo;
};

export const fallbackSite: SiteData = {
  logoLight: "/spectrum-logo-light.png",
  logoMark: "/spectrum-mark.png",
  favicon: "/favicon.png",
  introVideoWebm: "/spr-intro.webm",
  introVideoMp4: "/spr-intro.mp4",
  introAudio: "",
  sessionAudio: "",
  copy: siteCopy,
  seo: {
    title: "Spectrum — Every Moment, Yours Forever",
    description: "Spectrum captures school and college events across India.",
    ogTitle: "Spectrum — Every Moment, Yours Forever",
    ogDescription: "Premium school and college event photography.",
  },
};

/** Site chrome never takes the whole site down: on an API error it logs and uses the defaults. */
export async function getSite(): Promise<SiteData> {
  if (!hasApi) return fallbackSite;
  try {
    const data = await apiFetch<SiteData>("/api/site/");
    return {
      ...data,
      logoLight: data.logoLight || fallbackSite.logoLight,
      logoMark: data.logoMark || fallbackSite.logoMark,
      favicon: data.favicon || fallbackSite.favicon,
      introVideoWebm: data.introVideoWebm || fallbackSite.introVideoWebm,
      introVideoMp4: data.introVideoMp4 || fallbackSite.introVideoMp4,
      introAudio: data.introAudio || "",
      sessionAudio: data.sessionAudio || "",
      copy: { ...siteCopy, ...data.copy },
    };
  } catch (error) {
    console.error("Site settings unavailable, using defaults", error);
    return fallbackSite;
  }
}

/** Standard meta tags for a route's head(). */
export function seoMeta(seo: Seo | undefined) {
  if (!seo) return [];
  return [
    { title: seo.title },
    { name: "description", content: seo.description },
    { property: "og:title", content: seo.ogTitle || seo.title },
    { property: "og:description", content: seo.ogDescription || seo.description },
  ];
}
