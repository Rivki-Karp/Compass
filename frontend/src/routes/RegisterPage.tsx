import { useState, type FormEvent } from "react";
import { Link, Navigate } from "react-router-dom";
import mark from "../assets/compass-mark.png";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/context";
import { Field } from "../auth/Field";
import {
  NAME_MAX,
  PASSWORD_MATCH_MESSAGE,
  formatCodeInput,
  passwordProblem,
} from "../auth/rules";
import "../landing/landing.css";
import { Icon } from "../ui/icons";

const GENERIC_ERROR = "הקוד או המייל אינם תקינים";
const UNAVAILABLE = "לא ניתן להירשם כרגע. נסו שוב.";

/**
 * `/register` (COMPASS_AUTH=1): the first registration, with the invite code the admin gave. The
 * password rules are checked here before submit; everything about the invite stays the server's
 * one generic message, so this form cannot be used to find out who was invited.
 */
export function RegisterPage() {
  const auth = useAuth();
  const [form, setForm] = useState({ email: "", code: "", name: "", password: "", confirm: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (auth.status === "in") return <Navigate to="/" replace />;

  const set = (key: keyof typeof form) => (value: string) => setForm((f) => ({ ...f, [key]: value }));

  async function submit(event: FormEvent) {
    event.preventDefault();
    const email = form.email.trim();
    const name = form.name.trim();
    if (!email || form.code.replace("-", "").length < 10 || !name) {
      setError(GENERIC_ERROR);
      return;
    }
    const problem = passwordProblem(form.password, email);
    if (problem) {
      setError(problem);
      return;
    }
    if (form.password !== form.confirm) {
      setError(PASSWORD_MATCH_MESSAGE);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await auth.register({ email, code: form.code, name, password: form.password });
    } catch (failure) {
      setError(
        failure instanceof ApiError && typeof failure.detail === "string" && failure.status < 500
          ? failure.detail
          : UNAVAILABLE,
      );
      setForm((f) => ({ ...f, password: "", confirm: "" }));
    } finally {
      setBusy(false);
    }
  }

  const described = error ? "register-error" : undefined;
  return (
    <div className="lp-hero min-h-screen px-6 py-10 text-engine-text">
      <main className="mx-auto flex max-w-[520px] flex-col gap-8">
        <div className="flex items-center gap-3">
          <span className="inline-flex rounded-[12px] bg-white p-[5px]">
            <img src={mark} alt="" className="h-[34px] w-auto" />
          </span>
          <span className="ltr text-[18px] font-bold tracking-[0.06em]">COMPASS</span>
          <Link to="/" className="ms-auto text-[15px] text-engine-guard underline hover:text-white">
            חזרה לכניסה
          </Link>
        </div>
        <form
          aria-label="הרשמה ראשונה"
          onSubmit={submit}
          noValidate
          className="flex flex-col gap-[18px] rounded-[22px] border border-white/20 bg-white/[0.07] p-8 backdrop-blur-[18px] max-sm:p-6"
        >
          <div className="flex items-center gap-2.5">
            <span className="text-engine-tool">
              <Icon name="shield" size={22} />
            </span>
            <h1 className="text-[24px] font-bold text-white">הרשמה ראשונה</h1>
          </div>
          <p className="-mt-2 text-[14px] text-soft">
            ההרשמה פתוחה רק למי שקיבל/ה קוד הזמנה מהמנהל/ת. הסיסמה נשמרת מוצפנת, והשיחות
            שלך נגישות רק לך.
          </p>
          <Field
            label="מייל"
            id="register-email"
            type="email"
            ltr
            autoComplete="username"
            placeholder="name@company.co.il"
            value={form.email}
            onChange={(e) => set("email")(e.target.value)}
            describedBy={described}
          />
          <Field
            label="קוד הזמנה"
            id="register-code"
            ltr
            autoComplete="off"
            spellCheck={false}
            placeholder="XXXXX-XXXXX"
            inputMode="text"
            value={form.code}
            onChange={(e) => set("code")(formatCodeInput(e.target.value))}
            describedBy={described}
          />
          <Field
            label="השם שלך"
            id="register-name"
            autoComplete="name"
            maxLength={NAME_MAX}
            value={form.name}
            onChange={(e) => set("name")(e.target.value)}
            describedBy={described}
          />
          <Field
            label="סיסמה (10 עד 128 תווים)"
            id="register-password"
            type="password"
            autoComplete="new-password"
            value={form.password}
            onChange={(e) => set("password")(e.target.value)}
            describedBy={described}
          />
          <Field
            label="אימות סיסמה"
            id="register-confirm"
            type="password"
            autoComplete="new-password"
            value={form.confirm}
            onChange={(e) => set("confirm")(e.target.value)}
            describedBy={described}
          />
          {error ? (
            <p id="register-error" role="alert" className="text-[14px] font-medium text-chip-pending-bg">
              {error}
            </p>
          ) : null}
          <button
            type="submit"
            disabled={busy}
            className="inline-flex min-h-[54px] items-center justify-center gap-2.5 rounded-[12px] bg-royal text-[17px] font-semibold text-white hover:bg-royal-hover disabled:opacity-60"
          >
            {busy ? "נרשמים…" : "הרשמה"}
            <Icon name="arrowLeft" size={18} />
          </button>
        </form>
      </main>
    </div>
  );
}
