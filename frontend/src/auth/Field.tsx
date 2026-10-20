import type { ComponentProps } from "react";

/** A labelled input for the dark account screens (login, register): a real <label>, a visible
 * focus ring (landing.css .lp-field) and a 52px control. `ltr`: an email, a code. */
export function Field({
  label,
  id,
  ltr = false,
  describedBy,
  ...props
}: Omit<ComponentProps<"input">, "id"> & {
  label: string;
  id: string;
  ltr?: boolean;
  describedBy?: string;
}) {
  return (
    <label htmlFor={id} className="flex flex-col gap-2 text-[14px] font-semibold text-engine-text">
      {label}
      <input
        id={id}
        dir={ltr ? "ltr" : undefined}
        aria-describedby={describedBy}
        className="lp-field min-h-[52px] rounded-[12px] border border-white/30 bg-engine-code/60 px-4 text-[16px] font-normal text-white placeholder:text-faint"
        {...props}
      />
    </label>
  );
}
