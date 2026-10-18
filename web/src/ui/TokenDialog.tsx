import * as Dialog from "@radix-ui/react-dialog";
import { useState, type FormEvent } from "react";
import { TOKEN_NOT_CONFIGURED, type TokenCheck } from "../lib/tokenCheck";
import { Button } from "./Button";

/**
 * Asks for a token once (admin: judges mode; rep: the inbox). `verify` checks it with the
 * server before it is kept; the caller stores it in sessionStorage only. `notConfigured`: the
 * server says it has no such token, so the dialog says so instead of asking.
 */
export function TokenDialog({
  open,
  title,
  description,
  label,
  verify,
  notConfigured = false,
  onCancel,
  onAccept,
}: {
  open: boolean;
  title: string;
  description: string;
  label: string;
  verify: (token: string) => Promise<TokenCheck>;
  notConfigured?: boolean;
  onCancel: () => void;
  onAccept: (token: string) => void;
}) {
  const [token, setToken] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const value = token.trim();
    if (!value) {
      setError("צריך להזין טוקן.");
      return;
    }
    setChecking(true);
    const result = await verify(value).catch(() => "unavailable" as const);
    setChecking(false);
    if (result === "ok") {
      setToken("");
      setError(null);
      onAccept(value);
    } else {
      setError(
        result === "wrong"
          ? "הטוקן שגוי."
          : result === "not_configured"
            ? TOKEN_NOT_CONFIGURED
            : "לא ניתן לאמת כרגע. נסו שוב.",
      );
    }
  }
  const shown = notConfigured ? TOKEN_NOT_CONFIGURED : error;

  return (
    <Dialog.Root
      open={open}
      onOpenChange={(next) => {
        if (!next) {
          setToken("");
          setError(null);
          onCancel();
        }
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-navy/40" />
        <Dialog.Content
          dir="rtl"
          className="fixed top-1/2 left-1/2 w-[min(440px,calc(100vw-32px))] -translate-x-1/2 -translate-y-1/2 rounded-card border border-line bg-surface p-6"
        >
          <Dialog.Title className="text-[22px] font-bold text-navy">{title}</Dialog.Title>
          <Dialog.Description className="mt-1 text-[13px] text-muted">
            {description}
          </Dialog.Description>
          <form onSubmit={submit} className="mt-5 flex flex-col gap-2" noValidate>
            <label htmlFor="token-input" className="text-[13px] font-medium text-ink">
              {label}
            </label>
            <input
              id="token-input"
              type="password"
              autoComplete="off"
              spellCheck={false}
              dir="ltr"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              disabled={notConfigured}
              aria-invalid={shown ? true : undefined}
              aria-describedby={shown ? "token-error" : undefined}
              className="h-12 rounded-tile border border-line px-3 font-mono text-[15px]"
            />
            {shown ? (
              <p id="token-error" role="alert" className="text-[13px] text-down">
                {shown}
              </p>
            ) : null}
            <div className="mt-3 flex gap-3">
              <Button type="submit" disabled={checking || notConfigured}>
                {checking ? "בודק…" : "אישור"}
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
