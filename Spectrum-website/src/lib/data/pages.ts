import { apiFetch, hasApi } from "../api";
import {
  events,
  heroSlides,
  institutions,
  services,
  type Institution,
  type SpectrumEvent,
} from "../spectrum-data";
import {
  capabilities,
  contactDetails,
  faqs,
  stats,
  story,
  tieUps,
  type ContactIcon,
} from "../page-fixtures";
import {
  aboutCopy,
  contactCopy,
  homeCopy,
  portalCopy,
  type AboutCopy,
  type ContactCopy,
  type HomeCopy,
  type PortalCopy,
} from "./defaults";
import type { Seo } from "./site";

export type HeroSlide = { id: number | string; src: string; caption: string };

export type HomeData = {
  seo: Seo;
  copy: HomeCopy;
  heroSlides: HeroSlide[];
  stats: { to: number; suffix: string; label: string }[];
  services: string[];
  institutions: Institution[];
  events: SpectrumEvent[];
};

export type AboutData = {
  seo: Seo;
  copy: AboutCopy;
  capabilities: string[];
  story: { title: string; body: string; image: string; alt: string }[];
  tieUps: { name: string; years: string; image: string }[];
  faqs: { q: string; a: string }[];
};

export type ContactData = {
  seo: Seo;
  copy: ContactCopy;
  services: string[];
  details: { icon: ContactIcon; label: string; value: string }[];
};

const withInstitutionRouting = (list: Institution[]): Institution[] =>
  list.map((inst) => {
    const own = events.filter((e) => e.institutionId === inst.id);
    return { ...inst, eventCount: own.length, firstEventSlug: own[0]?.slug ?? null };
  });

export async function getHome(): Promise<HomeData> {
  if (hasApi) {
    const data = await apiFetch<HomeData>("/api/pages/home/");
    return { ...data, copy: { ...homeCopy, ...data.copy } };
  }
  return {
    seo: {
      title: "Spectrum — School & College Event Photography",
      description:
        "Spectrum captures the events that define institutions. Browse protected galleries, choose your photos, and own your memories in full resolution.",
      ogTitle: "Spectrum — Every Moment, Yours Forever",
      ogDescription:
        "Premium event photography for schools and colleges. Browse, choose, and own your memories.",
    },
    copy: homeCopy,
    heroSlides: heroSlides.map((s) => ({ id: s.id, src: s.src, caption: s.caption ?? "" })),
    stats,
    services,
    institutions: withInstitutionRouting(institutions),
    events: events.slice(0, 6),
  };
}

export async function getAbout(): Promise<AboutData> {
  if (hasApi) {
    const data = await apiFetch<AboutData>("/api/pages/about/");
    return { ...data, copy: { ...aboutCopy, ...data.copy } };
  }
  return {
    seo: {
      title: "About Us — Spectrum",
      description:
        "Established in 1980, Spectrum has spent nearly five decades photographing the institutions of the NCR — from film to digital, all in-house.",
      ogTitle: "About Us — Spectrum",
      ogDescription:
        "Nearly five decades of experience, precision, and trust in institutional photography.",
    },
    copy: aboutCopy,
    capabilities,
    story,
    tieUps,
    faqs,
  };
}

export async function getContact(): Promise<ContactData> {
  if (hasApi) {
    const data = await apiFetch<ContactData>("/api/pages/contact/");
    return { ...data, copy: { ...contactCopy, ...data.copy } };
  }
  return {
    seo: {
      title: "Contact Spectrum — Book Event Photography",
      description:
        "Talk to Spectrum about covering your school or college event. Email, WhatsApp or send us a message and we'll plan the shoot.",
      ogTitle: "Contact Spectrum",
      ogDescription:
        "Get in touch with Spectrum for school and college event photography in India.",
    },
    copy: contactCopy,
    services,
    details: contactDetails,
  };
}

export type Enquiry = {
  name: string;
  email: string;
  phone: string;
  institution: string;
  service: string;
  serviceOther: string;
  message: string;
};

export async function submitEnquiry(enquiry: Enquiry): Promise<void> {
  if (!hasApi) return;
  await apiFetch("/api/contact/", { method: "POST", json: enquiry });
}

export async function getPortalCopy(): Promise<PortalCopy> {
  if (!hasApi) return portalCopy;
  try {
    const data = await apiFetch<{ copy: Partial<PortalCopy> }>("/api/pages/portal/");
    return { ...portalCopy, ...data.copy };
  } catch {
    return portalCopy;
  }
}
