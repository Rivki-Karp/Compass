import { useLayoutEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { api, type QuestionAnswer } from "../api/client";
import type { Ticket, TicketOptionView, TicketQuestionView, TicketWithView } from "../api/types";
import { Amount } from "../ui/Amount";
import { Diff } from "../ui/Diff";
import { Button } from "../ui/Button";
import { answerErrors, NO_ERRORS, type FormErrors } from "./answerErrors";
import { BidiText } from "../ui/BidiText";

const FILL_ONE = "צריך לענות על שאלה אחת לפחות, או לסמן ״צריך לבדוק״.";
// today's car outside the catalog: no default participation to fall back on
const NO_DEFAULT = "אין ברירת מחדל בקטלוג";
const NEEDS_CHECKING = "לא ידוע לי / צריך לבדוק";
const MAX_SEARCH_RESULTS = 8;

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

const isParticipation = (q: TicketQuestionView) => q.bound_field?.includes("participation") ?? false;
const isCar = (q: TicketQuestionView) =>
  q.bound_field?.startsWith("alternative_participation:") ?? false;

/** A section's heading: the car and its id for a car's participation, else the server's title. */
function QuestionHeading({ question, id }: { question: TicketQuestionView; id: string }) {
  const text = isCar(question) ? (question.car_name ?? question.title) : question.title;
  return (
    <h3
      id={id}
      className="flex flex-wrap items-baseline gap-x-2 text-[17px] font-semibold text-navy"
    >
      <span>
        <BidiText text={text} />
      </span>
      {question.car_id && isCar(question) ? (
        <code className="font-mono text-[13px] font-normal text-steel">{question.car_id}</code>
      ) : null}
    </h3>
  );
}

/** The agent's context paragraph: secondary, three lines at most until "הצג עוד". */
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
        <BidiText text={text} />
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

/** One ticket: the title built by the server, the agent's context, then one section per
 * question. Questions can be answered one at a time. */
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
          <BidiText text={ticket.view.title} />
        </h2>
        {context ? (
          <p className="mt-1 text-muted">
            <BidiText text={context} />
          </p>
        ) : null}
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
      <div className="text-[13px] text-muted">
        <BidiText text={label} />
      </div>
      <div className="mt-1 text-[20px] font-semibold text-ink">{children}</div>
      {note ? <div className="text-[12px] text-chip-pending">{note}</div> : null}
    </div>
  );
}

/** The employee's comparison this participation affects: that car's own for a car. */
function DiffTile({ question }: { question: TicketQuestionView }) {
  const comparison = question.comparison;
  return (
    <Tile
      label={
        comparison && !isCar(question)
          ? `ההפרש אצל העובד/ת · ${comparison.alternative_title}`
          : "ההפרש אצל העובד/ת"
      }
      note={comparison?.pending ? "זמני, לפי ברירת המחדל" : undefined}
    >
      {comparison ? <Diff view={comparison} currency /> : "עדיין אין חישוב"}
    </Tile>
  );
}

function FactTiles({ question }: { question: TicketQuestionView }) {
  return (
    <>
      {question.facts.map((fact) => (
        <Tile key={fact.label} label={fact.label}>
          <BidiText text={fact.value} />
        </Tile>
      ))}
    </>
  );
}

/**
 * What the question's answer depends on, and nothing else:
 * - a participation: the car, the catalog default, the employee's (provisional) difference;
 * - an occupation or today's car: what the employee wrote, and what the choice would give (the
 *   group; the car's drive and group), under the server's `detail_label`;
 * - a group: today's car and its group (with the occupation's group);
 * - a free question: no tiles (the agent's context paragraph is above).
 */
function QuestionTiles({
  question,
  chosen,
}: {
  question: TicketQuestionView;
  chosen: TicketOptionView | undefined;
}) {
  if (isParticipation(question)) {
    return (
      <div className="flex flex-wrap gap-3">
        {!isCar(question) ? (
          <Tile label="רכב">
            <span>{question.car_name ? <BidiText text={question.car_name} /> : "—"}</span>
          </Tile>
        ) : null}
        <Tile label="ברירת מחדל מהקטלוג">
          {question.catalog_default != null ? (
            <Amount value={question.catalog_default} currency />
          ) : (
            NO_DEFAULT
          )}
        </Tile>
        <DiffTile question={question} />
      </div>
    );
  }
  if (question.detail_label) {
    return (
      <div className="flex flex-wrap gap-3">
        <FactTiles question={question} />
        <Tile label={question.detail_label}>
          {chosen?.detail ? <BidiText text={chosen.detail} /> : "—"}
        </Tile>
      </div>
    );
  }
  if (question.facts.length) {
    return (
      <div className="flex flex-wrap gap-3">
        <FactTiles question={question} />
      </div>
    );
  }
  return null;
}

/** An answered question (an earlier part of a partial answer): what the rep answered. */
function Answered({ question }: { question: TicketQuestionView }) {
  return (
    <div className="flex flex-col gap-1 text-ink">
      <p className="flex items-center gap-2">
        <span className="font-medium text-up">נענה:</span>
        {typeof question.answer === "number" ? (
          <Amount value={question.answer} currency />
        ) : (
          <span>
            <BidiText text={question.answer ?? ""} />
          </span>
        )}
      </p>
      {question.note ? (
        <p className="text-[13px] text-muted">
          הערה: <BidiText text={question.note} />
        </p>
      ) : null}
    </div>
  );
}

interface Draft {
  value: string;
  checking: boolean;
  note: string;
}

const EMPTY: Draft = { value: "", checking: false, note: "" };

type InputProps = {
  question: TicketQuestionView;
  id: string;
  value: string;
  set: (value: string) => void;
  disabled: boolean;
  invalid: boolean;
};

/** amount: whole ILS, with the catalog default one click away. */
function AmountInput({ question, id, value, set, disabled, invalid }: InputProps) {
  return (
    <>
      <label htmlFor={id} className="font-medium text-ink">
        <BidiText text={question.label} />
      </label>
      <div className="flex flex-wrap items-center gap-3">
        <input
          id={id}
          type="text"
          inputMode="numeric"
          autoComplete="off"
          dir="ltr"
          value={value}
          disabled={disabled}
          onChange={(e) => set(e.target.value)}
          aria-invalid={invalid ? true : undefined}
          aria-describedby={invalid ? `${id}-error` : undefined}
          className={`h-14 max-w-[280px] rounded-tile border-2 bg-surface px-4 text-end text-[22px] font-semibold text-ink disabled:opacity-50 ${
            invalid ? "border-down" : "border-royal"
          }`}
        />
        {question.catalog_default != null ? (
          <Button
            type="button"
            variant="secondary"
            disabled={disabled}
            onClick={() => set(String(question.catalog_default))}
            aria-label={
              question.car_name
                ? `השתמש בברירת המחדל ל-${question.car_name}`
                : "השתמש בברירת המחדל"
            }
          >
            השתמש בברירת המחדל
          </Button>
        ) : null}
      </div>
    </>
  );
}

/** Whether a search box entry matches: its label or its detail, ignoring case. */
const matches = (option: TicketOptionView, query: string) =>
  [option.label, option.detail ?? ""].some((t) => t.toLowerCase().includes(query.toLowerCase()));

/** choice and yes_no: one radio per option (the server's options, never the model's for a
 * bound question). An occupation or today's car adds a search over the whole table (the
 * occupations, the catalog), labelled by the server; the option that needs a note comes last. */
function ChoiceInput({ question, id, value, set, disabled, invalid }: InputProps) {
  const [search, setSearch] = useState("");
  const query = search.trim();
  const listed = new Set(question.options.map((o) => o.value));
  const found = query
    ? question.search_options
        .filter((o) => !listed.has(o.value) && matches(o, query))
        .slice(0, MAX_SEARCH_RESULTS)
    : [];
  // the choice stays on screen when the search changes
  const kept = question.search_options.find(
    (o) => o.value === value && !listed.has(o.value) && !found.includes(o),
  );
  const shown = [...(kept ? [kept] : []), ...found];
  const noted = question.note_required_for;
  const other = question.options.filter((o) => o.value === noted);
  const options = question.options.filter((o) => o.value !== noted);
  const label = (o: TicketOptionView) => (o.detail ? `${o.label} · ${o.detail}` : o.label);
  const radio = (option: TicketOptionView) => (
    <label key={option.value} className="flex items-center gap-2 text-ink">
      <input
        type="radio"
        name={id}
        value={option.value}
        checked={value === option.value}
        disabled={disabled}
        onChange={() => set(option.value)}
        className="h-4 w-4 accent-royal"
      />
      <BidiText text={option.label} />
    </label>
  );
  return (
    <fieldset
      aria-invalid={invalid ? true : undefined}
      aria-describedby={invalid ? `${id}-error` : undefined}
      className="flex flex-col gap-2"
    >
      <legend className="mb-1 font-medium text-ink">
        <BidiText text={question.label} />
      </legend>
      {options.map(radio)}
      {question.search_options.length ? (
        <div className="mt-1 flex flex-col gap-2">
          <label htmlFor={`${id}-search`} className="text-[13px] text-muted">
            {question.search_label}
          </label>
          <input
            id={`${id}-search`}
            type="search"
            autoComplete="off"
            value={search}
            disabled={disabled}
            onChange={(e) => setSearch(e.target.value)}
            className="h-11 max-w-[360px] rounded-tile border border-line bg-surface px-3 text-[15px] text-ink"
          />
          {query && !found.length ? (
            <p className="text-[13px] text-muted">{question.search_empty}</p>
          ) : null}
          {shown.map((o) => radio({ ...o, label: label(o) }))}
        </div>
      ) : null}
      {other.map(radio)}
    </fieldset>
  );
}

function TextInput({ question, id, value, set, disabled, invalid }: InputProps) {
  return (
    <>
      <label htmlFor={id} className="font-medium text-ink">
        <BidiText text={question.label} />
      </label>
      <textarea
        id={id}
        rows={3}
        maxLength={2000}
        value={value}
        disabled={disabled}
        onChange={(e) => set(e.target.value)}
        aria-invalid={invalid ? true : undefined}
        aria-describedby={invalid ? `${id}-error` : undefined}
        className="max-w-[560px] rounded-tile border-2 border-royal bg-surface px-3 py-2 text-[15px] text-ink disabled:opacity-50"
      />
    </>
  );
}

const INPUTS: Record<TicketQuestionView["type"], (props: InputProps) => ReactNode> = {
  amount: AmountInput,
  choice: ChoiceInput,
  yes_no: ChoiceInput,
  text: TextInput,
};

/**
 * The answer: one section per question, each rendered by its answer type. Only the questions
 * answered (or marked "needs checking") are sent, as a partial answer: the others stay pending
 * and the ticket stays open for them. The server validates; the form shows its Hebrew messages
 * next to the question.
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
  const questions = ticket.view.questions;
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [errors, setErrors] = useState<FormErrors>(NO_ERRORS);
  const [sending, setSending] = useState(false);
  const draft = (q: TicketQuestionView) => drafts[q.id] ?? EMPTY;
  const update = (q: TicketQuestionView, change: Partial<Draft>) =>
    setDrafts((d) => ({ ...d, [q.id]: { ...(d[q.id] ?? EMPTY), ...change } }));

  async function submit(event: FormEvent) {
    event.preventDefault();
    const answers: Record<string, QuestionAnswer> = {};
    for (const q of questions) {
      if (q.status === "answered" || q.status === "unknown") continue;
      const { value, checking, note } = draft(q);
      const withNote = note.trim() ? { note: note.trim() } : {};
      if (checking) answers[q.id] = { status: "needs_checking", ...withNote };
      else if (value.trim()) answers[q.id] = { value: value.trim(), ...withNote };
    }
    if (!Object.keys(answers).length) {
      setErrors({ ...NO_ERRORS, form: [FILL_ONE] });
      return;
    }
    setSending(true);
    setErrors(NO_ERRORS);
    try {
      const answered = (await api.answerQuestions(token, ticket.id, answers)) as Ticket | null;
      setDrafts({});
      setSending(false);
      onAnswered(ticket.id, answered?.status === "open");
    } catch (error) {
      const names = questions.flatMap((q) => (q.bound_field ? [q.id, q.bound_field] : [q.id]));
      const mapped = answerErrors(error, names);
      setErrors(mapped);
      setSending(false);
      if (mapped.reauth) onReauth();
    }
  }

  return (
    <form onSubmit={submit} noValidate aria-label="תשובה לעובד/ת" className="flex flex-col gap-5">
      {questions.map((question, i) => {
        const id = `answer-${i}`;
        const messages = [
          ...(errors.byField[question.id] ?? []),
          ...(question.bound_field ? (errors.byField[question.bound_field] ?? []) : []),
        ];
        const invalid = messages.length > 0;
        const { value, checking, note } = draft(question);
        const chosen = [...question.options, ...question.search_options].find(
          (o) => o.value === value,
        );
        const done = question.status === "answered" || question.status === "unknown";
        const Input = INPUTS[question.type];
        const noteRequired =
          question.note_required_for !== null && value === question.note_required_for && !checking;
        return (
          <section
            key={question.id}
            aria-labelledby={`${id}-title`}
            className="flex flex-col gap-3 border-t border-line-soft pt-4 first:border-t-0 first:pt-0"
          >
            <QuestionHeading question={question} id={`${id}-title`} />
            {question.prompt_he && question.prompt_he !== question.title ? (
              <p className="text-[15px] text-ink">
                <BidiText text={question.prompt_he} />
              </p>
            ) : null}
            <QuestionTiles question={question} chosen={chosen} />
            <div className="flex flex-col gap-2 rounded-tile bg-ground p-5">
              {done ? (
                <Answered question={question} />
              ) : (
                <>
                  {question.status === "needs_checking" ? (
                    <p className="text-[13px] font-medium text-chip-pending">
                      סומן ״צריך לבדוק״{question.note ? `: ${question.note}` : ""}
                    </p>
                  ) : null}
                  <Input
                    question={question}
                    id={id}
                    value={checking ? "" : value}
                    set={(v) => update(question, { value: v })}
                    disabled={checking}
                    invalid={invalid}
                  />
                  <label className="flex items-center gap-2 text-ink">
                    <input
                      type="checkbox"
                      checked={checking}
                      onChange={(e) => update(question, { checking: e.target.checked })}
                      className="h-4 w-4 accent-royal"
                    />
                    {NEEDS_CHECKING}
                  </label>
                  <label htmlFor={`${id}-note`} className="text-[13px] font-medium text-ink">
                    {noteRequired ? (
                      question.note_required_label
                    ) : (
                      <>
                        הערה <span className="font-normal text-muted">(לא חובה)</span>
                      </>
                    )}
                  </label>
                  <textarea
                    id={`${id}-note`}
                    rows={2}
                    maxLength={1000}
                    value={note}
                    required={noteRequired}
                    onChange={(e) => update(question, { note: e.target.value })}
                    className="max-w-[560px] rounded-tile border border-line bg-surface px-3 py-2 text-[15px] text-ink"
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
          נשלחות רק השאלות שנענו; השאר ממתינות. ההערות מוצגות לעובד/ת ולא משנות אף ערך בחישוב
        </p>
      </div>
    </form>
  );
}
