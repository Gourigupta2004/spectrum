/**
 * Photos are shown at the proportions they were uploaded in — this is a
 * photography company, and a crop decided by a layout is a crop nobody chose.
 * Each API photo carries its pixel size; the box is sized from that before the
 * image loads, so the page never jumps as pictures arrive.
 *
 * The fallback is the frame each gallery used before this change (the demo
 * data has no sizes), so nothing already on the site moves.
 */
export function photoAspect(
  photo: { width?: number | null; height?: number | null },
  fallback: string,
): string {
  const { width, height } = photo;
  return width && height && width > 0 && height > 0 ? `${width} / ${height}` : fallback;
}
