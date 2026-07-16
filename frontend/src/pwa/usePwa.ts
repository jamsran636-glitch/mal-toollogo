import { useEffect, useState } from "react";

interface InstallPromptEvent extends Event {
  prompt(): Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

export function usePwa() {
  const [installPrompt, setInstallPrompt] = useState<InstallPromptEvent | null>(null);
  const [updateWorker, setUpdateWorker] = useState<ServiceWorker | null>(null);
  const [online, setOnline] = useState(navigator.onLine);

  useEffect(() => {
    const hadController = Boolean(navigator.serviceWorker?.controller);
    const onlineHandler = () => setOnline(true);
    const offlineHandler = () => setOnline(false);
    const promptHandler = (event: Event) => {
      event.preventDefault();
      setInstallPrompt(event as InstallPromptEvent);
    };
    window.addEventListener("online", onlineHandler);
    window.addEventListener("offline", offlineHandler);
    window.addEventListener("beforeinstallprompt", promptHandler);
    if ("serviceWorker" in navigator && import.meta.env.PROD) {
      navigator.serviceWorker.register("/sw.js").then((registration) => {
        registration.addEventListener("updatefound", () => {
          const worker = registration.installing;
          worker?.addEventListener("statechange", () => {
            if (worker.state === "installed" && navigator.serviceWorker.controller) setUpdateWorker(worker);
          });
        });
      });
      const controllerHandler = () => { if (hadController) window.location.reload(); };
      navigator.serviceWorker.addEventListener("controllerchange", controllerHandler);
      return () => {
        window.removeEventListener("online", onlineHandler);
        window.removeEventListener("offline", offlineHandler);
        window.removeEventListener("beforeinstallprompt", promptHandler);
        navigator.serviceWorker.removeEventListener("controllerchange", controllerHandler);
      };
    }
    return () => {
      window.removeEventListener("online", onlineHandler);
      window.removeEventListener("offline", offlineHandler);
      window.removeEventListener("beforeinstallprompt", promptHandler);
    };
  }, []);

  return {
    online,
    canInstall: Boolean(installPrompt),
    updateAvailable: Boolean(updateWorker),
    install: async () => { await installPrompt?.prompt(); setInstallPrompt(null); },
    update: () => updateWorker?.postMessage({ type: "SKIP_WAITING" }),
  };
}
