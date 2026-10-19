import type { MouseEvent } from "react";
import type { TicketWithView } from "../api/types";
import { ticketAge } from "./inbox";
import { BidiText } from "../ui/BidiText";

/** "טיקטים פתוחים" (brief §4.6): one link row per open ticket, updated live. */
export function TicketList({
  tickets,
  loaded,
  selectedId,
  now,
  onSelect,
}: {
  tickets: TicketWithView[];
  loaded: boolean;
  selectedId: string | null;
  now: number;
  onSelect: (ticketId: string) => void;
}) {
  return (
    <section
      aria-labelledby="tickets-title"
      className="flex min-w-0 flex-[1_1_340px] flex-col rounded-card border border-line bg-surface"
    >
      <div className="flex items-center gap-2 border-b border-line-soft px-5 py-4">
        <h2 id="tickets-title" className="text-[15px] font-semibold text-navy">
          טיקטים פתוחים
        </h2>
        <span
          aria-label={`${tickets.length} טיקטים פתוחים`}
          className="rounded-chip border border-chip-pending-border bg-chip-pending-bg px-2 text-[13px] font-semibold text-chip-pending"
        >
          <bdi>{tickets.length}</bdi>
        </span>
      </div>
      {tickets.length ? (
        <ul className="flex flex-col py-1">
          {tickets.map((ticket) => {
            const selected = ticket.id === selectedId;
            return (
              <li key={ticket.id}>
                <a
                  href={`?ticket=${encodeURIComponent(ticket.id)}`}
                  aria-current={selected ? "true" : undefined}
                  onClick={(event: MouseEvent) => {
                    if (event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0)
                      return; // let the browser open it elsewhere
                    event.preventDefault();
                    onSelect(ticket.id);
                  }}
                  className={`flex min-h-11 flex-col gap-0.5 border-s-[3px] px-5 py-3 hover:bg-ground ${
                    selected ? "border-royal bg-provenance-bg" : "border-transparent"
                  }`}
                >
                  <span className="flex items-baseline gap-3">
                    <span className="font-medium text-ink">
                      <BidiText text={ticket.view.title} />
                    </span>
                    <span className="ms-auto shrink-0 text-[12px] text-muted">
                      {ticketAge(ticket.created_at, now)}
                    </span>
                  </span>
                  <code className="self-end font-mono text-[12px] text-steel">
                    {ticket.blocking_fields.join(", ")}
                  </code>
                </a>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="px-5 py-8 text-center text-[13px] text-muted">
          {loaded ? "טיקטים חדשים יופיעו כאן אוטומטית" : "טוען טיקטים…"}
        </p>
      )}
    </section>
  );
}
