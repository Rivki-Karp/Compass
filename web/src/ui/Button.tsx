import type { ComponentProps } from "react";

type Variant = "primary" | "secondary" | "suggestion";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-royal text-white border-royal hover:bg-navy rounded-control px-4",
  secondary: "bg-surface text-ink border-line hover:border-steel rounded-control px-4",
  suggestion: "bg-surface text-royal border-royal hover:bg-ground rounded-chip px-3.5 text-[13px]",
};

/** A real <button>, at least 44px tall (brief §3.5). */
export function Button({
  variant = "primary",
  className = "",
  type = "button",
  ...props
}: ComponentProps<"button"> & { variant?: Variant }) {
  return (
    <button
      type={type}
      className={`inline-flex min-h-11 items-center justify-center gap-2 border font-medium disabled:cursor-not-allowed disabled:opacity-50 ${VARIANTS[variant]} ${className}`}
      {...props}
    />
  );
}
