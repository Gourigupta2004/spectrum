/** "{count} photos · ₹{price}" -> "3 photos · ₹87". Unknown keys are left as-is. */
export function fill(template: string, values: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (match, key: string) =>
    key in values ? String(values[key]) : match,
  );
}

/** Splits "Every Moment, [Yours] Forever" into plain and highlighted parts. */
export function highlightParts(text: string): { text: string; highlight: boolean }[] {
  const parts: { text: string; highlight: boolean }[] = [];
  const re = /\[([^\]]+)\]/g;
  let last = 0;
  for (let match = re.exec(text); match; match = re.exec(text)) {
    if (match.index > last) parts.push({ text: text.slice(last, match.index), highlight: false });
    parts.push({ text: match[1]!, highlight: true });
    last = match.index + match[0].length;
  }
  if (last < text.length) parts.push({ text: text.slice(last), highlight: false });
  return parts;
}

/** Plain text with the [brackets] removed, for titles and alt text. */
export const plain = (text: string): string => text.replace(/\[([^\]]+)\]/g, "$1");
