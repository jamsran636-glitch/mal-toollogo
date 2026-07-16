import { useEffect, useMemo, useState } from "react";
import { BarChart3, Beef, Download, HelpCircle, LogOut, PawPrint, RefreshCw, UsersRound, UserRound } from "lucide-react";
import { api } from "./api/client";
import { useAuth } from "./auth/AuthContext";
import { ChangeCodeDialog, LoginPage, Modal, SyncPanel } from "./components/Common";
import { CattlePage, HorsePage } from "./features/Animals";
import { AnalyticsPage, OwnerToolPage, SheepPage } from "./features/Operations";
import { usePwa } from "./pwa/usePwa";
import type { ModuleKey } from "./types";

const catalog = [
  { key: "horses" as const, label: "Адуу", icon: PawPrint },
  { key: "cattle" as const, label: "Үхэр", icon: Beef },
  { key: "small_livestock" as const, label: "Хонь", icon: UsersRound },
  { key: "analytics" as const, label: "Анализ", icon: BarChart3 },
];
const roleLabels = { OWNER: "Малын эзэн", HORSE_KEEPER: "Адуучин", CATTLE_KEEPER: "Үхэрчин", SHEEP_KEEPER: "Хоньчин" };

export default function App() {
  const { user, loading, logout } = useAuth();
  const pwa = usePwa();
  const [view, setView] = useState<"home" | ModuleKey | string>("home");
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [help, setHelp] = useState(false);

  useEffect(() => {
    if (!user) return;
    const jobs: Array<Promise<void>> = [];
    if (user.allowed_modules.includes("horses")) {
      jobs.push(api<{ total: number }>("/api/v1/horses/statistics").then((row) => { setCounts((old) => ({ ...old, horses: row.total })); }));
    }
    if (user.allowed_modules.includes("cattle")) {
      jobs.push(api<{ total: number }>("/api/v1/cattle/statistics").then((row) => { setCounts((old) => ({ ...old, cattle: row.total })); }));
    }
    if (user.allowed_modules.includes("small_livestock")) {
      jobs.push(api<{ total: number }>("/api/v1/small-livestock/current").then((row) => { setCounts((old) => ({ ...old, small_livestock: row.total })); }));
    }
    void Promise.allSettled(jobs);
  }, [user, view]);

  const allowed = useMemo(() => catalog.filter((item) => user?.allowed_modules.includes(item.key)), [user]);
  if (loading) return <main className="loading-screen"><img src="/icon-192.png" alt="" /><p>Ачаалж байна…</p></main>;
  if (!user) return <>{!pwa.online && <div className="offline-banner global">Офлайн горим — нэвтрэхийн тулд сүлжээнд холбогдоно уу.</div>}<LoginPage /></>;
  if (view === "horses") return <HorsePage onBack={() => setView("home")} />;
  if (view === "cattle") return <CattlePage onBack={() => setView("home")} />;
  if (view === "small_livestock") return <SheepPage onBack={() => setView("home")} />;
  if (view === "analytics") return <AnalyticsPage onBack={() => setView("home")} openTool={setView} />;
  if (["finance", "herders", "audit", "snapshots", "reports"].includes(view)) return <OwnerToolPage tool={view} onBack={() => setView("analytics")} />;

  return <main className="app-shell">
    {!pwa.online && <div className="offline-banner">Офлайн горим — өмнө ачаалсан дэлгэц харагдаж болно.</div>}
    {pwa.updateAvailable && <div className="update-banner"><span>Шинэ хувилбар бэлэн боллоо.</span><button onClick={pwa.update}><RefreshCw /> Шинэчлэх</button></div>}
    <header className="home-header"><div><p className="eyebrow">Гэр бүлийн мал аж ахуйн бүртгэл</p><h1>Мал тооллого</h1></div><div className="account-actions"><SyncPanel userId={user.id} online={pwa.online} /><button className="user-chip"><UserRound /><span><strong>{user.username}</strong><small>{roleLabels[user.role]}</small></span></button><button className="icon" aria-label="Гарах" onClick={() => void logout()}><LogOut /></button></div></header>
    <section className="home-grid">{allowed.map(({ key, label, icon: Icon }) => <button className="home-card" key={key} onClick={() => setView(key)}><Icon /><span>{label}</span>{key !== "analytics" && <strong>{counts[key] ?? "—"}</strong>}</button>)}</section>
    <section className="home-help"><button className="ghost" onClick={() => setHelp(true)}><HelpCircle /> Суулгах заавар</button>{pwa.canInstall && <button className="secondary" onClick={() => void pwa.install()}><Download /> Апп суулгах</button>}</section>
    <footer>Мал тооллого · v2.0</footer>
    {user.must_change_code && <ChangeCodeDialog />}
    {help && <Modal title="Апп суулгах" onClose={() => setHelp(false)}><h3>iPhone / iPad</h3><p>Safari-д нээгээд Share товч → “Add to Home Screen” сонгоно.</p><h3>Android / Desktop</h3><p>Хөтчийн “Install app” товч эсвэл энэ дэлгэцийн “Апп суулгах” товчийг ашиглана.</p></Modal>}
  </main>;
}
