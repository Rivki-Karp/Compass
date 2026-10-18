import { useEffect, useRef, useState, type FormEvent } from "react";
import type { ChatMessage, ToolActivity, Turn } from "../state/session";
import { Button } from "../ui/Button";
import { Icon } from "../ui/icons";
import { NumberText } from "../ui/NumberText";

const STILL_WORKING_MS = 8000; // the rep flow can take ~30 s

/** Messages and the run indicator (brief §4.2, chat panel). */
export function ChatPanel({
  messages,
  turns,
  thinking,
  suggestions,
  failedText,
  onSend,
  limitReached = false,
  onNewSession,
}: {
  messages: ChatMessage[];
  turns: Turn[];
  thinking: boolean;
  suggestions: string[];
  failedText: string | null;
  onSend: (text: string) => void;
  /** The session safety limit was reached: a "new chat" button replaces the input. */
  limitReached?: boolean;
  onNewSession?: () => void;
}) {
  const [draft, setDraft] = useState("");
  const list = useRef<HTMLOListElement>(null);
  const newChat = useRef<HTMLButtonElement>(null);

  // The input the employee was typing in goes away: keep keyboard focus on the way forward.
  useEffect(() => {
    if (limitReached) newChat.current?.focus();
  }, [limitReached]);

  // Newest message in view: scroll the list itself, never the page (on wide screens the chat
  // is sticky and the page scroll belongs to the comparison column).
  useEffect(() => {
    const el = list.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages.length, thinking]);

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!draft.trim()) return;
    onSend(draft);
    setDraft("");
  }

  return (
    <section
      aria-label="שיחה"
      className="wide:sticky wide:top-[calc(var(--header-h)+24px)] wide:h-[calc(100dvh-var(--header-h)-48px)] wide:min-h-0 flex min-h-[560px] flex-[1_1_420px] flex-col rounded-card border border-line bg-surface"
    >
      <div className="flex items-center justify-between border-b border-line-soft px-5 py-3">
        <h2 className="text-[15px] font-semibold text-navy">שיחה</h2>
        <span className="inline-flex items-center gap-1 text-[12px] text-muted">
          <Icon name="shield" size={13} />
          שומר המספרים פעיל
        </span>
      </div>

      {/* Focusable, so keyboard users can scroll it (axe scrollable-region-focusable). */}
      <ol
        ref={list}
        tabIndex={0}
        aria-label="הודעות"
        className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto px-5 py-4"
        aria-live="polite"
      >
        {messages.length === 0 && !thinking ? (
          <li className="text-[13px] text-muted">
            ספרו לי על התפקיד והשכר שלכם, ואחשב איך שינוי ברכב ישפיע על הנטו.
          </li>
        ) : null}
        {messages.map((message) => (
          <MessageItem
            key={message.seq}
            message={message}
            tools={message.turn !== null ? (turns[message.turn]?.tools ?? []) : []}
          />
        ))}
        {thinking ? <Thinking /> : null}
      </ol>

      {failedText !== null ? (
        <div
          role="alert"
          className="mx-5 mb-3 flex items-center gap-3 rounded-tile border border-down bg-down-bg px-3 py-2 text-[13px] text-down"
        >
          <Icon name="alert" size={16} />
          <span className="flex-1">ההודעה לא נשלחה.</span>
          <Button variant="secondary" onClick={() => onSend(failedText)}>
            <Icon name="refresh" size={16} />
            נסו שוב
          </Button>
        </div>
      ) : null}

      {limitReached ? (
        <div className="flex border-t border-line-soft px-5 py-4">
          <Button ref={newChat} onClick={onNewSession} className="flex-1">
            <Icon name="refresh" size={16} />
            שיחה חדשה
          </Button>
        </div>
      ) : (
        <>
      {suggestions.length ? (
        <div className="flex flex-wrap gap-2 px-5 pb-3" aria-label="הצעות">
          {suggestions.map((text) => (
            <Button
              key={text}
              variant="suggestion"
              onClick={() => onSend(text)}
              title={text}
              className="max-w-full"
            >
              <span className="truncate">
                <NumberText text={text} />
              </span>
            </Button>
          ))}
        </div>
      ) : null}

      <form onSubmit={submit} className="flex gap-2 border-t border-line-soft px-5 py-4">
        <label htmlFor="chat-input" className="sr-only">
          הודעה
        </label>
        <input
          id="chat-input"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="כתבו הודעה…"
          autoComplete="off"
          maxLength={4000}
          className="h-12 min-w-0 flex-1 rounded-tile border border-line bg-surface px-4 text-[15px] placeholder:text-muted"
        />
        <button
          type="submit"
          aria-label="שליחה"
          disabled={!draft.trim()}
          className="inline-flex h-12 w-12 shrink-0 items-center justify-center rounded-tile bg-royal text-white hover:bg-navy disabled:opacity-50"
        >
          <Icon name="arrowLeft" size={20} />
        </button>
      </form>
        </>
      )}
    </section>
  );
}

function MessageItem({ message, tools }: { message: ChatMessage; tools: ToolActivity[] }) {
  if (message.role === "employee") {
    return (
      <li className="flex justify-end">
        <p className="max-w-[85%] rounded-[14px] rounded-ee-[4px] bg-navy px-4 py-2.5 whitespace-pre-wrap text-white">
          <NumberText text={message.text} />
        </p>
      </li>
    );
  }
  if (message.role === "rep") {
    return (
      <li className="flex flex-col items-start">
        <div
          role="note"
          aria-label="הערת הנציג"
          className="max-w-[85%] rounded-[14px] rounded-es-[4px] border border-chip-rep bg-chip-rep-bg px-4 py-2.5 text-ink"
        >
          <p className="text-[13px] font-semibold text-chip-rep">הערת הנציג</p>
          <p className="whitespace-pre-wrap">
            <NumberText text={message.text} />
          </p>
        </div>
      </li>
    );
  }
  return (
    <li className="flex flex-col items-start gap-1.5">
      <p className="max-w-[85%] rounded-[14px] rounded-es-[4px] border border-bubble-border bg-ground px-4 py-2.5 whitespace-pre-wrap text-ink">
        <NumberText text={message.text} />
      </p>
      {tools.length ? <ToolRow tools={tools} /> : null}
    </li>
  );
}

/** The tools a turn used: mono LTR chips, ✓ or ✕ (brief §4.2). */
function ToolRow({ tools }: { tools: ToolActivity[] }) {
  return (
    <ul className="flex flex-wrap gap-1.5" aria-label="כלים שהופעלו">
      {tools.map((tool) => (
        <li
          key={tool.toolUseId}
          className="ltr rounded-chip bg-tool-chip-bg px-2 py-0.5 font-mono text-[12px] text-steel"
        >
          {tool.name}{" "}
          {tool.ok === false ? (
            <span className="text-down" aria-label="נכשל">
              ✕
            </span>
          ) : tool.ok ? (
            <span aria-label="הצליח">✓</span>
          ) : (
            <span aria-label="רץ">…</span>
          )}
        </li>
      ))}
    </ul>
  );
}

/** Three dots and "מחשב…"; after 8 s also "עדיין עובד על זה". */
export function Thinking() {
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => setSlow(true), STILL_WORKING_MS);
    return () => clearTimeout(timer);
  }, []);
  return (
    <li className="flex items-start" role="status">
      <p className="flex items-center gap-2 rounded-[14px] rounded-es-[4px] border border-bubble-border bg-ground px-4 py-2.5 text-muted">
        <span className="motion-dots inline-flex gap-1" aria-hidden="true">
          <span className="h-1.5 w-1.5 rounded-full bg-steel" />
          <span className="h-1.5 w-1.5 rounded-full bg-steel" />
          <span className="h-1.5 w-1.5 rounded-full bg-steel" />
        </span>
        מחשב…{slow ? <span> עדיין עובד על זה</span> : null}
      </p>
    </li>
  );
}
