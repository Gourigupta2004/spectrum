import { createContext, useContext } from "react";

/**
 * Reopens the Individual Photographs guidelines from anywhere in that section.
 * The section's layout route owns the popup and provides this.
 */
export const RosterGuidelinesContext = createContext<() => void>(() => {});

export const useOpenRosterGuidelines = () => useContext(RosterGuidelinesContext);
