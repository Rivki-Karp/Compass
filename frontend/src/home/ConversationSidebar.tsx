import * as Dialog from "@radix-ui/react-dialog";
import { useState } from "react";
import { Link } from "react-router-dom";
import type { ConversationEntry } from "../api/client";
import { formatSigned } from "../lib/format";
import { whenLabel } from "./when";
import { Button } from "../ui/Button";
import { Icon } from "../ui/icons";

/** The chip under a title: the diff with its state, or the state alone. */
function Chip({ entry }: { entry: ConversationEntry }) {
  const diff = entry.diff;
  const sign = diff === null ? null : diff > 0 ? "text-up" : diff < 0 ? "text-down" : "text-muted";
  return (
    <span className="flex flex-wrap items-center gap-x-1.5 font-semibold">
      {diff !== null ? (
        <span className={sign ?? ""}>
          <bdi>{formatSigned(diff)}</bdi> ₪
        </span>
      ) : null}
      {entry.status === "final" ? (
        <span className="text-up-ink">{diff !== null ? "· סופי" : "סופי"}</span>
      ) : entry.status === "pending" ? (
        <span className="text-chip-pending">{diff !== null ? "· ממתינה לנציג" : "ממתינה לנציג"}</span>
      ) : entry.status === "partial" ? (
        <span className="text-chip-pending">{diff !== null ? "· חלקי" : "חלקי"}</span>
      ) : null}
    </span>
  );
}

/**
 * The list of the user's conversations, newest first: "שיחה חדשה", then each one (title, when, a
 * diff chip and a status chip), with a delete button behind a confirmation. Opening one is a link
 * to /c/:id, which resumes it exactly where it stopped.
 */
export function ConversationSidebar({
  items,
  failed,
  currentId,
  currentEmpty = false,
  onDelete,
  onNavigate,
}: {
  items: ConversationEntry[] | null;
  failed: boolean;
  currentId: string;
  /** The open conversation is empty (it is not in the list): "שיחה חדשה" stays in it. */
  currentEmpty?: boolean;
  onDelete: (id: string) => Promise<void>;
  /** Called when a link is followed (the phone drawer closes). */
  onNavigate?: () => void;
}) {
  const [deleting, setDeleting] = useState<ConversationEntry | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function confirmDelete() {
    if (!deleting) return;
    setBusy(true);
    setError(null);
    try {
      await onDelete(deleting.id);
      setDeleting(null);
    } catch {
      setError("המחיקה נכשלה. נסו שוב.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <aside
      aria-label="השיחות שלי"
      className="flex min-w-0 flex-col gap-3.5 rounded-card border border-line bg-surface p-[18px]"
    >
      <Link
        to="/new"
        onClick={(event) => {
          if (currentEmpty) event.preventDefault(); // already in a new conversation
          onNavigate?.();
        }}
        className="inline-flex min-h-12 items-center justify-center gap-2 rounded-tile bg-royal text-[15px] font-semibold text-white hover:bg-royal-hover"
      >
        <svg
          aria-hidden="true"
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
        >
          <path d="M12 5v14M5 12h14" />
        </svg>
        שיחה חדשה
      </Link>
      <h2 className="px-1 pt-1.5 text-[13px] font-semibold text-muted">השיחות שלי</h2>
      {failed && items === null ? (
        <p role="alert" className="px-1 text-[13px] text-down">
          לא הצלחנו לטעון את השיחות.
        </p>
      ) : null}
      <ul className="flex flex-col gap-1">
        {(items ?? []).map((entry) => {
          const current = entry.id === currentId;
          return (
            <li
              key={entry.id}
              className={`group flex items-stretch rounded-tile ${current ? "bg-chip-employee-bg" : "hover:bg-provenance-bg"}`}
            >
              <Link
                to={`/c/${entry.id}`}
                onClick={onNavigate}
                aria-current={current ? "page" : undefined}
                className="flex min-w-0 flex-1 flex-col gap-1 rounded-tile p-3 text-ink no-underline"
              >
                <span className="text-[14px] font-semibold">
                  <bdi>{entry.title}</bdi>
                </span>
                <span className="flex justify-between gap-2 text-[12px] text-muted">
                  <span>{whenLabel(entry.updated_at)}</span>
                  <Chip entry={entry} />
                </span>
              </Link>
              <button
                type="button"
                aria-label={`מחיקת שיחה: ${entry.title}`}
                onClick={() => {
                  setError(null);
                  setDeleting(entry);
                }}
                className="m-1 inline-flex h-11 w-11 shrink-0 items-center justify-center self-center rounded-control text-muted hover:bg-down-bg hover:text-down"
              >
                <Icon name="x" size={16} />
              </button>
            </li>
          );
        })}
      </ul>
      <p className="mt-auto text-[12px] leading-normal text-muted">רק את/ה רואה את השיחות האלה.</p>

      <Dialog.Root open={deleting !== null} onOpenChange={(open) => !open && setDeleting(null)}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-40 bg-navy/40" />
          <Dialog.Content
            dir="rtl"
            role="alertdialog"
            className="fixed top-1/2 left-1/2 z-50 w-[min(440px,calc(100vw-32px))] -translate-x-1/2 -translate-y-1/2 rounded-card border border-line bg-surface p-6"
          >
            <Dialog.Title className="text-[20px] font-bold text-navy">למחוק את השיחה?</Dialog.Title>
            <Dialog.Description className="mt-2 text-[14px] text-muted">
              {deleting ? <bdi>{deleting.title}</bdi> : null} תימחק לצמיתות, יחד עם כל מה שנאמר בה.
              אי אפשר לשחזר אותה.
            </Dialog.Description>
            {error ? (
              <p role="alert" className="mt-3 text-[13px] text-down">
                {error}
              </p>
            ) : null}
            <div className="mt-5 flex gap-3">
              <Button
                onClick={() => void confirmDelete()}
                disabled={busy}
                className="border-down bg-down hover:bg-down hover:opacity-90"
              >
                {busy ? "מוחק…" : "מחיקה"}
              </Button>
              <Dialog.Close asChild>
                <Button variant="secondary">ביטול</Button>
              </Dialog.Close>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </aside>
  );
}
