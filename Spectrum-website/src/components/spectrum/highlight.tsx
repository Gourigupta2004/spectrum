import { Fragment } from "react";
import { highlightParts } from "@/lib/text";

/** Renders admin text where [bracketed] words take the animated Spectrum gradient. */
export function Highlight({ text }: { text: string }) {
  return (
    <>
      {highlightParts(text).map((part, i) =>
        part.highlight ? (
          <span key={i} className="spectrum-text">
            {part.text}
          </span>
        ) : (
          <Fragment key={i}>{part.text}</Fragment>
        ),
      )}
    </>
  );
}
