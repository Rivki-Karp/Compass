/**
 * The numbers on the landing page's demo card.
 *
 * MARKETING ONLY: this is the golden E-001 example (BYD ATTO 3, group ג׳; the representative
 * confirms 350 ₪ participation), typed here so the page can show it before anyone is logged in.
 * It is not a calculation and it is not read by anything that computes money: the real figures
 * always come from the server's tools, with a source for each.
 */

export const DEMO_CAR = "BYD ATTO 3 · חשמלי · קבוצה ג'";
export const DEMO_PENDING_DIFF = 661; // before the representative answers
export const DEMO_FINAL_DIFF = 611; // after: participation 350 ₪
export const DEMO_PARTICIPATION = 350;

/** The waterfall bars: height in percent, and which colour token paints it. */
export const DEMO_BARS: readonly { height: number; tone: "navy" | "up" | "down" | "royal" }[] = [
  { height: 96, tone: "navy" },
  { height: 40, tone: "up" },
  { height: 28, tone: "up" },
  { height: 18, tone: "down" },
  { height: 24, tone: "royal" },
  { height: 100, tone: "up" },
];

/** The source chips under the bars: label, and the chip tokens that colour it. */
export const DEMO_CHIPS: readonly { label: string; tone: string }[] = [
  { label: "אושר על ידי נציג", tone: "text-chip-rep bg-chip-rep-bg" },
  { label: "לפי התלוש", tone: "text-up-ink bg-up-bg" },
  { label: "לפי העיסוק", tone: "text-chip-occupation bg-chip-occupation-bg" },
  { label: "לפי דבריך", tone: "text-chip-employee bg-chip-employee-bg" },
];
