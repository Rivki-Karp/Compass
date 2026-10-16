import type { ReactNode } from "react";
import mark from "../assets/compass-mark.png";
import type { StreamStatus } from "../api/sse";

/** The app header (brief §4.1): the mark, the wordmark, and the status controls. */
export function Header({ children }: { children?: ReactNode }) {
  return (
    <header className="flex flex-wrap items-center gap-x-6 gap-y-3 border-b border-line bg-surface px-8 py-3">
      <div className="flex items-center gap-3">
        <img src={mark} alt="" className="h-12 w-12" />
        <div>
          <div className="ltr text-[20px] leading-tight font-bold tracking-[0.04em] text-navy">
            COMPASS
          </div>
          <div className="text-[13px] text-muted">יועץ הרכב של Strauss</div>
        </div>
      </div>
      <div className="ms-auto flex flex-wrap items-center gap-3">{children}</div>
    </header>
  );
}

export function ConnectionPill({ status }: { status: StreamStatus }) {
  const connected = status === "open";
  return (
    <span
      role="status"
      className={`inline-flex items-center gap-2 rounded-chip px-3 py-1 text-[13px] ${
        connected ? "bg-up-bg text-up" : "bg-chip-pending-bg text-chip-pending"
      }`}
    >
      <span
        aria-hidden="true"
        className={`h-2 w-2 rounded-full ${connected ? "bg-up" : "bg-chip-pending-border"}`}
      />
      {connected ? "מחובר" : "מתחבר מחדש…"}
    </span>
  );
}

export function DemoBadge() {
  return (
    <span className="rounded-chip border border-line bg-ground px-3 py-1 text-[13px] font-medium text-steel">
      מצב דמו
    </span>
  );
}

/** The judges-mode switch: a real button with aria-pressed. */
export function JudgesToggle({ on, onToggle }: { on: boolean; onToggle: () => void }) {
  return (
    <button
      type="button"
      aria-pressed={on}
      onClick={onToggle}
      className={`inline-flex min-h-11 items-center gap-3 rounded-chip border px-4 text-[14px] font-medium ${
        on ? "border-navy bg-navy text-white" : "border-line bg-surface text-ink"
      }`}
    >
      <span
        aria-hidden="true"
        className={`relative inline-block h-5 w-9 rounded-chip ${on ? "bg-steel" : "bg-line"}`}
      >
        <span
          className={`absolute top-0.5 h-4 w-4 rounded-full ${
            on ? "start-[18px] bg-knob-on" : "start-0.5 bg-surface"
          }`}
        />
      </span>
      מצב שופטים
    </button>
  );
}
