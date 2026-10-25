import { useAuth } from "../auth/context";

/** A thin strip on every page of a demo login (the quick access): the account is shared. */
export function DemoBanner() {
  const auth = useAuth();
  if (auth.status !== "in" || !auth.user?.demo) return null;
  return (
    <div
      role="region"
      aria-label="חשבון הדגמה"
      className="flex flex-wrap items-center justify-center gap-x-4 gap-y-1 bg-chip-pending-bg px-4 py-1.5 text-[13px] font-medium text-chip-pending"
    >
      <span>את/ה בחשבון הדגמה משותף</span>
      <button
        type="button"
        onClick={() => void auth.logout()}
        className="inline-flex min-h-8 items-center underline"
      >
        התנתקות
      </button>
    </div>
  );
}
