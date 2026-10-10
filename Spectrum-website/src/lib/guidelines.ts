import type { PortalCopy } from "./data/defaults";

/** What a guidelines popup says; each workspace section has its own, set in the admin. */
export type Guidelines = {
  title: string;
  intro: string;
  points: string;
  outro: string;
  dismiss: string;
};

/** Class Photographs (titles). */
export const titleGuidelines = (copy: PortalCopy): Guidelines => ({
  title: copy.guidelinesTitle,
  intro: copy.guidelinesIntro,
  points: copy.guidelinesPoints,
  outro: copy.guidelinesOutro,
  dismiss: copy.guidelinesDismiss,
});

/** Individual Photographs (naming students). */
export const rosterGuidelines = (copy: PortalCopy): Guidelines => ({
  title: copy.rosterGuidelinesTitle,
  intro: copy.rosterGuidelinesIntro,
  points: copy.rosterGuidelinesPoints,
  outro: copy.rosterGuidelinesOutro,
  dismiss: copy.rosterGuidelinesDismiss,
});
