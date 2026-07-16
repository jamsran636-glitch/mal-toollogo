import { useEffect } from "react";
import { retryQueue } from "./queue";

const POLL_INTERVAL_MS = 30_000;

export function useAutoSync(userId: string | undefined): void {
  useEffect(() => {
    if (!userId) return;

    const sync = () => {
      if (navigator.onLine && document.visibilityState === "visible") {
        void retryQueue(userId).catch(() => undefined);
      }
    };
    const online = () => sync();
    const visibility = () => {
      if (document.visibilityState === "visible") sync();
    };
    const focus = () => sync();
    const mutation = () => sync();

    sync();
    window.addEventListener("online", online);
    window.addEventListener("focus", focus);
    window.addEventListener("mal-mutation-success", mutation);
    document.addEventListener("visibilitychange", visibility);
    const poll = window.setInterval(sync, POLL_INTERVAL_MS);
    return () => {
      window.removeEventListener("online", online);
      window.removeEventListener("focus", focus);
      window.removeEventListener("mal-mutation-success", mutation);
      document.removeEventListener("visibilitychange", visibility);
      window.clearInterval(poll);
    };
  }, [userId]);
}
