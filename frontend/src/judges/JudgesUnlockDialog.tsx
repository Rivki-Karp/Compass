import * as Dialog from "@radix-ui/react-dialog";
import { useState, type FormEvent } from "react";
import { ApiError } from "../api/client";
import { Button } from "../ui/Button";

export const JUDGES_WRONG = "הסיסמה שגויה";
const UNAVAILABLE = "לא ניתן לאמת כרגע. נסו שוב.";

/**
 * Judges mode for a logged-in user (COMPASS_JUDGES_UNLOCK): asks for the admin password once.
 * `unlock` sends it to the server, which unlocks this login only. The password lives in this
 * component's state while the dialog is open and nowhere else: it is cleared on every close and
 * on every answer. The error is always the same words (a 429 adds the server's own hint).
 * Focus is trapped and Esc closes (Radix).
 */
export function JudgesUnlockDialog({
  open,
  unlock,
  onCancel,
  onUnlocked,
}: {
  open: boolean;
  unlock: (password: string) => Promise<void>;
  onCancel: () => void;
  onUnlocked: () => void;
}) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);

  function reset() {
    setPassword("");
    setError(null);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!password) {
      setError(JUDGES_WRONG);
      return;
    }
    setChecking(true);
    setError(null);
    try {
      await unlock(password);
      reset();
      onUnlocked();
    } catch (failure) {
      setPassword("");
      if (failure instanceof ApiError && failure.status === 401) setError(JUDGES_WRONG);
      else if (
        failure instanceof ApiError &&
        failure.status === 429 &&
        typeof failure.detail === "string"
      ) {
        setError(failure.detail); // the same words, and a hint to wait
      } else setError(UNAVAILABLE);
    } finally {
      setChecking(false);
    }
  }

  return (
    <Dialog.Root
      open={open}
      onOpenChange={(next) => {
        if (!next) {
          reset();
          onCancel();
        }
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-navy/40" />
        <Dialog.Content
          dir="rtl"
          className="fixed top-1/2 left-1/2 z-50 w-[min(440px,calc(100vw-32px))] -translate-x-1/2 -translate-y-1/2 rounded-card border border-line bg-surface p-6"
        >
          <Dialog.Title className="text-[22px] font-bold text-navy">מצב שופטים</Dialog.Title>
          <Dialog.Description className="mt-1 text-[13px] text-muted">
            הזינו את סיסמת המנהל כדי לראות את חדר המנועים
          </Dialog.Description>
          <form onSubmit={submit} className="mt-5 flex flex-col gap-2" noValidate>
            <label htmlFor="judges-password" className="text-[13px] font-medium text-ink">
              סיסמת מנהל
            </label>
            <input
              id="judges-password"
              type="password"
              autoComplete="off"
              spellCheck={false}
              dir="ltr"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              aria-invalid={error ? true : undefined}
              aria-describedby={error ? "judges-error" : undefined}
              className="h-12 rounded-tile border border-line px-3 font-mono text-[15px]"
            />
            {error ? (
              <p id="judges-error" role="alert" className="text-[13px] text-down">
                {error}
              </p>
            ) : null}
            <div className="mt-3 flex gap-3">
              <Button type="submit" disabled={checking}>
                {checking ? "בודק…" : "פתיחה"}
              </Button>
              <Dialog.Close asChild>
                <Button variant="secondary">ביטול</Button>
              </Dialog.Close>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
