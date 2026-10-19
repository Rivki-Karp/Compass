/**
 * Car names in right-to-left text (round 3, item 1): a bubble with "MG4" shows "MG4" on screen,
 * never "4MG". The DOM text is the same either way, so this reads the order the browser drew the
 * letters in, left to right.
 */

import { expect, test } from "@playwright/test";

test("a chat bubble with MG4 reads MG4 on screen", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("מחובר", { exact: true })).toBeVisible();
  await page.getByLabel("הודעה").fill("מה יקרה לנטו אם אעבור ל-MG4 בקבוצה ג׳?");
  await page.getByRole("button", { name: "שליחה" }).click();

  const bubble = page.getByRole("listitem").filter({ hasText: "MG4" }).first();
  await expect(bubble).toBeVisible();
  const drawn = await bubble.evaluate((el) => {
    // every character of the bubble with its text node, so the token is found across nodes
    const chars: { node: Text; i: number }[] = [];
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const length = node.textContent?.length ?? 0;
      for (let i = 0; i < length; i++) chars.push({ node: node as Text, i });
    }
    const at = (el.textContent ?? "").indexOf("MG4");
    if (at < 0) throw new Error("no MG4 in the bubble");
    return chars
      .slice(at, at + 3)
      .map(({ node, i }) => {
        const range = document.createRange();
        range.setStart(node, i);
        range.setEnd(node, i + 1);
        return { ch: node.textContent?.[i] ?? "", x: range.getBoundingClientRect().left };
      })
      .sort((a, b) => a.x - b.x)
      .map((l) => l.ch)
      .join("");
  });
  expect(drawn).toBe("MG4");
});
