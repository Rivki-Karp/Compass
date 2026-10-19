/**
 * Dev-only: the design system in isolation (brief §3), for review. Swatch values are read from
 * the CSS variables at runtime, so this page cannot drift from index.css.
 */

import { useEffect, useState } from "react";
import type { ChipSource } from "../api/types";
import logo from "../assets/compass-logo.png";
import mark from "../assets/compass-mark.png";
import { MINUS } from "../lib/format";
import { Amount } from "../ui/Amount";
import { Button } from "../ui/Button";
import { Icon } from "../ui/icons";
import { Needle } from "../ui/Needle";
import { CHIP } from "../ui/chips";
import { SourceChip } from "../ui/SourceChip";

const GROUPS: { title: string; tokens: [string, string][]; dark?: boolean }[] = [
  {
    title: "מותג ומשטחים",
    tokens: [
      ["navy", "מותג, כותרות, בועות עובד, עמודת סה״כ"],
      ["royal", "פעולות ראשיות, טבעת מיקוד, בחירה"],
      ["steel", "הדגשות משניות, שבבי כלים"],
      ["mist", "קו המחט, קווים שקטים"],
      ["ground", "רקע העמוד, בועות הבוט"],
      ["surface", "כרטיסים"],
      ["ink", "טקסט"],
      ["muted", "טקסט משני"],
      ["line", "גבולות כרטיסים"],
      ["line-soft", "מפרידים בתוך כרטיס"],
    ],
  },
  {
    title: "כיוון הכסף",
    tokens: [
      ["up", "הפרש חיובי"],
      ["up-bg", "שבב ״סופי״, מחובר"],
      ["down", "הפרש שלילי"],
      ["down-bg", "גוון שלילי"],
    ],
  },
  {
    title: "חדר המנועים",
    dark: true,
    tokens: [
      ["engine", "רקע הפאנל"],
      ["engine-border", "גבול כרטיס אירוע"],
      ["engine-code", "רקע קוד"],
      ["engine-text", "טקסט"],
      ["engine-muted", "טקסט משני"],
      ["engine-model", "אירוע מודל"],
      ["engine-tool", "תוצאת כלי"],
      ["engine-tool-border", "גבול תוצאת כלי"],
      ["engine-guard-bg", "רקע השומר"],
      ["engine-guard", "הדגשת השומר"],
      ["engine-guard-border", "גבול השומר"],
      ["knob-on", "ידית מתג פעיל"],
    ],
  },
];

const SOURCES = Object.keys(CHIP) as ChipSource[];

function useTokenValue(name: string): string {
  const [value, setValue] = useState("");
  useEffect(() => {
    setValue(
      getComputedStyle(document.documentElement).getPropertyValue(`--color-${name}`).trim(),
    );
  }, [name]);
  return value;
}

function Swatch({ name, use, dark }: { name: string; use: string; dark?: boolean }) {
  const value = useTokenValue(name);
  return (
    <li className="flex items-center gap-3">
      <span
        className="h-11 w-11 shrink-0 rounded-tile border border-line"
        style={{ background: `var(--color-${name})` }}
      />
      <span>
        <code className={`font-mono text-[13px] ${dark ? "text-engine-text" : "text-ink"}`}>
          {name} {value}
        </code>
        <span className={`block text-[12px] ${dark ? "text-engine-muted" : "text-muted"}`}>
          {use}
        </span>
      </span>
    </li>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-card border border-line bg-surface p-6">
      <h2 className="mb-4 text-[15px] font-semibold text-navy">{title}</h2>
      {children}
    </section>
  );
}

export function Styleguide() {
  return (
    <main className="mx-auto flex max-w-[1240px] flex-col gap-6 px-8 py-6">
      <header className="flex flex-wrap items-center gap-4">
        <img src={mark} alt="" className="h-12 w-12" />
        <div>
          <div className="ltr text-[20px] font-bold tracking-[0.04em] text-navy">COMPASS</div>
          <div className="text-[13px] text-muted">יועץ הרכב של Strauss</div>
        </div>
        <span className="ms-auto rounded-chip bg-ground px-3 py-1 text-[13px] text-muted">
          מדריך סגנון · מסלול פיתוח בלבד
        </span>
      </header>

      {GROUPS.map((group) => (
        <section
          key={group.title}
          className={`rounded-card border p-6 ${group.dark ? "border-engine-border bg-engine" : "border-line bg-surface"}`}
        >
          <h2
            className={`mb-4 text-[15px] font-semibold ${group.dark ? "text-engine-text" : "text-navy"}`}
          >
            {group.title}
          </h2>
          <ul className="grid grid-cols-[repeat(auto-fill,minmax(260px,1fr))] gap-4">
            {group.tokens.map(([name, use]) => (
              <Swatch key={name} name={name} use={use} dark={group.dark} />
            ))}
          </ul>
        </section>
      ))}

      <Section title="טיפוגרפיה">
        <div className="flex flex-col gap-4">
          <div className="flex items-baseline gap-2 text-up">
            <span className="text-[64px] leading-none font-bold">
              <Amount value={2914} signed />
            </span>
            <span className="text-[28px] font-bold">₪</span>
            <span className="text-[13px] text-muted">הפרש · 64/700 (52 במצב שופטים)</span>
          </div>
          <div className="text-[24px] font-semibold">
            <Amount value={13914} currency />{" "}
            <span className="text-[13px] font-normal text-muted">סכום בכרטיס · 24/600</span>
          </div>
          <div className="text-[22px] font-bold text-navy">כותרת מסך · 22/700</div>
          <div className="text-[15px] font-semibold">כותרת אזור · 15/600</div>
          <p className="max-w-[60ch]">
            גוף טקסט · 15/1.6. אם תוותרי על הרכב, הנטו המשוער עולה מ-
            <Amount value={11000} currency /> ל-<Amount value={13914} currency />: הפרש של{" "}
            <Amount value={2914} signed currency /> בחודש.
          </p>
          <div className="text-[13px] text-muted">מטא · 12–13</div>
          <code className="font-mono text-[13px] text-steel">save_profile · CAR-10 · {"{ }"}</code>
        </div>
      </Section>

      <Section title="מספרים ב-RTL">
        <ul className="grid gap-2 text-[15px]">
          <li>
            חיובי: <Amount value={2914} signed currency /> · שלילי:{" "}
            <Amount value={-50} signed currency /> · אפס: <Amount value={0} signed currency />
          </li>
          <li>
            סימן המינוס הוא U+2212 (<bdi>{MINUS}</bdi>), לא מקף. כל סכום עטוף ב-
            <code className="font-mono">&lt;bdi&gt;</code>.
          </li>
        </ul>
      </Section>

      <Section title="שבבי מקור">
        <div className="flex flex-wrap items-center gap-3">
          {SOURCES.map((source) => (
            <SourceChip key={source} source={source} />
          ))}
          <span className="inline-flex items-center gap-1 rounded-chip bg-up-bg px-2.5 py-0.5 text-[12px] font-semibold text-up">
            <Icon name="check" size={13} />
            סופי
          </span>
          <span className="inline-flex items-center gap-1 rounded-chip bg-tool-chip-bg px-2.5 py-0.5 font-mono text-[12px] text-steel">
            <span className="ltr">save_profile ✓</span>
          </span>
          <span className="inline-flex items-center gap-1 rounded-chip bg-tool-chip-bg px-2.5 py-0.5 font-mono text-[12px] text-down">
            <span className="ltr">compare ✕</span>
          </span>
        </div>
      </Section>

      <Section title="המחט">
        <div className="flex flex-wrap items-end gap-10">
          {(["up", "down", "flat", "empty"] as const).map((direction) => (
            <figure key={direction} className="flex flex-col items-center gap-2">
              <Needle direction={direction} />
              <figcaption className="text-[12px] text-muted">
                {
                  {
                    up: "יותר נטו",
                    down: "פחות נטו",
                    flat: "ללא שינוי",
                    empty: "לפני חישוב",
                  }[direction]
                }
              </figcaption>
            </figure>
          ))}
        </div>
      </Section>

      <Section title="כפתורים ומיקוד">
        <p className="mb-4 text-[13px] text-muted">
          לחצו Tab כדי לראות את טבעת המיקוד (3px royal, מרווח 2px). גובה מינימלי 44px.
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <Button>אישור ושליחה לעובד/ת</Button>
          <Button variant="secondary">נסו שוב</Button>
          <Button variant="suggestion">ומה אם אעבור לחשמלי?</Button>
          <Button disabled>לא זמין</Button>
          <button
            type="button"
            aria-label="שליחה"
            className="inline-flex h-12 w-12 items-center justify-center rounded-tile bg-royal text-white hover:bg-navy"
          >
            <Icon name="arrowLeft" size={20} />
          </button>
        </div>
      </Section>

      <Section title="צורה">
        <div className="flex flex-wrap items-center gap-4 text-[12px] text-muted">
          <div className="flex h-20 w-32 items-center justify-center rounded-card border border-line">
            כרטיס 16
          </div>
          <div className="flex h-16 w-28 items-center justify-center rounded-tile border border-line">
            אריח 12
          </div>
          <div className="flex h-11 w-24 items-center justify-center rounded-control border border-line">
            פקד 10
          </div>
          <div className="max-w-[260px] rounded-[14px] rounded-es-[4px] border border-bubble-border bg-ground px-3 py-2 text-[15px] text-ink">
            בועת בוט
          </div>
          <div className="max-w-[260px] rounded-[14px] rounded-ee-[4px] bg-navy px-3 py-2 text-[15px] text-white">
            בועת עובד/ת
          </div>
        </div>
      </Section>

      <Section title="לוגו מלא (README, favicon)">
        <img src={logo} alt="Compass Car Advisor" className="h-28" />
      </Section>
    </main>
  );
}
