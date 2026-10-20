/** Today's car unknown (fix/current-car, item 2): every eligible alternative on screen with its
 * own net, the difference as "חסר הרכב של היום"; once today's car is set, the server's second
 * set brings the differences. The log is real: save_profile, list_options, then
 * set_current_situation, through the dev tools endpoint. */

import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { SessionEvent } from "../api/types";
import { initialSession, reduce } from "../state/session";
import log from "../test/fixtures/options_without_today.json";
import { Waterfall } from "../waterfall/Waterfall";
import { HeroCard } from "./HeroCard";
import { optionList } from "./options";
import { OptionsSelector } from "./OptionsSelector";
import { PhoneBar } from "./PhoneBar";

const events = log as unknown as SessionEvent[];
const sets = events.filter((e) => e.type === "comparison_set_ready");
const before = events.slice(0, events.indexOf(sets[1] as SessionEvent)).reduce(reduce, initialSession);
const after = events.reduce(reduce, initialSession);
const NOTE = "חסר הרכב של היום";

describe("before today's car is known", () => {
  const options = optionList(before);

  it("every eligible alternative is on screen, best net first, with no difference", () => {
    expect(options.length).toBeGreaterThan(2);
    const nets = options.map((o) => o.comparison.view.alternative_net ?? 0);
    expect(nets).toEqual([...nets].sort((a, b) => b - a));
    for (const { comparison } of options) {
      expect(comparison.view.display_diff).toBeNull();
      expect(comparison.view.diff_note).toBe(NOTE);
    }
  });

  it("each option shows its net and what the difference waits for", () => {
    render(
      <OptionsSelector
        options={options}
        selected={options[0]?.key ?? ""}
        onSelect={() => undefined}
      />,
    );
    const radios = within(screen.getByRole("radiogroup")).getAllByRole("radio");
    expect(radios).toHaveLength(options.length);
    const first = options[0]?.comparison.view;
    expect(radios[0]).toHaveTextContent(NOTE);
    expect(radios[0]).toHaveTextContent("חלקי"); // not final: no difference yet
    expect(radios[0]).not.toHaveTextContent("סופי");
    expect(radios[0]).toHaveTextContent((first?.alternative_net ?? 0).toLocaleString("en-US"));
    expect(radios[0]?.getAttribute("aria-label")).toContain(NOTE);
  });

  it("the hero shows the alternative's net and the note in place of the difference", () => {
    const shown = options[0]?.comparison;
    if (!shown) throw new Error("no option");
    render(<HeroCard comparison={shown} />);
    const hero = screen.getByRole("article", { name: "תוצאת ההשוואה" });
    expect(hero).toHaveTextContent(NOTE);
    expect(hero).toHaveTextContent((shown.view.alternative_net ?? 0).toLocaleString("en-US"));
    expect(hero).not.toHaveTextContent("ההפרש חלקי");
  });

  it("the waterfall says the breakdown waits for today's car, and the phone bar the note", () => {
    const shown = options[0]?.comparison;
    if (!shown) throw new Error("no option");
    render(
      <>
        <Waterfall view={shown.view} />
        <PhoneBar comparison={shown} heroId="hero" />
      </>,
    );
    expect(screen.getByRole("region", { name: "מאיפה מגיע ההפרש" })).toHaveTextContent(
      "פירוט ההפרש יוצג כשהרכב של היום יהיה ידוע",
    );
    expect(screen.queryByRole("alert")).toBeNull(); // not an invariant failure
    expect(screen.getByTestId("phone-bar")).toHaveTextContent(NOTE);
  });
});

describe("after today's car is set", () => {
  it("the server's second set brings every difference; the nets stay as they were", () => {
    const was = Object.fromEntries(
      optionList(before).map((o) => [o.key, o.comparison.view.alternative_net]),
    );
    const now = optionList(after);
    expect(now.length).toBeGreaterThan(2);
    for (const { key, comparison } of now) {
      const { view } = comparison;
      expect(view.display_diff).not.toBeNull();
      expect(view.diff_note).toBeNull();
      expect(view.alternative_net).toBe(was[key]);
      expect((view.today_net ?? 0) + (view.display_diff ?? 0)).toBe(view.alternative_net);
    }
  });
});
