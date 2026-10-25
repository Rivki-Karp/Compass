import * as Dialog from "@radix-ui/react-dialog";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { ApiError, api, type AdminUser, type InviteCreated } from "../api/client";
import { useAuth } from "../auth/context";
import type { Role } from "../auth/authStore";
import { AccountBar } from "../home/AccountBar";
import { Button } from "../ui/Button";
import { Header } from "../ui/Header";

const ROLE_LABEL: Record<Role, string> = { employee: "עובד/ת", rep: "נציג/ה", admin: "מנהל/ת" };
const STATUS_LABEL = { active: "פעיל", disabled: "מושבת" } as const;
const ROLES: Role[] = ["employee", "rep", "admin"];

const DEMO_PROTECTED = "חשבון הדגמה משותף. אי אפשר למחוק אותו, להשבית אותו או לשנות את התפקיד שלו";

function day(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? "—"
    : `${d.getDate()}/${d.getMonth() + 1}/${d.getFullYear()} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

function messageOf(failure: unknown): string {
  return failure instanceof ApiError && typeof failure.detail === "string"
    ? failure.detail
    : "הפעולה נכשלה. נסו שוב.";
}

/** The code, once: a dialog with a copy button. Closing it is the end of the code's life. */
function InviteCodeDialog({ invite, onClose }: { invite: InviteCreated | null; onClose: () => void }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    if (!invite) return;
    try {
      await navigator.clipboard.writeText(invite.code);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }
  return (
    <Dialog.Root
      open={invite !== null}
      onOpenChange={(open) => {
        if (!open) {
          setCopied(false);
          onClose();
        }
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-navy/40" />
        <Dialog.Content
          dir="rtl"
          className="fixed top-1/2 left-1/2 z-50 w-[min(460px,calc(100vw-32px))] -translate-x-1/2 -translate-y-1/2 rounded-card border border-line bg-surface p-6"
        >
          <Dialog.Title className="text-[22px] font-bold text-navy">קוד הזמנה</Dialog.Title>
          <Dialog.Description className="mt-1 text-[14px] text-muted">
            הקוד יוצג פעם אחת בלבד. מסרו אותו ל-<bdi>{invite?.email}</bdi> ({invite ? ROLE_LABEL[invite.role] : ""}
            ). הוא תקף עד <bdi>{invite ? day(invite.expires_at) : ""}</bdi> ויעבוד פעם אחת.
          </Dialog.Description>
          <p
            aria-label="הקוד"
            className="ltr mt-4 rounded-tile border border-line bg-ground px-4 py-3 text-center font-mono text-[28px] font-medium tracking-[0.12em] text-navy select-all"
          >
            {invite?.code}
          </p>
          <div className="mt-5 flex items-center gap-3">
            <Button onClick={() => void copy()}>{copied ? "הועתק" : "העתקה"}</Button>
            <Dialog.Close asChild>
              <Button variant="secondary">סגירה</Button>
            </Dialog.Close>
            <span role="status" className="text-[13px] text-up">
              {copied ? "הקוד הועתק ללוח" : ""}
            </span>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

/**
 * `/admin` (role admin): who may use Compass. The users with their role and status, an invite
 * form, and the code once. The admin manages access only: nothing here (or reachable from here)
 * shows a conversation, a profile or a payslip.
 */
export function AdminPage() {
  const auth = useAuth();
  const [users, setUsers] = useState<AdminUser[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [invite, setInvite] = useState<InviteCreated | null>(null);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>("employee");
  const [busy, setBusy] = useState(false);
  const [deleting, setDeleting] = useState<AdminUser | null>(null);
  const [notice, setNotice] = useState("");

  const load = useCallback(() => {
    api
      .adminUsers()
      .then(setUsers)
      .catch((failure) => setError(messageOf(failure)));
  }, []);
  useEffect(load, [load]);

  async function createInvite(event: FormEvent) {
    event.preventDefault();
    if (!email.trim()) {
      setError("צריך להזין כתובת מייל.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      setInvite(await api.invite(email.trim(), role));
      setEmail("");
    } catch (failure) {
      setError(messageOf(failure));
    } finally {
      setBusy(false);
    }
  }

  async function change(user: AdminUser, change: { role?: Role; status?: "active" | "disabled" }) {
    setError(null);
    try {
      const updated = await api.patchUser(user.id, change);
      setUsers((list) => list?.map((u) => (u.id === updated.id ? updated : u)) ?? list);
      setNotice("השינוי נשמר.");
    } catch (failure) {
      setError(messageOf(failure));
      load(); // show what is true
    }
  }

  async function remove() {
    if (!deleting) return;
    setError(null);
    try {
      await api.deleteUser(deleting.id);
      setUsers((list) => list?.filter((u) => u.id !== deleting.id) ?? list);
      setNotice("המשתמש נמחק, יחד עם כל השיחות שלו.");
    } catch (failure) {
      setError(messageOf(failure));
    } finally {
      setDeleting(null);
    }
  }

  const me = auth.user;
  return (
    <div className="min-h-screen bg-ground">
      <Header variant="account" heading={false}>
        {me ? <AccountBar user={me} onLogout={() => void auth.logout()} /> : null}
      </Header>
      <main className="mx-auto flex max-w-[1100px] flex-col gap-6 px-8 py-6 max-sm:px-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h1 className="text-[26px] font-bold text-navy">ניהול משתמשים</h1>
          <Link to="/" className="text-[14px] text-royal underline">
            חזרה לשיחות
          </Link>
        </div>
        <p className="text-[14px] text-muted">
          כאן מנהלים גישה בלבד: מי יכול להיכנס ובאיזה תפקיד. השיחות, הפרופילים והתלושים של העובדים
          אינם נגישים למנהל.
        </p>
        <p role="status" className="sr-only">
          {notice}
        </p>
        {error ? (
          <p role="alert" className="rounded-tile border border-down bg-down-bg px-4 py-3 text-down">
            {error}
          </p>
        ) : null}

        <section aria-labelledby="invite-title" className="rounded-card border border-line bg-surface p-5">
          <h2 id="invite-title" className="text-[18px] font-semibold text-navy">
            הזמנה חדשה
          </h2>
          <form onSubmit={createInvite} noValidate className="mt-3 flex flex-wrap items-end gap-3">
            <label htmlFor="invite-email" className="flex min-w-[240px] flex-1 flex-col gap-1.5 text-[13px] font-medium">
              מייל
              <input
                id="invite-email"
                type="email"
                dir="ltr"
                autoComplete="off"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="h-12 rounded-tile border border-line px-3 text-[15px] text-start"
              />
            </label>
            <label htmlFor="invite-role" className="flex flex-col gap-1.5 text-[13px] font-medium">
              תפקיד
              <select
                id="invite-role"
                value={role}
                onChange={(e) => setRole(e.target.value as Role)}
                className="h-12 rounded-tile border border-line bg-surface px-3 text-[15px]"
              >
                {ROLES.filter((r) => !(auth.user?.demo && r === "admin")).map((r) => (
                  <option key={r} value={r}>
                    {ROLE_LABEL[r]}
                  </option>
                ))}
              </select>
            </label>
            <Button type="submit" disabled={busy} className="h-12">
              {busy ? "יוצר…" : "יצירת קוד הזמנה"}
            </Button>
          </form>
          <p className="mt-2 text-[12px] text-muted">
            אין איפוס סיסמה: מי ששכח/ה סיסמה נמחק/ת ומוזמן/ת שוב.
          </p>
        </section>

        <section aria-labelledby="users-title" className="overflow-x-auto rounded-card border border-line bg-surface">
          <table className="w-full min-w-[760px] border-collapse text-start text-[14px]">
            <caption id="users-title" className="px-5 pt-4 pb-2 text-start text-[18px] font-semibold text-navy">
              משתמשים
            </caption>
            <thead>
              <tr className="border-b border-line text-[12px] text-muted">
                {["שם", "מייל", "תפקיד", "סטטוס", "נוצר", "כניסה אחרונה", ""].map((h, i) => (
                  <th key={i} scope="col" className="px-5 py-2 text-start font-medium">
                    {h || <span className="sr-only">פעולות</span>}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(users ?? []).map((user) => {
                return (
                  <tr key={user.id} className="border-b border-line-soft last:border-0">
                    <td className="px-5 py-3 font-medium">
                      <bdi>{user.name}</bdi>
                      {user.demo ? (
                        <span className="ms-2 rounded-chip border border-line bg-ground px-2 py-0.5 text-[12px] font-medium text-steel">
                          הדגמה
                        </span>
                      ) : null}
                    </td>
                    <td className="px-5 py-3">
                      <bdi dir="ltr">{user.email}</bdi>
                    </td>
                    <td className="px-5 py-3">
                      <select
                        aria-label={`תפקיד של ${user.name}`}
                        value={user.role}
                        disabled={user.demo === true}
                        title={user.demo ? DEMO_PROTECTED : undefined}
                        onChange={(e) => void change(user, { role: e.target.value as Role })}
                        className="h-11 rounded-control border border-line bg-surface px-2"
                      >
                        {ROLES.map((r) => (
                          <option key={r} value={r}>
                            {ROLE_LABEL[r]}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="px-5 py-3">
                      <button
                        type="button"
                        aria-pressed={user.status === "active"}
                        disabled={user.demo === true}
                        title={user.demo ? DEMO_PROTECTED : undefined}
                        aria-label={`${user.status === "active" ? "השבתת" : "הפעלת"} ${user.name}`}
                        onClick={() =>
                          void change(user, { status: user.status === "active" ? "disabled" : "active" })
                        }
                        className={`inline-flex min-h-11 items-center rounded-chip border px-3 text-[13px] font-medium ${
                          user.status === "active"
                            ? "border-up bg-up-bg text-up-ink"
                            : "border-chip-pending-border bg-chip-pending-bg text-chip-pending"
                        }`}
                      >
                        {STATUS_LABEL[user.status]}
                      </button>
                    </td>
                    <td className="px-5 py-3 whitespace-nowrap">{day(user.created_at)}</td>
                    <td className="px-5 py-3 whitespace-nowrap">{day(user.last_login_at)}</td>
                    <td className="px-5 py-3">
                      <Button
                        variant="secondary"
                        aria-label={`מחיקת ${user.name}`}
                        disabled={user.demo === true}
                        title={user.demo ? DEMO_PROTECTED : undefined}
                        onClick={() => setDeleting(user)}
                      >
                        מחיקה
                      </Button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {users === null && !error ? <p className="px-5 py-4 text-muted">טוען…</p> : null}
        </section>
      </main>

      <InviteCodeDialog invite={invite} onClose={() => setInvite(null)} />

      <Dialog.Root open={deleting !== null} onOpenChange={(open) => !open && setDeleting(null)}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-40 bg-navy/40" />
          <Dialog.Content
            dir="rtl"
            role="alertdialog"
            className="fixed top-1/2 left-1/2 z-50 w-[min(460px,calc(100vw-32px))] -translate-x-1/2 -translate-y-1/2 rounded-card border border-line bg-surface p-6"
          >
            <Dialog.Title className="text-[20px] font-bold text-navy">למחוק את המשתמש?</Dialog.Title>
            <Dialog.Description className="mt-2 text-[14px] text-muted">
              <bdi>{deleting?.name}</bdi> יימחק/תימחק יחד עם כל השיחות שלו/ה, ואי אפשר לשחזר. כדי
              שיחזרו להשתמש במערכת, תצטרכו להזמין אותו/ה מחדש.
            </Dialog.Description>
            <div className="mt-5 flex gap-3">
              <Button
                onClick={() => void remove()}
                className="border-down bg-down hover:bg-down hover:opacity-90"
              >
                מחיקה
              </Button>
              <Dialog.Close asChild>
                <Button variant="secondary">ביטול</Button>
              </Dialog.Close>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}
