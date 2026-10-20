import { useEffect, useRef, useState } from "react";
import { ApiError, confirmPayslip, uploadPayslip } from "../api/client";
import type { PendingPayslip } from "../state/session";
import { Button } from "../ui/Button";
import { Icon } from "../ui/icons";
import { PayslipCard } from "./PayslipCard";
import { precheck, PRIVACY_NOTICE, type PayslipLimits } from "./payslip";

type Phase =
  | { kind: "idle" }
  | { kind: "notice" }
  | { kind: "uploading" }
  | { kind: "extracting" }
  | { kind: "error"; message: string; retry: File | null }
  | { kind: "confirming" }
  | { kind: "saved" };

const ACK_KEY = "compass.payslip.ack."; // + session id: the notice, once per session

function acknowledged(sessionId: string): boolean {
  try {
    return sessionStorage.getItem(ACK_KEY + sessionId) === "1";
  } catch {
    return false;
  }
}

function acknowledge(sessionId: string): void {
  try {
    sessionStorage.setItem(ACK_KEY + sessionId, "1");
  } catch {
    // no storage (a private window): the notice simply shows again next time
  }
}

function messageOf(error: unknown): string {
  if (error instanceof ApiError && error.errors[0]?.message) return error.errors[0].message;
  return "לא הצלחנו לשלוח את התלוש. בדקו את החיבור ונסו שוב.";
}

/**
 * The payslip upload in the chat (COMPASS_PAYSLIP=1, as /api/health says; never a frontend
 * flag): the attach button, the privacy notice once per session, the states (uploading,
 * reading, error with retry) and the confirmation card for the pending candidate. `open` starts
 * the same upload from elsewhere (the offer card in the empty state); null while one is running.
 */
export function usePayslip({
  sessionId,
  limits,
  pending,
}: {
  sessionId: string | null;
  limits: PayslipLimits | undefined;
  pending: PendingPayslip | null;
}) {
  const [phase, setPhase] = useState<Phase>({ kind: "idle" });
  const picker = useRef<HTMLInputElement>(null);

  useEffect(() => setPhase({ kind: "idle" }), [sessionId]);

  if (!limits || !sessionId) return { attach: null, tray: null, open: null };
  const id = sessionId;
  const busy = ["uploading", "extracting", "confirming"].includes(phase.kind);

  function open() {
    if (acknowledged(id)) picker.current?.click();
    else setPhase({ kind: "notice" });
  }

  async function send(file: File) {
    const problem = precheck(file, limits as PayslipLimits);
    if (problem) {
      setPhase({ kind: "error", message: problem, retry: null });
      return;
    }
    setPhase({ kind: "uploading" });
    try {
      await uploadPayslip(id, file, () => setPhase({ kind: "extracting" }));
      setPhase({ kind: "idle" }); // the card comes from the session's payslip_extracted event
    } catch (error) {
      const retry = error instanceof ApiError && error.status >= 500 ? file : null;
      setPhase({ kind: "error", message: messageOf(error), retry });
    }
  }

  async function confirm(fields: Record<string, string>) {
    setPhase({ kind: "confirming" });
    try {
      await confirmPayslip(id, fields);
      setPhase({ kind: "saved" });
    } catch (error) {
      setPhase({ kind: "error", message: messageOf(error), retry: null });
    }
  }

  const attach = (
    <>
      <button
        type="button"
        aria-label="צירוף תלוש שכר"
        title="צירוף תלוש שכר"
        onClick={open}
        disabled={busy}
        className="inline-flex h-12 w-12 shrink-0 items-center justify-center rounded-tile border border-line bg-surface text-steel hover:bg-ground disabled:opacity-50"
      >
        <Icon name="paperclip" size={20} />
      </button>
      <input
        ref={picker}
        type="file"
        accept={limits.types.join(",")}
        className="sr-only"
        tabIndex={-1}
        aria-hidden="true"
        onChange={(e) => {
          const file = e.target.files?.[0];
          e.target.value = ""; // the same file can be picked again
          if (file) void send(file);
        }}
        data-testid="payslip-input"
      />
    </>
  );

  let tray = null;
  if (phase.kind === "notice") {
    tray = (
      <div role="dialog" aria-labelledby="payslip-notice-title" className="mx-5 mb-3 rounded-tile border border-line bg-ground p-4">
        <p id="payslip-notice-title" className="font-semibold text-navy">
          לפני שמעלים תלוש
        </p>
        <p className="mt-1 text-[14px] text-ink">{PRIVACY_NOTICE}</p>
        <div className="mt-3 flex flex-wrap gap-2">
          <Button
            onClick={() => {
              acknowledge(id);
              setPhase({ kind: "idle" });
              picker.current?.click();
            }}
          >
            הבנתי, לבחירת קובץ
          </Button>
          <Button variant="secondary" onClick={() => setPhase({ kind: "idle" })}>
            ביטול
          </Button>
        </div>
      </div>
    );
  } else if (phase.kind === "uploading" || phase.kind === "extracting") {
    tray = (
      <p role="status" className="mx-5 mb-3 flex items-center gap-2 text-[14px] text-muted">
        <Icon name="clock" size={16} />
        {phase.kind === "uploading" ? "מעלה את התלוש…" : "קורא את נתוני השכר מהתלוש…"}
      </p>
    );
  } else if (phase.kind === "error") {
    tray = (
      <div role="alert" className="mx-5 mb-3 flex flex-wrap items-center gap-3 rounded-tile border border-down bg-down-bg px-3 py-2 text-[13px] text-down">
        <Icon name="alert" size={16} />
        <span className="flex-1">{phase.message}</span>
        {phase.retry ? (
          <Button variant="secondary" onClick={() => void send(phase.retry as File)}>
            <Icon name="refresh" size={16} />
            נסו שוב
          </Button>
        ) : (
          <Button variant="secondary" onClick={open}>
            בחירת קובץ אחר
          </Button>
        )}
      </div>
    );
  } else if (pending) {
    tray = (
      <PayslipCard
        key={pending.seq}
        pending={pending}
        busy={phase.kind === "confirming"}
        onConfirm={(fields) => void confirm(fields)}
      />
    );
  } else if (phase.kind === "saved") {
    tray = (
      <p role="status" className="mx-5 mb-3 flex items-center gap-2 text-[14px] text-chip-payslip">
        <Icon name="check" size={16} />
        הנתונים נשמרו לפי התלוש.
      </p>
    );
  }
  return { attach, tray, open: busy ? null : open };
}
