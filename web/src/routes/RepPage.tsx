import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { clearToken, getToken, setToken } from "../lib/tokens";
import { useHealth } from "../lib/useHealth";
import { selectedTicket } from "../rep/inbox";
import { TicketDetail } from "../rep/TicketDetail";
import { TicketList } from "../rep/TicketList";
import { useRepInbox } from "../rep/useRepInbox";
import { Button } from "../ui/Button";
import { ConnectionPill, DemoBadge, Header } from "../ui/Header";
import { TOKEN_NOT_CONFIGURED, tokenCheck, type TokenCheck } from "../lib/tokenCheck";
import { TokenDialog } from "../ui/TokenDialog";

/** Re-render every `ms`, for the tickets' ages. */
function useNow(ms: number): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), ms);
    return () => clearInterval(timer);
  }, [ms]);
  return now;
}

async function verifyRep(token: string): Promise<TokenCheck> {
  const response = await fetch("/api/tickets?status=open", {
    headers: { Authorization: `Bearer ${token}` },
  });
  return tokenCheck(response.status);
}

/** The representative screen (brief §4.6): the live inbox and the answer form. */
export function RepPage() {
  const health = useHealth();
  const [token, setRepToken] = useState<string | null>(() => getToken("rep"));
  const [asking, setAsking] = useState(token === null);
  const [notice, setNotice] = useState("");
  const inbox = useRepInbox(token);
  const { state, select: selectTicket } = inbox;
  const now = useNow(30_000);
  const [params, setParams] = useSearchParams();
  const fromUrl = useRef(params.get("ticket"));

  function forgetToken() {
    clearToken("rep");
    setRepToken(null);
    setAsking(true);
  }

  // A stored token the server no longer accepts: ask again.
  useEffect(() => {
    if (token && inbox.connection === "unauthorized") {
      clearToken("rep");
      setRepToken(null);
      setAsking(true);
    }
  }, [token, inbox.connection]);

  // ?ticket=… (a row opened in a new tab): select it once the list is in.
  useEffect(() => {
    if (!state.loaded || fromUrl.current === null) return;
    selectTicket(fromUrl.current);
    fromUrl.current = null;
  }, [state.loaded, selectTicket]);

  function select(ticketId: string) {
    selectTicket(ticketId);
    setNotice("");
    setParams({ ticket: ticketId }, { replace: true });
  }

  function answered(ticketId: string, stillOpen: boolean) {
    if (stillOpen) {
      // a partial answer: the ticket stays, with its other fields pending
      setNotice("התשובה נשלחה. השדות שלא מולאו ממתינים לתשובה.");
      return;
    }
    inbox.answered(ticketId);
    setParams({}, { replace: true });
    setNotice("התשובה נשלחה. החישוב אצל העובד/ת מתעדכן.");
  }

  const ticket = selectedTicket(state);
  return (
    <div className="min-h-screen bg-ground">
      <Header variant="rep">
        {health?.llm === "scripted" ? <DemoBadge /> : null}
        {token && inbox.connection === "open" ? (
          <span className="text-[13px] text-mist">מחובר כנציג · טוקן נשמר לסשן הזה בלבד</span>
        ) : token ? (
          <ConnectionPill status={inbox.connection} />
        ) : null}
      </Header>
      <TokenDialog
        open={asking}
        title="מסך נציג"
        description="הזינו את טוקן הנציג כדי לראות את הטיקטים הפתוחים ולענות עליהם. הטוקן נשמר לסשן הזה בלבד."
        label="טוקן נציג"
        verify={verifyRep}
        notConfigured={health?.auth?.rep === false}
        onCancel={() => setAsking(false)}
        onAccept={(value) => {
          setToken("rep", value);
          setRepToken(value);
          setAsking(false);
        }}
      />

      <p aria-live="polite" className="sr-only">
        {notice}
      </p>

      {token ? (
        <main className="flex flex-wrap items-start gap-6 px-8 py-6 max-sm:px-4">
          <TicketList
            tickets={state.tickets}
            loaded={state.loaded}
            selectedId={state.selectedId}
            now={now}
            onSelect={select}
          />
          {ticket ? (
            <TicketDetail
              ticket={ticket}
              token={token}
              onAnswered={answered}
              onReauth={forgetToken}
            />
          ) : (
            <div className="flex min-w-0 flex-[999_1_560px] flex-col items-center gap-2 rounded-card border border-line bg-surface px-6 py-16 text-center text-muted">
              {notice ? <p className="font-medium text-up">{notice}</p> : null}
              <p>
                {!state.loaded
                  ? "טוען…"
                  : state.tickets.length
                    ? "בחרו טיקט מהרשימה."
                    : "אין כרגע שאלות שמחכות לתשובה."}
              </p>
            </div>
          )}
        </main>
      ) : (
        <main className="px-8 py-6 max-sm:px-4">
          <div className="mx-auto flex max-w-[480px] flex-col items-center gap-4 rounded-card border border-line bg-surface px-6 py-12 text-center">
            {health?.auth?.rep === false ? (
              <p role="alert" className="font-medium text-down">
                {TOKEN_NOT_CONFIGURED}
              </p>
            ) : (
              <>
                <p className="text-ink">כדי לראות את הטיקטים צריך טוקן נציג.</p>
                <Button onClick={() => setAsking(true)}>הזנת טוקן</Button>
              </>
            )}
          </div>
        </main>
      )}
    </div>
  );
}
