import { useState, type FormEvent, type ReactNode } from "react";
import { api } from "../api/client";
import type { TicketFieldView, TicketWithView } from "../api/types";
import { SHEKEL } from "../lib/format";
import { Amount } from "../ui/Amount";
import { Button } from "../ui/Button";
import { answerErrors, NO_ERRORS, type FormErrors } from "./answerErrors";

const CHOOSE_ONE = "צריך לבחור אחת מהאפשרויות.";

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

/** One ticket (brief §4.6): the question, then one section per blocking field (its tiles and
 * its input), and one answer for all of them. */
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

/** The employee's latest comparison: shown once, in the first section. */
function DiffTile({ ticket }: { ticket: TicketWithView }) {
  const comparison = ticket.view.comparison;
  return (
    <Tile
      label={
        comparison ? `ההפרש אצל העובד/ת · ${comparison.alternative_title}` : "ההפרש אצל העובד/ת"
      }
      note={comparison?.pending ? "זמני, לפי ברירת המחדל" : undefined}
    >
      {comparison ? <Amount value={comparison.display_diff} signed currency /> : "עדיין אין חישוב"}
    </Tile>
  );
}

/** What a field's answer depends on: the car and its catalog default, or (a choice such as a
 * group exception) the server's own text tiles. */
function FieldTiles({ field, diff }: { field: TicketFieldView; diff: ReactNode }) {
  if (field.options.length) {
    return (
      <div className="flex flex-wrap gap-3">
        {field.facts.map((fact) => (
          <Tile key={fact.label} label={fact.label}>
            <bdi>{fact.value}</bdi>
          </Tile>
        ))}
        {diff}
      </div>
    );
  }
  return (
    <div className="flex flex-wrap gap-3">
      <Tile label="רכב">
        <span className="inline-flex flex-wrap items-baseline gap-x-2">
          <span>{field.car_name ?? "—"}</span>
          {field.car_id ? (
            <code className="font-mono text-[13px] font-normal text-steel">{field.car_id}</code>
          ) : null}
        </span>
      </Tile>
      <Tile label="ברירת מחדל מהקטלוג">
        {field.catalog_default != null ? <Amount value={field.catalog_default} currency /> : "—"}
      </Tile>
      {diff}
    </div>
  );
}

/**
 * The answer: one section per blocking field, sent together. A typed value is sent as typed; a
 * choice (a group exception) as the chosen option's value. The server validates (the same rules
 * as the agent's tools) and the form shows its Hebrew messages next to the field.
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
  const [note, setNote] = useState("");
  const [errors, setErrors] = useState<FormErrors>(NO_ERRORS);
  const [sending, setSending] = useState(false);
  const several = fields.length > 1;

  async function submit(event: FormEvent) {
    event.preventDefault();
    const unchosen = fields.filter((f) => f.options.length && !values[f.field]);
    if (unchosen.length) {
      setErrors({
        ...NO_ERRORS,
        byField: Object.fromEntries(unchosen.map((f) => [f.field, [CHOOSE_ONE]])),
      });
      return;
    }
    setSending(true);
    setErrors(NO_ERRORS);
    try {
      const sent = Object.fromEntries(fields.map((f) => [f.field, values[f.field]?.trim() ?? ""]));
      await api.answerTicket(token, ticket.id, sent, note.trim() || undefined);
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
    <form onSubmit={submit} noValidate aria-label="תשובה לעובד/ת" className="flex flex-col gap-5">
      {fields.map((field, i) => {
        const id = `answer-${i}`;
        const messages = errors.byField[field.field] ?? [];
        const invalid = messages.length > 0;
        const set = (value: string) => setValues((v) => ({ ...v, [field.field]: value }));
        return (
          <section
            key={field.field}
            aria-labelledby={several ? `${id}-title` : undefined}
            className="flex flex-col gap-4"
          >
            {several ? (
              <h3 id={`${id}-title`} className="text-[17px] font-semibold text-navy">
                {field.car_name ? `${field.title} · ${field.car_name}` : field.title}
              </h3>
            ) : null}
            <FieldTiles field={field} diff={i === 0 ? <DiffTile ticket={ticket} /> : null} />
            <div className="flex flex-col gap-2 rounded-tile bg-ground p-5">
              {field.options.length ? (
                <fieldset
                  aria-invalid={invalid ? true : undefined}
                  aria-describedby={invalid ? `${id}-error` : undefined}
                  className="flex flex-col gap-2"
                >
                  <legend className="mb-1 font-medium text-ink">{fieldLabel(field)}</legend>
                  {field.options.map((option) => (
                    <label key={option.value} className="flex items-center gap-2 text-ink">
                      <input
                        type="radio"
                        name={id}
                        value={option.value}
                        checked={values[field.field] === option.value}
                        onChange={() => set(option.value)}
                        className="h-4 w-4 accent-royal"
                      />
                      {option.label}
                    </label>
                  ))}
                </fieldset>
              ) : (
                <>
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
                    onChange={(e) => set(e.target.value)}
                    aria-invalid={invalid ? true : undefined}
                    aria-describedby={invalid ? `${id}-error` : undefined}
                    className={`h-14 max-w-[280px] rounded-tile border-2 bg-surface px-4 text-end text-[22px] font-semibold text-ink ${
                      invalid ? "border-down" : "border-royal"
                    }`}
                  />
                </>
              )}
              {invalid ? (
                <p id={`${id}-error`} role="alert" className="text-[13px] font-medium text-down">
                  {messages.join(" ")}
                </p>
              ) : null}
            </div>
          </section>
        );
      })}
      <div className="flex flex-col gap-2">
        <label htmlFor="answer-note" className="font-medium text-ink">
          הערה לעובד/ת <span className="font-normal text-muted">(לא חובה)</span>
        </label>
        <textarea
          id="answer-note"
          rows={3}
          maxLength={4000}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          aria-describedby="answer-note-hint"
          className="max-w-[560px] rounded-tile border border-line bg-surface px-3 py-2 text-[15px] text-ink"
        />
        <p id="answer-note-hint" className="text-[13px] text-muted">
          מוצגת לעובד/ת כהערת הנציג. היא לא משנה אף ערך בחישוב.
        </p>
      </div>
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
