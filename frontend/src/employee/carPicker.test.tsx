import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/client";
import type { CarPicker, SessionEvent } from "../api/types";
import { initialSession, reduce } from "../state/session";
import { CurrentCarPicker } from "./CurrentCarPicker";
import { back, START, step } from "./carPicker";

// the shape the server builds from the catalog (compass/tools/car_picker.py)
const PICKER: CarPicker = {
  manufacturers: [
    {
      id: "00100",
      label: "טויוטה",
      models: [
        {
          id: "COROLLA",
          label: "COROLLA",
          years: [{ car_id: "CAR-07", year: 2026, label: "2026 · בנזין · קבוצה ג׳" }],
        },
        {
          id: "RAV4",
          label: "RAV4",
          years: [{ car_id: "CAR-18", year: 2025, label: "2025 · היברידי · קבוצה ד׳" }],
        },
      ],
    },
    {
      id: "00200",
      label: "קיה",
      models: [
        {
          id: "NIRO",
          label: "NIRO",
          years: [{ car_id: "CAR-05", year: 2025, label: "2025 · היברידי · קבוצה ב׳" }],
        },
      ],
    },
  ],
  extra: [
    { id: "not_in_list", label: "הרכב שלי לא ברשימה" },
    { id: "no_car", label: "אין לי רכב היום" },
  ],
  year_check: { id: "check_year", label: "שנה אחרת — לבדיקת נציג" },
};

describe("the steps", () => {
  it("manufacturer, model, year, and back one at a time", () => {
    expect(step(START)).toBe("maker");
    expect(step({ maker: "a", model: null })).toBe("model");
    expect(step({ maker: "a", model: "b" })).toBe("year");
    expect(back({ maker: "a", model: "b" })).toEqual({ maker: "a", model: null });
    expect(back({ maker: "a", model: null })).toEqual(START);
  });
});

describe("CurrentCarPicker", () => {
  it("manufacturer, then model, then year; the pick names the catalog car", async () => {
    const onPick = vi.fn().mockResolvedValue(undefined);
    render(<CurrentCarPicker picker={PICKER} onPick={onPick} />);
    const card = screen.getByRole("region");
    // only the server's manufacturers, and the two other choices, from the first step
    const makers = within(card).getByRole("list", { name: "האפשרויות" });
    expect(within(makers).getAllByRole("button").map((b) => b.textContent)).toEqual(["טויוטה", "קיה"]);
    expect(within(card).getByRole("button", { name: "הרכב שלי לא ברשימה" })).toBeInTheDocument();
    expect(within(card).getByRole("button", { name: "אין לי רכב היום" })).toBeInTheDocument();

    await userEvent.click(within(card).getByRole("button", { name: "טויוטה" }));
    expect(within(card).getByRole("heading")).toHaveTextContent("בחרו דגם");
    await userEvent.click(within(card).getByRole("button", { name: "COROLLA" }));
    expect(within(card).getByRole("heading")).toHaveTextContent("בחרו שנה");
    await userEvent.click(within(card).getByRole("button", { name: /COROLLA 2026/ }));
    expect(onPick).toHaveBeenCalledWith({ choice: "car", car_id: "CAR-07" });
  });

  it("the year step offers 'לבדיקת נציג' for another year, not 'a different car'", async () => {
    const onPick = vi.fn().mockResolvedValue(undefined);
    render(<CurrentCarPicker picker={PICKER} onPick={onPick} />);
    await userEvent.click(screen.getByRole("button", { name: "קיה" }));
    await userEvent.click(screen.getByRole("button", { name: "NIRO" }));
    await userEvent.click(screen.getByRole("button", { name: "שנה אחרת — לבדיקת נציג" }));
    expect(onPick).toHaveBeenCalledWith({ choice: "check_year", car_id: "CAR-05" });
  });

  it("the two other choices are there at every step, and back goes one step", async () => {
    const onPick = vi.fn().mockResolvedValue(undefined);
    render(<CurrentCarPicker picker={PICKER} onPick={onPick} />);
    await userEvent.click(screen.getByRole("button", { name: "טויוטה" }));
    await userEvent.click(screen.getByRole("button", { name: "חזרה" }));
    expect(screen.getByRole("heading")).toHaveTextContent("בחרו יצרן");
    await userEvent.click(screen.getByRole("button", { name: "אין לי רכב היום" }));
    expect(onPick).toHaveBeenCalledWith({ choice: "no_car" });
    await userEvent.click(screen.getByRole("button", { name: "הרכב שלי לא ברשימה" }));
    expect(onPick).toHaveBeenLastCalledWith({ choice: "not_in_list" });
  });

  it("a refusal stays on the card with the server's reason", async () => {
    const onPick = vi
      .fn()
      .mockRejectedValue(new ApiError(409, "current_car_not_needed", [
        { code: "current_car_not_needed", field: null, message: "הרכב של היום כבר נקבע." },
      ]));
    render(<CurrentCarPicker picker={PICKER} onPick={onPick} />);
    await userEvent.click(screen.getByRole("button", { name: "אין לי רכב היום" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("הרכב של היום כבר נקבע.");
  });
});

describe("the session's picker", () => {
  const base = { session_id: "s", created_at: "2026-10-20T12:00:00Z" };
  const offered = { ...base, seq: 1, type: "current_car_offered", payload: PICKER } as SessionEvent;

  it("set by the offer, cleared once today's car is known, picked, or a rep is asked", () => {
    const shown = reduce(initialSession, offered);
    expect(shown.carPicker).toEqual(PICKER);
    const cleared = [
      { ...base, seq: 2, type: "current_situation_set", payload: { scenario: {} } },
      { ...base, seq: 2, type: "current_car_picked", payload: { outcome: "not_in_list" } },
      {
        ...base,
        seq: 2,
        type: "ticket_opened",
        payload: { ticket: { id: "t", blocking_fields: ["current_car"] } },
      },
    ] as unknown as SessionEvent[];
    for (const event of cleared) expect(reduce(shown, event).carPicker).toBeNull();
    // a ticket about something else leaves it
    const other = {
      ...base,
      seq: 2,
      type: "ticket_opened",
      payload: { ticket: { id: "t", blocking_fields: ["current_participation"] } },
    } as unknown as SessionEvent;
    expect(reduce(shown, other).carPicker).toEqual(PICKER);
  });
});
