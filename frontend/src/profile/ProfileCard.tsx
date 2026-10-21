import { useState } from "react";
import type { ProfileOffer, ProfileOfferField } from "../api/types";
import { formatDayMonth, formatInput } from "../lib/format";
import { Amount } from "../ui/Amount";
import { Button } from "../ui/Button";
import { Icon } from "../ui/icons";
import { SourceChip } from "../ui/SourceChip";

export interface ProfileChoice {
  name: string;
  action: "keep" | "edit" | "drop";
  value?: string;
}

const SUFFIX: Record<ProfileOfferField["unit"], string> = {
  ils: "₪",
  percent: "%",
  points: "",
  text: "",
};

/** Whether a field can be typed over: the numbers; the occupation and the car are kept or removed. */
const editable = (f: ProfileOfferField) => f.unit !== "text";

/**
 * "יש לי פרטים מהשיחה מ־{date}": the saved details of this account at the top of a new
 * conversation, a pending candidate like the payslip's. Nothing is used until a button is
 * pressed: "להשתמש בהם" keeps what is shown, "לעדכן" lets numbers be corrected first,
 * "להתחיל מחדש" ignores them for this conversation. Each row can be removed. RTL, numbers in <bdi>.
 */
export function ProfileCard({
  offer,
  busy,
  error,
  onApply,
  onDismiss,
  onDelete,
}: {
  offer: ProfileOffer;
  busy: boolean;
  error: string | null;
  onApply: (choices: ProfileChoice[]) => void;
  onDismiss: () => void;
  onDelete: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [removed, setRemoved] = useState<Set<string>>(new Set());
  const [typed, setTyped] = useState<Record<string, string>>({});
  const [asking, setAsking] = useState(false);

  const toggle = (name: string) =>
    setRemoved((all) => {
      const next = new Set(all);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  const used = offer.fields.filter((f) => !removed.has(f.name));
  const choices = (): ProfileChoice[] =>
    offer.fields.map((f): ProfileChoice => {
      if (removed.has(f.name)) return { name: f.name, action: "drop" };
      const value = typed[f.name]?.trim();
      return value !== undefined && value !== "" && value !== f.value
        ? { name: f.name, action: "edit", value }
        : { name: f.name, action: "keep" };
    });

  return (
    <section
      aria-labelledby="profile-card-title"
      className="mx-5 mt-3 rounded-tile border border-chip-previous bg-chip-previous-bg p-4"
    >
      <h3 id="profile-card-title" className="font-semibold text-navy">
        יש לי פרטים מהשיחה מ־<bdi>{formatDayMonth(offer.saved_at)}</bdi>
      </h3>
      <p className="mt-0.5 text-[13px] text-muted">
        רק מה שתאשרו ישמש בשיחה הזאת. אפשר להסיר שורה או לעדכן לפני האישור.
      </p>
      {offer.stale_note ? (
        <p className="mt-1 flex items-center gap-1 text-[13px] text-chip-pending">
          <Icon name="alert" size={14} />
          {offer.stale_note}
        </p>
      ) : null}
      <ul className="mt-3 flex flex-col gap-2" aria-label="פרטים שמורים">
        {offer.fields.map((field) => {
          const gone = removed.has(field.name);
          const inputId = `profile-${field.name}`;
          return (
            <li
              key={field.name}
              className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-control bg-surface px-3 py-2"
            >
              <label
                htmlFor={editing && editable(field) && !gone ? inputId : undefined}
                className={`min-w-[6.5rem] flex-1 text-[14px] ${gone ? "text-muted line-through" : "text-ink"}`}
              >
                {field.label}
              </label>
              {gone ? (
                <span className="text-[13px] text-muted">לא ישמש בשיחה</span>
              ) : editing && editable(field) ? (
                <span className="inline-flex items-center gap-1">
                  <input
                    id={inputId}
                    dir="ltr"
                    inputMode="decimal"
                    value={typed[field.name] ?? field.value}
                    onChange={(e) => setTyped((all) => ({ ...all, [field.name]: e.target.value }))}
                    className="h-10 w-28 rounded-control border border-line bg-surface px-2 text-end font-mono"
                  />
                  {SUFFIX[field.unit] ? <span aria-hidden="true">{SUFFIX[field.unit]}</span> : null}
                </span>
              ) : (
                <span className="font-medium text-ink">
                  {field.unit === "ils" ? (
                    <Amount value={Number(field.value)} currency />
                  ) : (
                    <bdi>
                      {field.unit === "text" ? field.display : formatInput(field.value, field.unit)}
                    </bdi>
                  )}
                </span>
              )}
              {!gone ? <SourceChip source={field.source_chip} /> : null}
              <button
                type="button"
                aria-label={gone ? `החזרת ${field.label}` : `הסרת ${field.label}`}
                onClick={() => toggle(field.name)}
                className="inline-flex h-10 w-10 items-center justify-center rounded-control text-steel hover:bg-ground"
              >
                <Icon name={gone ? "refresh" : "x"} size={16} />
              </button>
            </li>
          );
        })}
      </ul>
      {error ? (
        <p role="alert" className="mt-2 flex items-center gap-1 text-[13px] text-down">
          <Icon name="alert" size={14} />
          {error}
        </p>
      ) : null}
      <div className="mt-3 flex flex-wrap gap-2">
        {editing ? (
          <Button disabled={busy || used.length === 0} onClick={() => onApply(choices())}>
            <Icon name="check" size={16} />
            אישור ושמירה
          </Button>
        ) : (
          <>
            <Button disabled={busy || used.length === 0} onClick={() => onApply(choices())}>
              להשתמש בהם
            </Button>
            <Button variant="secondary" disabled={busy} onClick={() => setEditing(true)}>
              לעדכן
            </Button>
          </>
        )}
        <Button variant="secondary" disabled={busy} onClick={onDismiss}>
          להתחיל מחדש
        </Button>
      </div>
      {asking ? (
        <div
          role="alertdialog"
          aria-labelledby="profile-delete-title"
          className="mt-3 rounded-control border border-down bg-surface p-3"
        >
          <p id="profile-delete-title" className="text-[14px] text-ink">
            למחוק את הפרטים השמורים? לא תהיה אפשרות לשחזר אותם.
          </p>
          <div className="mt-2 flex gap-2">
            <Button variant="secondary" disabled={busy} onClick={onDelete}>
              מחיקה
            </Button>
            <Button variant="secondary" onClick={() => setAsking(false)}>
              ביטול
            </Button>
          </div>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setAsking(true)}
          className="mt-3 border-0 bg-transparent p-0 text-[13px] text-steel underline"
        >
          מחיקת הפרטים השמורים
        </button>
      )}
    </section>
  );
}
