import { useLayoutEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { api } from "../api/client";
import type { Ticket, TicketFieldView, TicketWithView } from "../api/types";
import { SHEKEL } from "../lib/format";
import { Amount } from "../ui/Amount";
import { Button } from "../ui/Button";
import { answerErrors, NO_ERRORS, type FormErrors } from "./answerErrors";

const FILL_ONE = "צריך למלא לפחות שדה אחד.";
// today's car outside the catalog: no default participation to fall back on
const NO_DEFAULT = "אין ברירת מחדל בקטלוג";

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

const isParticipation = (field: TicketFieldView) => field.field.includes("participation");
const isCar = (field: TicketFieldView) => field.field.startsWith("alternative_participation:");

/** The input's visible label, with the car's name: "סכום ההשתתפות החודשית ב-MG4 (₪)". */
function fieldLabel(field: TicketFieldView): string {
  if (isParticipation(field)) {
    return field.car_name
      ? `סכום ההשתתפות החודשית ב-${field.car_name} (${SHEKEL})`
      : `סכום ההשתתפות החודשית (${SHEKEL})`;
  }
  return field.unit === "ils" ? `${field.label} (${SHEKEL})` : field.label;
}

/** A section's heading: the car and its id for a car's participation, else the field. */
function FieldHeading({ field, id }: { field: TicketFieldView; id: string }) {
  const text = isCar(field)
    ? (field.car_name ?? field.title)
    : field.car_name
      ? `${field.title} · ${field.car_name}`
      : field.title;
  return (
    <h3
      id={id}
      className="flex flex-wrap items-baseline gap-x-2 text-[17px] font-semibold text-navy"
    >
      <span>{text}</span>
      {field.car_id ? (
        <code className="font-mono text-[13px] font-normal text-steel">{field.car_id}</code>
      ) : null}
    </h3>
  );
}

/** The model's question: secondary, three lines at most until "הצג עוד". */
function Question({ text }: { text: string }) {
  const ref = useRef<HTMLParagraphElement>(null);
  const [open, setOpen] = useState(false);
  const [overflows, setOverflows] = useState(false);
  useLayoutEffect(() => {
    const el = ref.current;
    if (el && !open) setOverflows(el.scrollHeight > el.clientHeight + 1);
  }, [text, open]);
  return (
    <div className="mt-2">
      <p
        ref={ref}
        id="ticket-question"
        className={`text-[15px] whitespace-pre-wrap text-ink ${open ? "" : "line-clamp-3"}`}
      >
        {text}
      </p>
      {overflows || open ? (
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          aria-controls="ticket-question"
          className="mt-1 min-h-6 text-[13px] font-medium text-royal underline"
        >
          {open ? "הצג פחות" : "הצג עוד"}
        </button>
      ) : null}
    </div>
  );
}

/** One ticket (brief §4.6): the title built from its fields, the question, then one section per
 * blocking field (its own facts and input). Fields can be answered one at a time. */
export function TicketDetail({
  ticket,
  token,
  onAnswered,
  onReauth,
}: {
  ticket: TicketWithView;
  token: string;
  onAnswered: (ticketId: string, stillOpen: boolean) => void;
  onReauth: () => void;
}) {
  const context = contextLine(ticket.context);
  return (
    <article
      aria-labelledby="ticket-title"
      className="flex min-w-0 flex-[999_1_560px] flex-col gap-5 rounded-card border border-line bg-surface p-6"
    >
      <div>
        <h2 id="ticket-title" className="text-[22px] font-bold text-navy">
          {ticket.view.title}
        </h2>
        {context ? <p className="mt-1 text-muted">{context}</p> : null}
        <Question text={ticket.question} />
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

/** The employee's comparison this field affects: that car's own for a car's participation. */
function DiffTile({ field }: { field: TicketFieldView }) {
  const comparison = field.comparison;
  return (
    <Tile
      label={
        comparison && !isCar(field)
          ? `ההפרש אצל העובד/ת · ${comparison.alternative_title}`
          : "ההפרש אצל העובד/ת"
      }
      note={comparison?.pending ? "זמני, לפי ברירת המחדל" : undefined}
    >
      {comparison ? <Amount value={comparison.display_diff} signed currency /> : "עדיין אין חישוב"}
    </Tile>
  );
}

/** What a field's answer depends on, for this field only (never another car's numbers). */
function FieldTiles({ field }: { field: TicketFieldView }) {
  return (
    <div className="flex flex-wrap gap-3">
      {field.options.length ? (
        field.facts.map((fact) => (
          <Tile key={fact.label} label={fact.label}>
            <bdi>{fact.value}</bdi>
          </Tile>
        ))
      ) : (
        <>
          {!isCar(field) ? (
            <Tile label="רכב">
              <span>{field.car_name ?? "—"}</span>
            </Tile>
          ) : null}
          <Tile label="ברירת מחדל מהקטלוג">
            {field.catalog_default != null ? (
              <Amount value={field.catalog_default} currency />
            ) : field.unit === "ils" ? (
              NO_DEFAULT
            ) : (
              "—"
            )}
          </Tile>
        </>
      )}
      <DiffTile field={field} />
    </div>
  );
}

/** An answered field (an earlier part of a partial answer): what the rep answered. */
function Answered({ field }: { field: TicketFieldView }) {
  return (
    <p className="flex items-center gap-2 text-ink">
      <span className="font-medium text-up">נענה:</span>
      {typeof field.answer === "number" ? (
        <Amount value={field.answer} currency />
      ) : (
        <span>{field.answer}</span>
      )}
    </p>
  );
}

/**
 * The answer: one section per blocking field. Only the fields with a value are sent, as a partial
 * answer: the others stay pending and the ticket stays open for them. The server validates (the
 * same rules as the agent's tools) and the form shows its Hebrew messages next to the field.
 */
function AnswerForm({
  ticket,
  token,
  onAnswered,
  onReauth,
}: {
  ticket: TicketWithView;
  token: string;
  onAnswered: (ticketId: string, stillOpen: boolean) => void;
  onReauth: () => void;
}) {
  const fields = ticket.view.fields;
  const [values, setValues] = useState<Record<string, string>>({});
  const [note, setNote] = useState("");
  const [errors, setErrors] = useState<FormErrors>(NO_ERRORS);
  const [sending, setSending] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const sent = Object.fromEntries(
      fields
        .filter((f) => !f.answered)
        .map((f) => [f.field, values[f.field]?.trim() ?? ""] as const)
        .filter(([, value]) => value !== ""),
    );
    if (!Object.keys(sent).length) {
      setErrors({ ...NO_ERRORS, form: [FILL_ONE] });
      return;
    }
    setSending(true);
    setErrors(NO_ERRORS);
    try {
      const answered = (await api.answerTicket(
        token,
        ticket.id,
        sent,
        note.trim() || undefined,
        true,
      )) as Ticket | null;
      setValues({});
      setNote("");
      setSending(false);
      onAnswered(ticket.id, answered?.status === "open");
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
            aria-labelledby={`${id}-title`}
            className="flex flex-col gap-3 border-t border-line-soft pt-4 first:border-t-0 first:pt-0"
          >
            <FieldHeading field={field} id={`${id}-title`} />
            <FieldTiles field={field} />
            <div className="flex flex-col gap-2 rounded-tile bg-ground p-5">
              {field.answered ? (
                <Answered field={field} />
              ) : field.options.length ? (
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
                  <div className="flex flex-wrap items-center gap-3">
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
                    {field.catalog_default != null ? (
                      <Button
                        type="button"
                        variant="secondary"
                        onClick={() => set(String(field.catalog_default))}
                        aria-label={
                          field.car_name
                            ? `השתמש בברירת המחדל ל-${field.car_name}`
                            : "השתמש בברירת המחדל"
                        }
                      >
                        השתמש בברירת המחדל
                      </Button>
                    ) : null}
                  </div>
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
          נשלחים רק השדות שמולאו; השאר ממתינים. ברגע האישור השרת מחשב מחדש, והכרטיס אצל העובד/ת
          מתעדכן
        </p>
      </div>
    </form>
  );
}
