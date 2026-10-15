import { SHEKEL, formatAmount, formatSigned } from "../lib/format";

/**
 * An amount from the API. Only the number (with its sign) is isolated in <bdi>; the shekel
 * sign stays outside, in the paragraph's right-to-left flow, so "11,000 ₪" reads correctly
 * inside Hebrew text (inside the <bdi> it would be laid out left to right: "₪ 11,000").
 */
export function Amount({
  value,
  signed = false,
  currency = false,
  className,
}: {
  value: number;
  signed?: boolean;
  currency?: boolean;
  className?: string;
}) {
  const number = <bdi>{signed ? formatSigned(value) : formatAmount(value)}</bdi>;
  if (!currency) return <span className={className}>{number}</span>;
  return (
    <span className={className}>
      {number} {SHEKEL}
    </span>
  );
}
