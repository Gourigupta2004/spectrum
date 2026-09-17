export function Orb({
  className,
  colors = ["#f7c21f", "#b94c9e"],
  size = 520,
  opacity = 0.1,
  delay = 0,
}: {
  className?: string;
  colors?: [string, string] | string[];
  size?: number;
  opacity?: number;
  delay?: number;
}) {
  return (
    <div
      aria-hidden
      className={`orb ${className ?? ""}`}
      style={{
        width: size,
        height: size,
        opacity,
        animationDelay: `${delay}s`,
        background: `radial-gradient(circle at 35% 35%, ${colors[0]}, ${colors[1]} 60%, transparent 72%)`,
      }}
    />
  );
}
