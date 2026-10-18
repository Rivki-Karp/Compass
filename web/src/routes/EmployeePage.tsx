import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import type { JudgesStats } from "../api/types";
import { ChatPanel } from "../employee/ChatPanel";
import { type EffectsMemory, EffectsMemoryContext } from "../employee/effects";
import { EmptyComparison } from "../employee/EmptyComparison";
import { HeroAnnouncement, HeroCard } from "../employee/HeroCard";
import { InputsCard } from "../employee/InputsCard";
import { EngineRoom } from "../judges/EngineRoom";
import { HowItWorks, StatsGrid } from "../judges/Summary";
import { useTurnSelection } from "../judges/useTurnSelection";
import { demoSuggestions, GENERAL_SUGGESTIONS } from "../employee/suggestions";
import { clearToken, getToken, setToken } from "../lib/tokens";
import { useHealth } from "../lib/useHealth";
import { limitReached } from "../state/session";
import { useSession } from "../state/useSession";
import { ConnectionPill, DemoBadge, Header, JudgesToggle } from "../ui/Header";
import { TokenDialog } from "../ui/TokenDialog";
import { Waterfall } from "../waterfall/Waterfall";

/** Judges mode's stats tiles: loaded with the admin token when judges mode turns on. */
function useJudgesStats(token: string | null): JudgesStats | null {
  const [stats, setStats] = useState<JudgesStats | null>(null);
  useEffect(() => {
    if (!token) return;
    let live = true;
    api
      .judgesStats(token)
      .then((s) => live && setStats(s))
      .catch(() => live && setStats(null));
    return () => {
      live = false;
    };
  }, [token]);
  return token ? stats : null;
}

/**
 * The employee screen (brief §4.2): chat on the right, the comparison on the left. In judges
 * mode (§4.5): the summary on the right, the engine room on the left.
 */
export function EmployeePage() {
  const health = useHealth();
  const [judges, setJudges] = useState(false);
  const [asking, setAsking] = useState(false);
  const [adminToken, setAdminToken] = useState<string | null>(() => getToken("admin"));
  const session = useSession(judges ? adminToken : null);
  const { state } = session;
  // Which effects (motion, announcements) already played, per session: never twice.
  // A new, empty memory for each session id (the dependency is the point, not an input).
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const effects = useMemo<EffectsMemory>(() => ({}), [session.sessionId]);
  const stats = useJudgesStats(judges ? adminToken : null);
  const [turn, setTurn] = useTurnSelection(state.turns.length);

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
    <EffectsMemoryContext.Provider value={effects}>
      <div className="min-h-screen bg-ground">
        {/* once, outside both layouts: switching layouts never re-announces */}
        <HeroAnnouncement comparison={comparison} />
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

        {judges ? (
          <main className="wide:flex-nowrap flex flex-wrap items-start gap-6 px-8 py-6 max-sm:px-4">
            <div className="flex min-w-0 flex-[1_1_420px] flex-col gap-6">
              {comparison ? <HeroCard comparison={comparison} compact /> : <EmptyComparison />}
              <HowItWorks />
              <StatsGrid stats={stats} />
            </div>
            <EngineRoom turns={state.turns} selected={turn} onSelect={setTurn} />
          </main>
        ) : (
          <main className="wide:flex-nowrap flex flex-wrap items-start gap-6 px-8 py-6 max-sm:px-4">
            <ChatPanel
              messages={state.messages}
              turns={state.turns}
              thinking={state.thinking || session.sending}
              suggestions={suggestions}
              failedText={session.sendFailure?.text ?? null}
              onSend={session.send}
              limitReached={limitReached(state)}
              onNewSession={session.newSession}
            />
            <div className="flex min-w-0 flex-[999_1_640px] flex-col gap-6">
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
        )}
      </div>
    </EffectsMemoryContext.Provider>
  );
}
