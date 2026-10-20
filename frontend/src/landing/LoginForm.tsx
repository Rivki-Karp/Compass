import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/context";
import { dismissNotice } from "../auth/authStore";
import { Field } from "../auth/Field";
import { Icon } from "../ui/icons";

const GENERIC_ERROR = "מייל או סיסמה שגויים";
const UNAVAILABLE = "לא ניתן להתחבר כרגע. נסו שוב.";

/** The glass login card (briefs/design/Landing): email, password, "כניסה", and the way to the
 * first registration. The server's message is shown as it is: it never says which part failed. */
export function LoginForm() {
  const auth = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!email.trim() || !password) {
      setError(GENERIC_ERROR);
      return;
    }
    dismissNotice();
    setBusy(true);
    setError(null);
    try {
      await auth.login(email, password);
    } catch (failure) {
      setError(
        failure instanceof ApiError && typeof failure.detail === "string" && failure.status < 500
          ? failure.detail
          : UNAVAILABLE,
      );
      setPassword("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form
      aria-label="כניסה לעובדים"
      onSubmit={submit}
      noValidate
      className="lp-rise flex h-full min-w-0 flex-col gap-[18px] rounded-[22px] border border-white/20 bg-white/[0.07] p-8 backdrop-blur-[18px] [animation-delay:0.6s] max-sm:p-6"
    >
      <div className="flex items-center gap-2.5">
        <span className="text-engine-tool">
          <Icon name="shield" size={22} />
        </span>
        <h2 className="text-[22px] font-bold text-white">כניסה לעובדים</h2>
      </div>
      <p className="-mt-2 text-[14px] text-soft">
        רק לעובדי הקבוצה. השיחות שלך נשמרות ונגישות רק לך.
      </p>
      {auth.notice ? (
        <p
          role="status"
          className="rounded-tile bg-chip-pending-bg px-3 py-2 text-[14px] text-chip-pending"
        >
          {auth.notice}
        </p>
      ) : null}
      <Field
        label="מייל"
        id="login-email"
        type="email"
        ltr
        autoComplete="username"
        placeholder="name@company.co.il"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        describedBy={error ? "login-error" : undefined}
      />
      <Field
        label="סיסמה"
        id="login-password"
        type="password"
        autoComplete="current-password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        describedBy={error ? "login-error" : undefined}
      />
      {error ? (
        <p id="login-error" role="alert" className="text-[14px] font-medium text-chip-pending-bg">
          {error}
        </p>
      ) : null}
      <button
        type="submit"
        disabled={busy}
        className="inline-flex min-h-[54px] items-center justify-center gap-2.5 rounded-[12px] bg-royal text-[17px] font-semibold text-white hover:bg-royal-hover disabled:opacity-60"
      >
        {busy ? "נכנסים…" : "כניסה"}
        <Icon name="arrowLeft" size={18} />
      </button>
      <div className="h-px bg-white/15" />
      <span className="text-[14px] text-soft">
        קיבלת קוד הזמנה?{" "}
        <Link to="/register" className="font-semibold text-engine-guard underline hover:text-white">
          הרשמה ראשונה
        </Link>
      </span>
    </form>
  );
}
