/**
 * Writes every hardcoded fixture to ../Spectrum-backend/seed/fixtures.json so the
 * backend can seed its database (and download the images) with one command:
 *
 *   bun scripts/export-fixtures.ts
 *   cd ../Spectrum-backend && .venv/bin/python manage.py seed_fixtures
 */
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import {
  events,
  galleryPhotos,
  heroSlides,
  institutions,
  services,
} from "../src/lib/spectrum-data";
import { captionItems, portalInstitution } from "../src/lib/caption-data";
import { classes, seedNames, studentsOf } from "../src/lib/student-data";
import { capabilities, contactDetails, faqs, stats, story, tieUps } from "../src/lib/page-fixtures";

const out = resolve(import.meta.dir, "../../Spectrum-backend/seed/fixtures.json");

const data = {
  institutions,
  events: events.map((e, i) => ({ ...e, sortOrder: i })),
  // The demo has one gallery; every event gets it so each slug shows photos.
  gallery: galleryPhotos.map((p) => ({ title: p.title, image: p.image })),
  heroSlides: heroSlides.map((s) => ({ caption: s.caption, image: s.src })),
  services,
  stats,
  capabilities,
  story,
  tieUps,
  faqs,
  contactDetails,
  portal: {
    institutionId: portalInstitution.id,
    login: { username: "dps-newdelhi", password: "demo" },
    event: events.find((e) => e.institutionId === portalInstitution.id)?.slug,
    captions: captionItems.map((c, i) => ({
      key: c.id,
      momentTitle: c.momentTitle,
      image: c.image,
      caption: c.caption,
      correction: c.correction ?? "",
      requested: c.requested,
      status: c.status,
      updatedAt: c.updatedAt,
      actionBy: c.actionBy ?? "",
      sortOrder: i,
    })),
    classes: classes.map((cls, i) => ({
      id: cls.id,
      name: cls.name,
      group: cls.group,
      sortOrder: i,
      students: studentsOf(cls.id).map((s, k) => ({
        key: s.id,
        name: seedNames[s.id] ?? "",
        // Same hue formula as avatar() in student-data.ts.
        hue: ((cls.name.charCodeAt(0) + k * 7 + cls.size) * 47) % 360,
      })),
    })),
  },
};

mkdirSync(dirname(out), { recursive: true });
writeFileSync(out, JSON.stringify(data, null, 2));
console.log(`Wrote ${out}`);
