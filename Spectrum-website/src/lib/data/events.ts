import { notFound } from "@tanstack/react-router";
import { ApiError, apiFetch, hasApi } from "../api";
import {
  BUNDLE_PRICE,
  bundleSavings,
  events,
  galleryEvent,
  galleryPhotos,
  institutions,
  type Institution,
  type Photo,
  type SpectrumEvent,
} from "../spectrum-data";
import { fill } from "../text";
import { eventsCopy, galleryCopy, type EventsCopy, type GalleryCopy } from "./defaults";
import type { Seo } from "./site";

/** An institution type as a filter chip: id matches Institution.type, label is what the chip says. */
export type InstitutionType = { id: string; label: string };

export type EventsData = {
  seo: Seo;
  copy: EventsCopy;
  types: InstitutionType[];
  events: SpectrumEvent[];
  institutions: Institution[];
};

const fallbackTypes: InstitutionType[] = [
  { id: "school", label: "Schools" },
  { id: "college", label: "Colleges" },
];

export type EventDetail = SpectrumEvent & { bundlePrice: number; bundleSavings: number };
export type GalleryData = { event: EventDetail; photos: Photo[]; seo: Seo; copy: GalleryCopy };

export async function getEvents(): Promise<EventsData> {
  if (hasApi) {
    const data = await apiFetch<EventsData>("/api/events/");
    return { ...data, copy: { ...eventsCopy, ...data.copy }, types: data.types ?? fallbackTypes };
  }
  return {
    seo: {
      title: "All Events — Spectrum Event Photography",
      description:
        "Browse every school and college event captured by Spectrum — annual days, sports meets, graduations and cultural fests.",
      ogTitle: "All Events — Spectrum",
      ogDescription: "Browse every school and college event captured by Spectrum.",
    },
    copy: eventsCopy,
    types: fallbackTypes,
    events,
    institutions,
  };
}

export async function getEvent(slug: string): Promise<GalleryData> {
  if (hasApi) {
    try {
      const data = await apiFetch<GalleryData>(`/api/events/${encodeURIComponent(slug)}/`);
      return { ...data, copy: { ...galleryCopy, ...data.copy } };
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) throw notFound();
      throw error;
    }
  }
  // Demo mode: every slug shows the one hardcoded gallery.
  const event = galleryEvent;
  const vars = { event: event.name, institution: event.institution };
  return {
    event: { ...event, bundlePrice: BUNDLE_PRICE, bundleSavings },
    photos: galleryPhotos,
    seo: {
      title: fill(galleryCopy.seoTitleTemplate, vars),
      description: fill(galleryCopy.seoDescriptionTemplate, vars),
    },
    copy: galleryCopy,
  };
}
