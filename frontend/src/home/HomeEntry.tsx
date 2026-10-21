import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { Button } from "../ui/Button";

/**
 * `/` and `/new` for a logged-in user: open a new conversation (the server deletes the user's other
 * empty ones, so they do not pile up; "שיחה חדשה" inside an empty conversation never gets here).
 * The address becomes /c/:id, which is what resuming and sharing the link use.
 */
export function HomeEntry() {
  const navigate = useNavigate();
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const started = useRef<number | null>(null);

  useEffect(() => {
    if (started.current === attempt) return; // StrictMode runs effects twice: one conversation
    started.current = attempt;
    void (async () => {
      try {
        const { id } = await api.createSession();
        navigate(`/c/${id}`, { replace: true });
      } catch {
        setFailed(true);
      }
    })();
  }, [attempt, navigate]);

  if (failed) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-ground p-6 text-center">
        <p role="alert" className="text-ink">
          לא הצלחנו לפתוח שיחה.
        </p>
        <Button
          onClick={() => {
            setFailed(false);
            setAttempt((n) => n + 1);
          }}
        >
          נסו שוב
        </Button>
      </div>
    );
  }
  return <div role="status" aria-label="פותח שיחה" className="min-h-screen bg-ground" />;
}
