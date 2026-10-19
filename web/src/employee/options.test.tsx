/** Every alternative on screen (round 2, item 4): the list, the default, the keyboard, and the
 * panels that follow the selection. The log is real: the walkthrough, then list_options. */

import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { SessionEvent } from "../api/types";
import { initialSession, reduce, type SessionState } from "../state/session";
import optionsLog from "../test/fixtures/options.json";
import { Waterfall } from "../waterfall/Waterfall";
import { HeroCard } from "./HeroCard";
import { InputsCard } from "./InputsCard";
import { defaultOptionKey, optionList, shownComparison, useOptionSelection } from "./options";
import { OptionsSelector } from "./OptionsSelector";

const log = optionsLog as unknown as SessionEvent[];
const state = log.reduce(reduce, initialSession);

describe("the options", () => {
  it("are every alternative on screen, best first", () => {
    const options = optionList(state);
    const diffs = options.map((o) => o.comparison.view.display_diff);
    expect(options.length).toBeGreaterThan(2);
    expect(diffs).toEqual([...diffs].sort((a, b) => b - a));
    expect(options[0]?.key).toBe("waiver:");
    expect(options.map((o) => o.comparison.view.alternative_title)).toContain("MG4");
  });

  it("default: the one the agent compared last (the walkthrough's waiver), else the best", () => {
    const options = optionList(state);
    expect(defaultOptionKey(options, state.comparison)).toBe("waiver:");
    expect(defaultOptionKey(options, null)).toBe(options[0]?.key);
    const mg4 = options.find((o) => o.comparison.view.alternative_title === "MG4");
    expect(shownComparison(options, state.comparison, mg4?.key ?? null)).toBe(mg4?.comparison);
    expect(shownComparison(options, state.comparison, "car:NOPE")?.view.alternative_kind).toBe(
      "waiver",
    );
  });

  it("the set keeps the hero where it was", () => {
    const before = log.slice(
      0,
      log.findIndex((e) => e.type === "comparison_set_ready"),
    );
    expect(state.comparison).toEqual(before.reduce(reduce, initialSession).comparison);
  });
});

describe("OptionsSelector: a radio group", () => {
  const options = optionList(state);

  function renderSelector(selected = options[0]?.key ?? "") {
    const onSelect = vi.fn();
    render(<OptionsSelector options={options} selected={selected} onSelect={onSelect} />);
    return onSelect;
  }

  it("one radio per option, one tab stop, each with its name, diff and state", () => {
    renderSelector();
    const radios = within(screen.getByRole("radiogroup")).getAllByRole("radio");
    expect(radios).toHaveLength(options.length);
    expect(radios.filter((r) => r.tabIndex === 0)).toHaveLength(1);
    expect(radios[0]).toHaveAttribute("aria-checked", "true");
    expect(
      screen.getByRole("radio", { name: /^MG4, חשמלי · קבוצה ב׳: פלוס 1,013 שקלים, סופי$/ }),
    ).toBeInTheDocument();
  });

  it("arrow keys, Home, End and Enter select", async () => {
    const onSelect = renderSelector();
    const user = userEvent.setup();
    const radios = screen.getAllByRole("radio");
    act(() => radios[0]?.focus());
    await user.keyboard("{ArrowDown}");
    expect(onSelect).toHaveBeenLastCalledWith(options[1]?.key);
    await user.keyboard("{End}");
    expect(onSelect).toHaveBeenLastCalledWith(options[options.length - 1]?.key);
    await user.keyboard("{Home}");
    expect(onSelect).toHaveBeenLastCalledWith(options[0]?.key);
    await user.keyboard("{ArrowUp}"); // wraps around
    expect(onSelect).toHaveBeenLastCalledWith(options[options.length - 1]?.key);
    act(() => radios[2]?.focus());
    await user.keyboard("{Enter}");
    expect(onSelect).toHaveBeenLastCalledWith(options[2]?.key);
  });
});

/** The employee screen's panels, driven by the selection as EmployeePage drives them. */
function Panels({ session }: { session: SessionState }) {
  const { options, comparison, selected, select } = useOptionSelection(session);
  if (!comparison || !selected) return null;
  return (
    <>
      <OptionsSelector options={options} selected={selected} onSelect={select} />
      <HeroCard comparison={comparison} />
      <Waterfall view={comparison.view} />
      <InputsCard view={comparison.view} />
    </>
  );
}

describe("selecting an option switches every panel", () => {
  it("the hero, the waterfall and its provenance strip, the inputs card", async () => {
    render(<Panels session={state} />);
    const hero = screen.getByRole("article", { name: "תוצאת ההשוואה" });
    expect(hero).toHaveTextContent("ויתור על הרכב לעומת היום");
    expect(hero).toHaveTextContent("+2,914");
    expect(screen.getByText(/חושב בכלי/)).toBeInTheDocument(); // the agent's own compare

    await userEvent.setup().click(screen.getByRole("radio", { name: /^MG4/ }));
    expect(hero).toHaveTextContent("MG4 לעומת היום");
    expect(hero).toHaveTextContent("+1,013");
    expect(hero).not.toHaveTextContent("+2,914");
    expect(screen.getByText("חושב מחדש בשרת · בלי מודל")).toBeInTheDocument(); // the strip
    const inputs = screen.getByRole("region", { name: "על מה החישוב מבוסס" });
    expect(inputs).toHaveTextContent("הרכב בחלופה · MG4");
    expect(screen.getByRole("radio", { name: /^MG4/ })).toHaveAttribute("aria-checked", "true");
  });

  it("a new compare by the agent takes the screen back", async () => {
    const { rerender } = render(<Panels session={state} />);
    await userEvent.setup().click(screen.getByRole("radio", { name: /^MG4/ }));
    const waiver = log.filter((e) => e.type === "comparison_ready").at(-1) as SessionEvent;
    const again = reduce(state, { ...waiver, seq: state.lastSeq + 1 });
    rerender(<Panels session={again} />);
    expect(screen.getByRole("article", { name: "תוצאת ההשוואה" })).toHaveTextContent(
      "ויתור על הרכב לעומת היום",
    );
  });
});
