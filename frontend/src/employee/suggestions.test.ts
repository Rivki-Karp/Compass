import { describe, expect, it } from "vitest";
import { demoSuggestions } from "./suggestions";

const scripts = [
  { name: "walkthrough", title: "ויתור", messages: ["w1", "w2"] },
  { name: "e001", title: "ATTO 3", messages: ["e1", "e2", "e3"] },
];

describe("demoSuggestions", () => {
  it("offers each script's first message at the start", () => {
    expect(demoSuggestions(scripts, [])).toEqual(["w1", "e1"]);
  });

  it("follows the script in progress", () => {
    expect(demoSuggestions(scripts, ["e1"])).toEqual(["e2"]);
    expect(demoSuggestions(scripts, ["w1 "])).toEqual(["w2"]); // whitespace-insensitive
  });

  it("offers nothing when the script is done or the conversation left it", () => {
    expect(demoSuggestions(scripts, ["w1", "w2"])).toEqual([]);
    expect(demoSuggestions(scripts, ["שלום"])).toEqual([]);
  });
});
