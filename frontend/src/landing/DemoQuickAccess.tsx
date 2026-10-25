import { useState } from "react";
import type { Role } from "../auth/authStore";
import { useAuth } from "../auth/context";
import { useHealth } from "../lib/useHealth";
import { Icon } from "../ui/icons";

const CHOICES: { role: Role; label: string; hint: string }[] = [
  { role: "employee", label: "עובדת", hint: "צ'אט, תלוש והיסטוריה" },
  { role: "rep", label: "נציג", hint: "מענה לפניות" },
  { role: "admin", label: "מנהלת", hint: "הזמנת משתמשים · מצב שופטים" },
];

const UNAVAILABLE = "לא ניתן להיכנס כרגע. נסו שוב.";

/**
 * "כניסה מהירה להתנסות" (COMPASS_DEMO_LOGIN): for judges and recruiters, one click into a shared
 * demo account of each role, with no password. Shown only when GET /api/health says it is on.
 */
export function DemoQuickAccess() {
  const health = useHealth();
  const auth = useAuth();
  const [busy, setBusy] = useState<Role | null>(null);
  const [error, setError] = useState<string | null>(null);
  if (health?.demo_login !== true) return null;

  async function enter(role: Role) {
    setBusy(role);
    setError(null);
    try {
      await auth.demoLogin(role);
    } catch {
      setError(UNAVAILABLE);
      setBusy(null);
    }
  }

  return (
    <section
      aria-labelledby="quick-title"
      className="lp-rise flex min-w-0 flex-col gap-3.5 rounded-[22px] border border-white/20 bg-white/[0.07] p-6 backdrop-blur-[18px] [animation-delay:0.7s]"
    >
      <div className="flex items-center gap-2.5">
        <span className="text-engine-tool">
          <Icon name="check" size={20} />
        </span>
        <h2 id="quick-title" className="text-[19px] font-bold text-white">
          כניסה מהירה להתנסות
        </h2>
      </div>
      <p className="-mt-1.5 text-[14px] text-soft">לשופטים ולמגייסים: לחיצה אחת, בלי סיסמה.</p>
      <div className="grid grid-cols-1 gap-2.5 min-[420px]:grid-cols-3">
        {CHOICES.map((choice) => (
          <button
            key={choice.role}
            type="button"
            disabled={busy !== null}
            onClick={() => void enter(choice.role)}
            className="flex min-h-[84px] flex-col items-start justify-center gap-1 rounded-[12px] border border-white/25 px-3.5 py-2.5 text-start text-white hover:bg-white/10 disabled:opacity-60"
          >
            <span className="text-[17px] font-semibold">
              {busy === choice.role ? "נכנסים…" : choice.label}
            </span>
            <span className="text-[13px] leading-snug text-soft">{choice.hint}</span>
          </button>
        ))}
      </div>
      {error ? (
        <p role="alert" className="text-[14px] font-medium text-chip-pending-bg">
          {error}
        </p>
      ) : null}
      <p className="text-[13px] text-soft">חשבונות הדגמה משותפים. אל תזינו מידע אישי אמיתי.</p>
    </section>
  );
}
