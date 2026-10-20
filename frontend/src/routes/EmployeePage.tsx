import { useEffect, useMemo, useState } from "react";
import { api, apiFetch } from "../api/client";
import type { JudgesStats } from "../api/types";
import { ChatPanel } from "../employee/ChatPanel";
import { CurrentCarPicker } from "../employee/CurrentCarPicker";
import { type EffectsMemory, EffectsMemoryContext } from "../employee/effects";
import { EmptyComparison } from "../employee/EmptyComparison";
import { HeroAnnouncement, HeroCard } from "../employee/HeroCard";
import { InputsCard } from "../employee/InputsCard";
import { useOptionSelection } from "../employee/options";
import { OptionsSelector } from "../employee/OptionsSelector";
import { PhoneBar } from "../employee/PhoneBar";
import { PHONE_QUERY, phoneBarVisible } from "../employee/phoneBarRules";
import { useMediaQuery } from "../lib/useMediaQuery";
import { EngineRoom } from "../judges/EngineRoom";
import { HowItWorks, StatsGrid } from "../judges/Summary";
import { offerVisible } from "../payslip/payslip";
import { PayslipOffer } from "../payslip/PayslipOffer";
import { usePayslip } from "../payslip/usePayslip";
import { useTurnSelection } from "../judges/useTurnSelection";
import { demoSuggestions, GENERAL_SUGGESTIONS } from "../employee/suggestions";
import { useAuth } from "../auth/context";
import { expireSession } from "../auth/authStore";
import { clearToken, getToken, setToken } from "../lib/tokens";
import { useHealth } from "../lib/useHealth";
import { useInView } from "../lib/useInView";
import { limitReached } from "../state/session";
import { useSession } from "../state/useSession";
import { Button } from "../ui/Button";
import { ConnectionPill, DemoBadge, Header, JudgesToggle } from "../ui/Header";
import { tokenCheck, type TokenCheck } from "../lib/tokenCheck";
import { TokenDialog } from "../ui/TokenDialog";
import { Waterfall } from "../waterfall/Waterfall";

const HERO_ID = "hero-card";

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
  // with accounts the stream carries the login (the server decides what each role may see)
  const auth = useAuth();
  const login = auth.status === "in" ? (auth.user?.token ?? null) : null;
  const session = useSession(login ?? (judges ? adminToken : null));
  const { state } = session;
  // Which effects (motion, announcements) already played, per session: never twice.
  // A new, empty memory for each session id (the dependency is the point, not an input).
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const effects = useMemo<EffectsMemory>(() => ({}), [session.sessionId]);
  const stats = useJudgesStats(judges ? adminToken : null);
  const [turn, setTurn] = useTurnSelection(state.turns.length);
  const phone = useMediaQuery(PHONE_QUERY);
  // the phone bar steps aside while the hero is on screen, below the bar's own 48 px
  const heroInView = useInView(HERO_ID, phone && !judges, 48, state.comparison !== null);

  // The login ended under an open stream: back to the landing page.
  useEffect(() => {
    if (login && session.connection === "unauthorized") expireSession();
  }, [login, session.connection]);

  // A stored admin token the server no longer accepts: forget it, leave judges mode.
  useEffect(() => {
    if (login) return;
    if (session.connection === "unauthorized" && judges) {
      clearToken("admin");
      setAdminToken(null);
      setJudges(false);
    }
  }, [session.connection, judges, login]);

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

  async function verifyAdmin(token: string): Promise<TokenCheck> {
    if (!session.sessionId) return "unavailable";
    const response = await apiFetch(`/sessions/${session.sessionId}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    return tokenCheck(response.status, [401]);
  }

  // the payslip upload: only when the server says the flag is on (health.payslip)
  const payslip = usePayslip({
    sessionId: session.sessionId,
    limits: health?.payslip,
    pending: state.payslip,
  });

  // today's car, picked from the catalog the server offers while the car is unknown
  const sessionId = session.sessionId;
  const carPicker =
    state.carPicker && sessionId ? (
      <CurrentCarPicker
        picker={state.carPicker}
        onPick={async (pick) => {
          await api.pickCurrentCar(sessionId, pick);
        }}
      />
    ) : null;
  const tray =
    payslip.tray || carPicker ? (
      <>
        {payslip.tray}
        {carPicker}
      </>
    ) : null;

  // Every alternative on screen (list_options) and the one shown: the employee's pick, until
  // the agent compares something new; by default the one the agent compared last, else the best.
  const { options, comparison, selected, select } = useOptionSelection(state);
  const selector =
    selected && options.length > 1 ? (
      <OptionsSelector options={options} selected={selected} onSelect={select} />
    ) : null;
  return (
    <EffectsMemoryContext.Provider value={effects}>
      <div className="min-h-screen bg-ground">
        {/* once, outside both layouts: switching layouts never re-announces */}
        <HeroAnnouncement comparison={comparison} />
        <Header>
          <ConnectionPill status={session.connection} />
          {health?.llm === "scripted" ? <DemoBadge /> : null}
          {login ? null : <JudgesToggle on={judges} onToggle={toggleJudges} />}
          {login ? (
            <Button variant="secondary" onClick={() => void auth.logout()}>
              יציאה
            </Button>
          ) : null}
        </Header>
        {comparison && phoneBarVisible({ narrow: phone, comparison, judges }) ? (
          <PhoneBar comparison={comparison} heroId={HERO_ID} hidden={heroInView} />
        ) : null}
        <TokenDialog
          open={asking}
          title="מצב שופטים"
          description="מצב השופטים מציג את חדר המנועים: קריאות לכלים, בדיקת המספרים ועלויות. הזינו את טוקן המנהל; הוא נשמר לסשן הזה בלבד."
          label="טוקן מנהל"
          verify={verifyAdmin}
          notConfigured={health?.auth?.admin === false}
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
              attach={payslip.attach}
              tray={tray}
              intro={
                payslip.open && offerVisible(state) ? <PayslipOffer onUpload={payslip.open} /> : null
              }
            />
            <div className="flex min-w-0 flex-[999_1_640px] flex-col gap-6">
              {selector}
              {comparison ? (
                <>
                  <HeroCard comparison={comparison} id={HERO_ID} />
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
