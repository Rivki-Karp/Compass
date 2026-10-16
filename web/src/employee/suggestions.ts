import type { DemoScript } from "../api/types";

/** Outside demo mode: plain example questions (they only send text). */
export const GENERAL_SUGGESTIONS = ["מה יקרה לנטו אם אוותר על הרכב?", "ומה אם אעבור לחשמלי?"];

/**
 * In demo mode, the next message of every script the conversation so far follows: at the start
 * the first message of each script, then the next one of the script in progress. The demo model
 * answers these exact texts (anything else gets its fixed no-numbers reply).
 */
export function demoSuggestions(scripts: DemoScript[], sent: string[]): string[] {
  const normalize = (text: string) => text.split(/\s+/).join(" ").trim();
  const said = sent.map(normalize);
  return scripts.flatMap((script) => {
    const messages = script.messages.map(normalize);
    const follows = said.every((text, i) => messages[i] === text);
    const next = script.messages[said.length];
    return follows && next !== undefined ? [next] : [];
  });
}
