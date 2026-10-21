import { useState } from "react";
import { applyProfile, deleteProfile, dismissProfile } from "../api/client";
import type { PendingProfile } from "../state/session";
import { ProfileCard, type ProfileChoice } from "./ProfileCard";

const FAILED = "לא הצלחנו להשלים את הפעולה. בדקו את הערכים ונסו שוב.";

/** The card with its calls. The answer reaches the screen as the server's own events
 * (profile_applied / profile_dismissed) that close it, so a refresh or another tab agree. */
export function ProfileOffer({
  sessionId,
  pending,
}: {
  sessionId: string;
  pending: PendingProfile;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch {
      setError(FAILED);
    } finally {
      setBusy(false);
    }
  }
  return (
    <ProfileCard
      key={pending.seq}
      offer={pending.offer}
      busy={busy}
      error={error}
      onApply={(choices: ProfileChoice[]) => void run(() => applyProfile(sessionId, choices))}
      onDismiss={() => void run(() => dismissProfile(sessionId))}
      onDelete={() =>
        void run(async () => {
          await deleteProfile();
          await dismissProfile(sessionId); // gone for good, and this card with it
        })
      }
    />
  );
}
