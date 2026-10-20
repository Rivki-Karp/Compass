import { useState } from "react";
import type { PendingPayslip } from "../state/session";
import { Button } from "../ui/Button";
import { Icon } from "../ui/icons";
import { basisCaption, confirmBody, ready, rows, warning, type Row } from "./payslip";

const UNIT_SUFFIX: Record<Row["unit"], string> = { ils: "₪", percent: "%", points: "", month: "" };

/** The pending candidate, field by field: the value (editable), a warning when the read is
 * unsure, remove / restore; one button confirms. RTL, numbers in <bdi>. */
export function PayslipCard({
  pending,
  busy,
  onConfirm,
}: {
  pending: PendingPayslip;
  busy: boolean;
  onConfirm: (fields: Record<string, string>) => void;
}) {
  const [list, setList] = useState<Row[]>(() => rows(pending.fields));
  const set = (name: string, change: Partial<Row>) =>
    setList((all) => all.map((r) => (r.name === name ? { ...r, ...change } : r)));

  return (
    <section
      aria-labelledby="payslip-card-title"
      className="mx-5 mb-3 rounded-tile border border-chip-payslip bg-chip-payslip-bg p-4"
    >
      <h3 id="payslip-card-title" className="font-semibold text-navy">
        מה קראנו מהתלוש
      </h3>
      <p className="mt-0.5 text-[13px] text-muted">
        בדקו כל שדה. אפשר לתקן ערך או להסיר שדה; רק מה שתאשרו יישמר.
      </p>
      <ul className="mt-3 flex flex-col gap-2" aria-label="שדות מהתלוש">
        {list.map((row) => {
          const note = warning(row);
          const inputId = `payslip-${row.name}`;
          return (
            <li
              key={row.name}
              className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-control bg-surface px-3 py-2 max-[699px]:flex-col max-[699px]:items-stretch"
            >
              <label htmlFor={inputId} className={`min-w-[6.5rem] flex-1 text-[14px] ${row.removed ? "text-muted line-through" : "text-ink"}`}>
                {row.label}
                {row.info ? <span className="ms-1 text-[12px] text-muted">(לידיעה)</span> : null}
              </label>
              {row.removed && row.noneable && row.read === null ? (
                // the payslip has no such line: one tap answers 0 (the employee's answer)
                <span className="text-[13px] text-muted">לא נמצא בתלוש — אין?</span>
              ) : row.removed ? (
                <span className="text-[13px] text-muted">
                  {row.read === null ? "לא יישמר" : (
                    <>
                      הוסר · <bdi>{row.read}</bdi>
                    </>
                  )}
                </span>
              ) : row.choices ? (
                <fieldset className="flex w-full flex-col gap-1">
                  <legend className="sr-only">{row.label}</legend>
                  {row.choices.map((choice) => (
                    <label key={choice.value} className="flex items-center gap-2 text-[14px]">
                      <input
                        type="radio"
                        name={inputId}
                        checked={row.value === choice.value}
                        onChange={() => set(row.name, { value: choice.value })}
                      />
                      <span>{choice.label}</span>
                    </label>
                  ))}
                </fieldset>
              ) : (
                <span className="inline-flex items-center gap-1">
                  <input
                    id={inputId}
                    dir="ltr"
                    inputMode={row.unit === "month" ? "text" : "decimal"}
                    value={row.value}
                    readOnly={row.unit === "month"}
                    onChange={(e) => set(row.name, { value: e.target.value })}
                    aria-describedby={note ? `${inputId}-note` : undefined}
                    className="h-10 w-28 rounded-control border border-line bg-surface px-2 text-end font-mono max-[699px]:w-full"
                  />
                  {UNIT_SUFFIX[row.unit] ? <span aria-hidden="true">{UNIT_SUFFIX[row.unit]}</span> : null}
                </span>
              )}
              {row.removed && row.noneable && row.read === null ? (
                <Button variant="secondary" onClick={() => set(row.name, { removed: false, value: "0" })}>
                  אין
                </Button>
              ) : row.removed ? (
                <Button variant="secondary" onClick={() => set(row.name, { removed: false, value: row.value || (row.read ?? "") })}>
                  החזרה
                </Button>
              ) : (
                <button
                  type="button"
                  aria-label={`הסרת ${row.label}`}
                  onClick={() => set(row.name, { removed: true })}
                  className="inline-flex h-10 w-10 items-center justify-center rounded-control text-steel hover:bg-ground"
                >
                  <Icon name="x" size={16} />
                </button>
              )}
              {basisCaption(row) && !row.removed ? (
                <p className="w-full text-[12px] text-muted">{basisCaption(row)}</p>
              ) : null}
              {note && !row.removed ? (
                <p id={`${inputId}-note`} className="flex w-full items-center gap-1 text-[12px] text-chip-pending">
                  <Icon name="alert" size={13} />
                  {note}
                </p>
              ) : null}
            </li>
          );
        })}
      </ul>
      <Button
        className="mt-3 w-full"
        disabled={busy || !ready(list)}
        onClick={() => onConfirm(confirmBody(list).fields)}
      >
        <Icon name="check" size={16} />
        אישור ושמירה
      </Button>
    </section>
  );
}
