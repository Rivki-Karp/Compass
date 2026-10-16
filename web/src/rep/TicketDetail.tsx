import { useState, type FormEvent, type ReactNode } from "react";
import { api } from "../api/client";
import type { TicketFieldView, TicketWithView } from "../api/types";
import { SHEKEL } from "../lib/format";
import { Amount } from "../ui/Amount";
import { Button } from "../ui/Button";
import { answerErrors, NO_ERRORS, type FormErrors } from "./answerErrors";

/** The context line: "מנהל/ת מוצר · קבוצה ג׳ · היום: COROLLA CROSS". */
function contextLine(context: Record<string, unknown>): string {
  const text = (key: string) => {
    const value = context[key];
    return typeof value === "string" && value ? value : null;
  };
  const group = text("group");
  return [
    text("display_name"),
    text("occupation"),
    group ? `קבוצה ${group}׳` : null, // the geresh, as labels.group_letter writes it
    text("current_situation") ? `היום: ${text("current_situation")}` : null,
    text("requested_alternative") ? `מבקש/ת: ${text("requested_alternative")}` : null,
  ]
    .filter(Boolean)
    .join(" · ");
}

function fieldLabel(field: TicketFieldView): string {
  if (field.field.includes("participation")) return `סכום ההשתתפות החודשית (${SHEKEL})`;
  return field.unit === "ils" ? `${field.label} (${SHEKEL})` : field.label;
}

/** One ticket (brief §4.6): the question, three info tiles, and the answer form. */
export function TicketDetail({
  ticket,
  token,
  onAnswered,
  onReauth,
}: {
  ticket: TicketWithView;
  token: string;
  onAnswered: (ticketId: string) => void;
  onReauth: () => void;
}) {
  const { view } = ticket;
  const first = view.fields[0];
  const context = contextLine(ticket.context);
  return (
    <article
      aria-labelledby="ticket-question"
      className="flex min-w-0 flex-[999_1_560px] flex-col gap-5 rounded-card border border-line bg-surface p-6"
    >
      <div>
        <h2 id="ticket-question" className="text-[22px] font-bold text-navy">
          {ticket.question}
        </h2>
        {context ? <p className="mt-1 text-muted">{context}</p> : null}
      </div>

      <div className="flex flex-wrap gap-3">
        <Tile label="רכב">
          <span className="inline-flex flex-wrap items-baseline gap-x-2">
            <span>{first?.car_name ?? "—"}</span>
            {first?.car_id ? (
              <code className="font-mono text-[13px] font-normal text-steel">{first.car_id}</code>
            ) : null}
          </span>
        </Tile>
        <Tile label="ברירת מחדל מהקטלוג">
          {first?.catalog_default != null ? <Amount value={first.catalog_default} currency /> : "—"}
        </Tile>
        <Tile
          label={
            view.comparison
              ? `ההפרש אצל העובד/ת · ${view.comparison.alternative_title}`
              : "ההפרש אצל העובד/ת"
          }
          note={view.comparison?.pending ? "זמני, לפי ברירת המחדל" : undefined}
        >
          {view.comparison ? (
            <Amount value={view.comparison.display_diff} signed currency />
          ) : (
            "עדיין אין חישוב"
          )}
        </Tile>
      </div>

      <AnswerForm
        key={ticket.id}
        ticket={ticket}
        token={token}
        onAnswered={onAnswered}
        onReauth={onReauth}
      />
    </article>
  );
}

function Tile({ label, note, children }: { label: string; note?: string; children: ReactNode }) {
  return (
    <div className="min-w-[160px] flex-1 rounded-tile border border-line px-4 py-3">
      <div className="text-[13px] text-muted">{label}</div>
      <div className="mt-1 text-[20px] font-semibold text-ink">{children}</div>
      {note ? <div className="text-[12px] text-chip-pending">{note}</div> : null}
    </div>
  );
}

/**
 * The answer: one input per blocking field, sent as typed. The server validates (the same
 * rules as the agent's tools) and the form shows its Hebrew messages next to the field.
 */
function AnswerForm({
  ticket,
  token,
  onAnswered,
  onReauth,
}: {
  ticket: TicketWithView;
  token: string;
  onAnswered: (ticketId: string) => void;
  onReauth: () => void;
}) {
  const fields = ticket.view.fields;
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(fields.map((f) => [f.field, ""])),
  );
  const [errors, setErrors] = useState<FormErrors>(NO_ERRORS);
  const [sending, setSending] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSending(true);
    setErrors(NO_ERRORS);
    try {
      const sent = Object.fromEntries(fields.map((f) => [f.field, values[f.field]?.trim() ?? ""]));
      await api.answerTicket(token, ticket.id, sent);
      onAnswered(ticket.id);
    } catch (error) {
      const mapped = answerErrors(
        error,
        fields.map((f) => f.field),
      );
      setErrors(mapped);
      setSending(false);
      if (mapped.reauth) onReauth();
    }
  }

  return (
    <form
      onSubmit={submit}
      noValidate
      aria-label="תשובה לעובד/ת"
      className="flex flex-col gap-4 rounded-tile bg-ground p-5"
    >
      {fields.map((field, i) => {
        const id = `answer-${i}`;
        const messages = errors.byField[field.field] ?? [];
        return (
          <div key={field.field} className="flex flex-col gap-2">
            <label htmlFor={id} className="font-medium text-ink">
              {fieldLabel(field)}
            </label>
            <input
              id={id}
              type="text"
              inputMode="decimal"
              autoComplete="off"
              dir="ltr"
              value={values[field.field] ?? ""}
              onChange={(e) => setValues((v) => ({ ...v, [field.field]: e.target.value }))}
              aria-invalid={messages.length ? true : undefined}
              aria-describedby={messages.length ? `${id}-error` : undefined}
              className={`h-14 max-w-[280px] rounded-tile border-2 bg-surface px-4 text-end text-[22px] font-semibold text-ink ${
                messages.length ? "border-down" : "border-royal"
              }`}
            />
            {messages.length ? (
              <p id={`${id}-error`} role="alert" className="text-[13px] font-medium text-down">
                {messages.join(" ")}
              </p>
            ) : null}
          </div>
        );
      })}
      {errors.form.length ? (
        <div role="alert" className="text-[13px] font-medium text-down">
          {errors.form.map((m) => (
            <p key={m}>{m}</p>
          ))}
        </div>
      ) : null}
      <div className="flex flex-wrap items-center gap-4">
        <Button type="submit" disabled={sending}>
          {sending ? "שולח…" : "אישור ושליחה לעובד/ת"}
        </Button>
        <p className="text-[13px] text-muted">
          ברגע האישור השרת מחשב מחדש, והכרטיס אצל העובד/ת מתעדכן
        </p>
      </div>
    </form>
  );
}
