import * as Dialog from "@radix-ui/react-dialog";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, apiFetch } from "../api/client";
import type { JudgesStats } from "../api/types";
import { ChatPanel } from "../employee/ChatPanel";
import { NumberSourceProvider } from "../ui/NumberSource";
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
import { ProfileOffer } from "../profile/ProfileOffer";
import { usePayslip } from "../payslip/usePayslip";
import { useTurnSelection } from "../judges/useTurnSelection";
import { demoSuggestions, GENERAL_SUGGESTIONS } from "../employee/suggestions";
import { useAuth } from "../auth/context";
import { expireSession } from "../auth/authStore";
import { clearToken, getToken, setToken } from "../lib/tokens";
import { useHealth } from "../lib/useHealth";
import { useInView } from "../lib/useInView";
import { isEmptyConversation, limitReached } from "../state/session";
import { useSession } from "../state/useSession";
import { AccountBar } from "../home/AccountBar";
import { ConversationSidebar } from "../home/ConversationSidebar";
import { useConversations } from "../home/useConversations";
import { NotFound } from "./NotFound";
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
export function EmployeePage({ conversationId }: { conversationId?: string } = {}) {
  const health = useHealth();
  const navigate = useNavigate();
  const [gone, setGone] = useState(false);
  const [drawer, setDrawer] = useState(false);
  const [judges, setJudges] = useState(false);
  const [asking, setAsking] = useState(false);
  const [adminToken, setAdminToken] = useState<string | null>(() => getToken("admin"));
  // with accounts the stream carries the login (the server decides what each role may see)
  const auth = useAuth();
  const login = auth.status === "in" ? (auth.user?.token ?? null) : null;
  const accounts = login !== null && conversationId !== undefined;
  const session = useSession(login ?? (judges ? adminToken : null), {
    fixedId: accounts ? conversationId : undefined,
    onGone: () => setGone(true),
  });
  const { state } = session;
  // the list beside the chat (accounts): reloaded as this conversation moves
  const conversations = useConversations(accounts, state.lastSeq);
  // with accounts the admin's judges mode needs no token dialog: the login is the proof
  const isAdmin = accounts && auth.user?.role === "admin";
  // Which effects (motion, announcements) already played, per session: never twice.
  // A new, empty memory for each session id (the dependency is the point, not an input).
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const effects = useMemo<EffectsMemory>(() => ({}), [session.sessionId]);
  const stats = useJudgesStats(judges ? (login ?? adminToken) : null);
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
    else if (accounts || adminToken) setJudges(true);
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
  // the conversation is not this user's (or was deleted): the not-found view, as for any page
  if (gone) return <NotFound />;

  async function deleteConversation(id: string) {
    await api.deleteConversation(id);
    if (id === conversationId) navigate("/new", { replace: true });
    else conversations.reload();
  }
  const sidebar = accounts ? (
    <ConversationSidebar
      items={conversations.items}
      failed={conversations.failed}
      currentId={conversationId}
      currentEmpty={session.connection === "open" && isEmptyConversation(state)}
      onDelete={deleteConversation}
      onNavigate={() => setDrawer(false)}
    />
  ) : null;
  return (
    <EffectsMemoryContext.Provider value={effects}>
      <div className="min-h-screen bg-ground">
        {/* once, outside both layouts: switching layouts never re-announces */}
        <HeroAnnouncement comparison={comparison} />
        <Header variant={accounts ? "account" : "employee"}>
          <ConnectionPill status={session.connection} />
          {health?.llm === "scripted" ? <DemoBadge /> : null}
          {!login || isAdmin ? <JudgesToggle on={judges} onToggle={toggleJudges} /> : null}
          {accounts && auth.user ? (
            <AccountBar
              user={auth.user}
              onLogout={() => void auth.logout()}
              onMenu={phone ? () => setDrawer(true) : undefined}
            />
          ) : null}
        </Header>
        {accounts && phone ? (
          <Dialog.Root open={drawer} onOpenChange={setDrawer}>
            <Dialog.Portal>
              <Dialog.Overlay className="fixed inset-0 z-40 bg-navy/40" />
              <Dialog.Content
                dir="rtl"
                aria-describedby={undefined}
                className="fixed inset-y-0 right-0 z-50 w-[min(320px,88vw)] overflow-y-auto bg-ground p-3"
              >
                <Dialog.Title className="sr-only">השיחות שלי</Dialog.Title>
                {sidebar}
              </Dialog.Content>
            </Dialog.Portal>
          </Dialog.Root>
        ) : null}
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
            {accounts && !phone ? (
              <div className="wide:sticky wide:top-[calc(var(--header-h)+24px)] wide:max-h-[calc(100dvh-var(--header-h)-48px)] w-[280px] max-w-full shrink-0 overflow-y-auto">
                {sidebar}
              </div>
            ) : null}
            <NumberSourceProvider views={state.views}>
            <ChatPanel
              messages={state.messages}
              turns={state.turns}
              thinking={state.thinking || session.sending}
              suggestions={suggestions}
              failedText={session.sendFailure?.text ?? null}
              onSend={session.send}
              limitReached={limitReached(state)}
              onNewSession={accounts ? () => navigate("/new") : session.newSession}
              greeting={accounts ? (auth.user?.name ?? null) : null}
              attach={payslip.attach}
              tray={tray}
              intro={
                <>
                  {state.profile && session.sessionId ? (
                    <ProfileOffer sessionId={session.sessionId} pending={state.profile} />
                  ) : null}
                  {payslip.open && offerVisible(state) ? (
                    <PayslipOffer onUpload={payslip.open} />
                  ) : null}
                </>
              }
            />
            </NumberSourceProvider>
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
