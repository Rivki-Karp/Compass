import { useState } from "react";
import { ApiError, type CarPick } from "../api/client";
import type { CarPicker } from "../api/types";
import { Button } from "../ui/Button";
import { Icon } from "../ui/icons";
import { BidiText } from "../ui/BidiText";
import { back, makerOf, modelOf, START, step, type PickerPath } from "./carPicker";

/**
 * Today's car, picked from the catalog: manufacturer, then model, then year; and always "הרכב
 * שלי לא ברשימה" and "אין לי רכב היום". Every option is the server's (built from the catalog);
 * nothing is typed. The pick is sent as it is; the card goes away when the server records it
 * (the event clears it), so a failed call leaves it here with the reason.
 */
export function CurrentCarPicker({
  picker,
  onPick,
}: {
  picker: CarPicker;
  onPick: (pick: CarPick) => Promise<void>;
}) {
  const [path, setPath] = useState<PickerPath>(START);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const where = step(path);
  const maker = makerOf(picker, path);
  const model = modelOf(picker, path);

  async function pick(choice: CarPick) {
    setBusy(true);
    setError(null);
    try {
      await onPick(choice);
      setBusy(false);
    } catch (e) {
      setError(
        e instanceof ApiError && e.errors[0]?.message
          ? e.errors[0].message
          : "לא הצלחנו לשמור את הבחירה. נסו שוב.",
      );
      setBusy(false);
    }
  }

  const title =
    where === "maker"
      ? "איזה רכב צמוד יש לכם היום? בחרו יצרן"
      : where === "model"
        ? `בחרו דגם · ${maker?.label ?? ""}`
        : `בחרו שנה · ${model?.label ?? ""}`;

  return (
    <section
      aria-labelledby="car-picker-title"
      className="mx-5 mb-3 rounded-tile border border-line bg-ground p-4"
    >
      <div className="flex items-center gap-2">
        {where !== "maker" ? (
          <button
            type="button"
            aria-label="חזרה"
            onClick={() => setPath(back(path))}
            disabled={busy}
            className="inline-flex h-9 w-9 items-center justify-center rounded-control text-steel hover:bg-surface disabled:opacity-50"
          >
            <Icon name="arrowRight" size={16} />
          </button>
        ) : null}
        <h3 id="car-picker-title" className="font-semibold text-navy">
          <BidiText text={title} />
        </h3>
      </div>

      <ul className="mt-3 flex flex-wrap gap-2" aria-label="האפשרויות">
        {where === "maker"
          ? picker.manufacturers.map((m) => (
              <li key={m.id}>
                <Button
                  variant="suggestion"
                  disabled={busy}
                  onClick={() => setPath({ maker: m.id, model: null })}
                >
                  <BidiText text={m.label} />
                </Button>
              </li>
            ))
          : null}
        {where === "model"
          ? (maker?.models ?? []).map((m) => (
              <li key={m.id}>
                <Button
                  variant="suggestion"
                  disabled={busy}
                  onClick={() => setPath({ maker: path.maker, model: m.id })}
                >
                  <BidiText text={m.label} />
                </Button>
              </li>
            ))
          : null}
        {where === "year"
          ? (model?.years ?? []).map((y) => (
              <li key={y.car_id}>
                <Button
                  variant="suggestion"
                  disabled={busy}
                  onClick={() => void pick({ choice: "car", car_id: y.car_id })}
                >
                  <BidiText text={`${model?.label ?? ""} ${y.label}`} />
                </Button>
              </li>
            ))
          : null}
        {where === "year" && model?.years[0] ? (
          <li>
            {/* the model matches, the year does not: a representative checks, the employee's
                car is not "a different car" */}
            <Button
              variant="secondary"
              disabled={busy}
              onClick={() =>
                void pick({ choice: "check_year", car_id: (model.years[0] as { car_id: string }).car_id })
              }
            >
              {picker.year_check.label}
            </Button>
          </li>
        ) : null}
      </ul>

      <ul className="mt-3 flex flex-wrap gap-2 border-t border-line-soft pt-3" aria-label="אחר">
        {picker.extra.map((choice) => (
          <li key={choice.id}>
            <Button
              variant="secondary"
              disabled={busy}
              onClick={() => void pick({ choice: choice.id as "not_in_list" | "no_car" })}
            >
              {choice.label}
            </Button>
          </li>
        ))}
      </ul>
      {error ? (
        <p role="alert" className="mt-2 flex items-center gap-1 text-[13px] text-down">
          <Icon name="alert" size={14} />
          {error}
        </p>
      ) : null}
    </section>
  );
}
