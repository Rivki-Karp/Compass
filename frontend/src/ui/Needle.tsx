import type { Direction } from "../api/types";

/**
 * The compass needle: a diamond outlined in mist; the half pointing in the direction of the
 * change is filled (up: green, top; down: orange, bottom). Flat: both halves mist. The filled
 * half rotates to its direction (300 ms, only without reduced motion).
 */
export function Needle({
  direction,
  width = 34,
  height = 56,
}: {
  direction: Direction | "empty";
  width?: number;
  height?: number;
}) {
  const fill =
    direction === "up"
      ? "var(--color-up)"
      : direction === "down"
        ? "var(--color-down)"
        : "var(--color-mist)";
  const rest = direction === "flat" ? "var(--color-mist)" : "transparent";
  return (
    <svg
      aria-hidden="true"
      focusable="false"
      data-direction={direction}
      width={width}
      height={height}
      viewBox="0 0 34 56"
    >
      <g
        className="motion-needle"
        style={{
          transformOrigin: "17px 28px",
          transform: direction === "down" ? "rotate(180deg)" : "rotate(0deg)",
        }}
      >
        <polygon points="17,2 32,28 2,28" fill={direction === "empty" ? "transparent" : fill} />
        <polygon points="2,28 32,28 17,54" fill={rest} />
      </g>
      <polygon
        points="17,2 32,28 17,54 2,28"
        fill="none"
        stroke="var(--color-mist)"
        strokeWidth={2}
        strokeLinejoin="round"
      />
    </svg>
  );
}
