import { useEffect, useMemo, useState } from "react";
import { ChatPanel } from "../employee/ChatPanel";
import { EmptyComparison } from "../employee/EmptyComparison";
import { HeroAnnouncement, HeroCard } from "../employee/HeroCard";
import { InputsCard } from "../employee/InputsCard";
import { demoSuggestions, GENERAL_SUGGESTIONS } from "../employee/suggestions";
import { clearToken, getToken, setToken } from "../lib/tokens";
import { useHealth } from "../lib/useHealth";
import { useSession } from "../state/useSession";
import { ConnectionPill, DemoBadge, Header, JudgesToggle } from "../ui/Header";
import { TokenDialog } from "../ui/TokenDialog";
import { Waterfall } from "../waterfall/Waterfall";

/** The employee screen (brief §4.2): chat on the right, the comparison on the left. */
export function EmployeePage() {
  const health = useHealth();
  const [judges, setJudges] = useState(false);
  const [asking, setAsking] = useState(false);
  const [adminToken, setAdminToken] = useState<string | null>(() => getToken("admin"));
  const session = useSession(judges ? adminToken : null);
  const { state } = session;

  // A stored admin token the server no longer accepts: forget it, leave judges mode.
  useEffect(() => {
    if (session.connection === "unauthorized" && judges) {
      clearToken("admin");
      setAdminToken(null);
      setJudges(false);
    }
  }, [session.connection, judges]);

  const suggestions = useMemo(() => {
    if (state.thinking || session.sending) return [];
    const sent = state.messages.filter((m) => m.role === "employee").map((m) => m.text);
    if (health?.llm === "scripted") return demoSuggestions(health.demo_scripts ?? [], sent);
    return sent.length ? [] : GENERAL_SUGGESTIONS;
  }, [health, state.messages, state.thinking, session.sending]);

  function toggleJudges() {
    if (judges) setJudges(false);
    else if (adminToken) setJudges(true);
    else setAsking(true);
  }

  async function verifyAdmin(token: string): Promise<"ok" | "wrong" | "unavailable"> {
    if (!session.sessionId) return "unavailable";
    const response = await fetch(`/api/sessions/${session.sessionId}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (response.ok) return "ok";
    return response.status === 401 ? "wrong" : "unavailable";
  }

  const comparison = state.comparison;
  return (
    <div className="min-h-screen bg-ground">
      <Header>
        <ConnectionPill status={session.connection} />
        {health?.llm === "scripted" ? <DemoBadge /> : null}
        <JudgesToggle on={judges} onToggle={toggleJudges} />
      </Header>
      <TokenDialog
        open={asking}
        title="מצב שופטים"
        description="מצב השופטים מציג את חדר המנועים: קריאות לכלים, בדיקת המספרים ועלויות. הזינו את טוקן המנהל; הוא נשמר לסשן הזה בלבד."
        label="טוקן מנהל"
        verify={verifyAdmin}
        onCancel={() => setAsking(false)}
        onAccept={(token) => {
          setToken("admin", token);
          setAdminToken(token);
          setAsking(false);
          setJudges(true);
        }}
      />

      <main className="flex flex-wrap items-start gap-6 px-8 py-6 max-sm:px-4">
        <ChatPanel
          messages={state.messages}
          turns={state.turns}
          thinking={state.thinking || session.sending}
          suggestions={suggestions}
          failedText={session.sendFailure?.text ?? null}
          onSend={session.send}
        />
        <div className="flex min-w-0 flex-[999_1_640px] flex-col gap-6">
          <HeroAnnouncement comparison={comparison} />
          {comparison ? (
            <>
              <HeroCard comparison={comparison} />
              <Waterfall view={comparison.view} />
              <InputsCard view={comparison.view} />
            </>
          ) : (
            <EmptyComparison />
          )}
        </div>
      </main>
    </div>
  );
}
