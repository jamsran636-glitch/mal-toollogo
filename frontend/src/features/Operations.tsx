import { useEffect, useRef, useState, type FormEvent } from "react";
import { ArrowLeft, Download, Plus, Upload } from "lucide-react";
import { Cell, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, API_URL, download, NetworkError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { ErrorBox, JsonDiff, Modal } from "../components/Common";
import { enqueueMutation } from "../offline/queue";
import type { AuditRow, Census, Dashboard, FinanceEntry, Herder } from "../types";

const today = new Date().toISOString().slice(0, 10);
const modules = [{ value: "horses", label: "Адуу" }, { value: "cattle", label: "Үхэр" }, { value: "small_livestock", label: "Хонь/ямаа" }, { value: "general", label: "Нэгдсэн" }];
const expenseCategories = ["Малчинд", "Өвс тэжээлд", "Татварт", "Хашаа хороонд", "Бусад ажлын хөлсөнд", "Түлшинд", "Бусад"];
const colors = ["#356c4b", "#d69442", "#7b6fc2", "#ca5d62", "#5094a0", "#94a34a", "#8b6c55"];
export const money = (value: number) => new Intl.NumberFormat("mn-MN", { style: "currency", currency: "MNT", maximumFractionDigits: 0 }).format(value);

function Header({ title, onBack, children }: { title: string; onBack(): void; children?: React.ReactNode }) { return <header className="page-header"><button className="icon" onClick={onBack} aria-label="Буцах"><ArrowLeft /></button><h1>{title}</h1><div>{children}</div></header>; }

function useSyncRefresh(load: () => void): void {
  const current = useRef(load);
  current.current = load;
  useEffect(() => {
    const refresh = () => current.current();
    window.addEventListener("mal-data-refresh", refresh);
    return () => window.removeEventListener("mal-data-refresh", refresh);
  }, []);
}

export function SheepPage({ onBack }: { onBack(): void }) {
  const { user } = useAuth();
  const [type, setType] = useState<"FULL" | "EVENING">("FULL");
  const [rows, setRows] = useState<Census[]>([]);
  const [losses, setLosses] = useState<Array<Record<string, string | number | boolean>>>([]);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Census | null>(null);
  const [lossOpen, setLossOpen] = useState(false);
  const [error, setError] = useState("");
  const load = async () => { try { setRows(await api(`/api/v1/small-livestock/counts?count_type=${type}`)); if (user?.role === "OWNER") setLosses(await api("/api/v1/small-livestock/losses")); } catch (reason) { setError(reason instanceof Error ? reason.message : "Мэдээлэл ачаалсангүй"); } };
  useSyncRefresh(() => void load());
  useEffect(() => { void load(); }, [type]);
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!user) return;
    const raw = Object.fromEntries(new FormData(event.currentTarget));
    const numeric = ["sheep_male", "sheep_female", "goat_male", "goat_female", "male_lamb", "female_lamb", "male_kid", "female_kid", "hogget", "yearling_goat", "ram", "buck", "evening_sheep_total", "evening_goat_total"];
    const payload: Record<string, unknown> = { count_type: type, count_date: raw.count_date, note: raw.note || null };
    numeric.forEach((key) => { if (raw[key] !== undefined && raw[key] !== "") payload[key] = Number(raw[key]); });
    if (editing) { payload.expected_version = editing.version; payload.correction_reason = raw.correction_reason; }
    try {
      await api(editing ? `/api/v1/small-livestock/counts/${editing.id}` : "/api/v1/small-livestock/counts", { method: editing ? "PATCH" : "POST", body: JSON.stringify(payload), headers: editing ? {} : { "Idempotency-Key": crypto.randomUUID() } });
      setOpen(false); setEditing(null); await load();
    } catch (reason) {
      if (!editing && reason instanceof NetworkError) { await enqueueMutation(user.id, "/api/v1/small-livestock/counts", "POST", payload); setOpen(false); setError("Тооллого синк хийх дараалалд орлоо."); }
      else setError(reason instanceof Error ? reason.message : "Хадгалсангүй");
    }
  }
  async function saveLoss(event: FormEvent<HTMLFormElement>) { event.preventDefault(); const raw = Object.fromEntries(new FormData(event.currentTarget)); await api("/api/v1/small-livestock/losses", { method: "POST", body: JSON.stringify({ ...raw, quantity: Number(raw.quantity), unnatural_loss: raw.unnatural_loss === "true", herder_id: null }) }); setLossOpen(false); await load(); }
  const current = rows[0];
  return <main className="page-shell"><Header title="Хонь, ямаа" onBack={onBack}><button className="primary" onClick={() => setOpen(true)}><Plus /> Тооллого</button></Header><ErrorBox error={error} />
    {current && <div className="stat-grid"><div><span>Нийт</span><strong>{current.total}</strong></div><div><span>Хонь</span><strong>{current.sheep_total}</strong></div><div><span>Ямаа</span><strong>{current.goat_total}</strong></div><div><span>Том мал</span><strong>{current.adult_total}</strong></div></div>}
    <nav className="tabs"><button className={type === "FULL" ? "active" : ""} onClick={() => setType("FULL")}>Бүрэн тооллого</button><button className={type === "EVENING" ? "active" : ""} onClick={() => setType("EVENING")}>Оройн тоо</button>{user?.role === "OWNER" && <button onClick={() => setLossOpen(true)}>Хорогдол бүртгэх</button>}</nav>
    <section className="table-card"><table><thead><tr><th>Огноо</th><th>Нийт</th><th>Хонь</th><th>Ямаа</th><th>Тайлбар</th><th /></tr></thead><tbody>{rows.map((row) => <tr key={row.id}><td>{row.count_date}</td><td>{row.total}</td><td>{row.sheep_total}</td><td>{row.goat_total}</td><td>{row.note || "—"}</td><td><button className="link" onClick={() => { setEditing(row); setOpen(true); }}>Засах</button></td></tr>)}</tbody></table></section>
    {user?.role === "OWNER" && losses.length > 0 && <section className="panel"><h2>Хорогдлын түүх</h2>{losses.map((loss) => <p key={String(loss.id)}>{loss.loss_date} · {loss.livestock_type} · {loss.quantity} · {loss.reason}</p>)}</section>}
    {open && <Modal title={editing ? "Тооллого засах" : "Тооллого бүртгэх"} onClose={() => { setOpen(false); setEditing(null); }} wide><form className="form-grid" onSubmit={save}><label>Огноо<input type="date" name="count_date" defaultValue={editing?.count_date || today} required /></label>{type === "EVENING" ? <><NumberInput name="evening_sheep_total" label="Хонины нийт" value={editing?.evening_sheep_total} /><NumberInput name="evening_goat_total" label="Ямааны нийт" value={editing?.evening_goat_total} /></> : <>{[["sheep_male","Нас бие гүйцсэн эр хонь (хуц тусдаа)"],["sheep_female","Нас бие гүйцсэн эм хонь"],["goat_male","Нас бие гүйцсэн эр ямаа (ухна тусдаа)"],["goat_female","Нас бие гүйцсэн эм ямаа"],["male_lamb","Эр хурга"],["female_lamb","Эм хурга"],["male_kid","Эр ишиг"],["female_kid","Эм ишиг"],["hogget","Төлөг"],["yearling_goat","Борлон"],["ram","Хуц"],["buck","Ухна"]].map(([name,label]) => <NumberInput key={name} name={name} label={label} value={editing?.[name]} />)}</>}{editing && <label className="span-2">Зассан шалтгаан<textarea name="correction_reason" required /></label>}<label className="span-2">Тайлбар<textarea name="note" defaultValue={editing?.note || ""} /></label><button className="primary span-2">Хадгалах</button></form></Modal>}
    {lossOpen && <Modal title="Хорогдол бүртгэх" onClose={() => setLossOpen(false)}><form className="form-stack" onSubmit={saveLoss}><label>Огноо<input type="date" name="loss_date" defaultValue={today} required /></label><label>Төрөл<select name="livestock_type"><option value="SHEEP">Хонь</option><option value="GOAT">Ямаа</option></select></label><label>Ангилал<input name="animal_category" required /></label><label>Тоо<input type="number" name="quantity" min="1" required /></label><label>Шалтгаан<textarea name="reason" required /></label><label className="check"><input type="checkbox" name="unnatural_loss" value="true" /> Зүй бус хорогдол</label><button className="primary">Хадгалах</button></form></Modal>}
  </main>;
}

function NumberInput({ name, label, value }: { name: string; label: string; value?: string | number | null }) { return <label>{label}<input type="number" name={name} min="0" defaultValue={value ?? 0} required /></label>; }

const widgetLabels: Record<string, string> = { profit: "Энэ жилийн ашиг", counts: "Малын тоо", mortality: "Жилийн хорогдол", growth: "Малын өсөлт", expenses: "Зардлын бүтэц", adult_males: "Нас гүйцсэн эр мал", balance: "Сарын мөнгөн урсгал" };
export function AnalyticsPage({ onBack, openTool }: { onBack(): void; openTool(tool: string): void }) {
  const [data, setData] = useState<Dashboard | null>(null);
  const [visible, setVisible] = useState(Object.keys(widgetLabels));
  const [error, setError] = useState("");
  const load = () => Promise.all([api<Dashboard>(`/api/v1/analytics/dashboard?year=${new Date().getFullYear()}`), api<{ visible_widgets: string[] }>("/api/v1/analytics/preferences")]).then(([dashboard, prefs]) => { setData(dashboard); setVisible(prefs.visible_widgets); }).catch((reason) => setError(reason instanceof Error ? reason.message : "Анализ ачаалсангүй"));
  useEffect(() => { void load(); }, []);
  useSyncRefresh(() => void load());
  async function toggle(key: string) { const next = visible.includes(key) ? visible.filter((item) => item !== key) : [...visible, key]; setVisible(next); await api("/api/v1/analytics/preferences", { method: "PUT", body: JSON.stringify({ visible_widgets: next }) }); }
  if (!data) return <main className="page-shell"><Header title="Анализ" onBack={onBack} /><ErrorBox error={error} /></main>;
  const profits = Object.entries(data.profit_by_livestock).map(([name, item]) => ({ name: modules.find((module) => module.value === name)?.label || name, value: item.profit }));
  const positiveProfit = profits.map((item) => ({ ...item, value: Math.max(item.value, 0) }));
  return <main className="page-shell"><Header title="Анализ" onBack={onBack} /><ErrorBox error={error} />
    <section className="widget-settings">{Object.entries(widgetLabels).map(([key, label]) => <label key={key}><input type="checkbox" checked={visible.includes(key)} onChange={() => void toggle(key)} /> {label}</label>)}</section>
    <section className="dashboard-grid">
      {visible.includes("profit") && <ChartCard title="Энэ жилийн ашиг"><Chart data={positiveProfit} />{profits.map((item) => <p key={item.name}>{item.name}: <strong className={item.value < 0 ? "negative" : ""}>{money(item.value)}</strong></p>)}</ChartCard>}
      {visible.includes("counts") && <ChartCard title="Малын тоо"><div className="three-way">{Object.entries(data.livestock_counts).map(([key, value]) => <div key={key}><span>{modules.find((module) => module.value === key)?.label}</span><strong>{value}</strong></div>)}</div></ChartCard>}
      {visible.includes("mortality") && <ChartCard title="Жилийн хорогдол"><div className="three-way">{Object.entries(data.mortality).map(([key, value]) => <div key={key}><span>{key}</span><strong>{value.total}</strong><small>Зүй бус: {value.abnormal}</small></div>)}</div></ChartCard>}
      {visible.includes("growth") && <ChartCard title="1-р сарын 1-ний малын өсөлт"><ResponsiveContainer width="100%" height={270}><LineChart data={data.growth}><XAxis dataKey="year" /><YAxis /><Tooltip /><Legend /><Line connectNulls={false} dataKey="horses" name="Адуу" stroke={colors[0]} /><Line connectNulls={false} dataKey="cattle" name="Үхэр" stroke={colors[1]} /><Line connectNulls={false} dataKey="small_livestock" name="Хонь" stroke={colors[2]} /></LineChart></ResponsiveContainer><p className="muted">Хоосон утга нь тухайн жилийн баталгаатай snapshot байхгүйг илэрхийлнэ.</p></ChartCard>}
      {visible.includes("expenses") && <ChartCard title="Зардлын бүтэц"><Chart data={Object.entries(data.expense_categories).map(([name, value]) => ({ name, value }))} /></ChartCard>}
      {visible.includes("adult_males") && <ChartCard title="Нас гүйцсэн эр мал"><div className="three-way">{Object.entries(data.adult_males).map(([key, item]) => <div key={key}><span>{key}</span><strong>{item.total}</strong>{Object.entries(item.age_structure || item.structure || {}).map(([label, count]) => <small key={label}>{label}: {count}</small>)}</div>)}</div></ChartCard>}
      {visible.includes("balance") && <ChartCard title="Сарын мөнгөн урсгал"><ResponsiveContainer width="100%" height={270}><LineChart data={data.monthly_balance}><XAxis dataKey="month" /><YAxis /><Tooltip formatter={(value) => money(Number(value))} /><Line dataKey="profit" name="Ашиг" stroke={colors[0]} /></LineChart></ResponsiveContainer></ChartCard>}
    </section>
    <section className="tool-grid">{[["finance","Орлого, зарлага"],["herders","Малчид"],["audit","Өөрчлөлтийн түүх"],["snapshots","Түүхэн үлдэгдэл"],["reports","Тайлан, backup"]].map(([key, label]) => <button className="secondary" key={key} onClick={() => openTool(key)}>{label}</button>)}</section>
  </main>;
}
function Chart({ data }: { data: Array<{ name: string; value: number }> }) { return <ResponsiveContainer width="100%" height={240}><PieChart><Pie data={data} dataKey="value" nameKey="name" innerRadius={55} outerRadius={85} label>{data.map((item, index) => <Cell key={item.name} fill={colors[index % colors.length]} />)}</Pie><Tooltip formatter={(value) => money(Number(value))} /><Legend /></PieChart></ResponsiveContainer>; }
function ChartCard({ title, children }: { title: string; children: React.ReactNode }) { return <article className="chart-card"><h2>{title}</h2>{children}</article>; }

export function OwnerToolPage({ tool, onBack }: { tool: string; onBack(): void }) {
  if (tool === "finance") return <FinancePage onBack={onBack} />;
  if (tool === "herders") return <HerderPage onBack={onBack} />;
  if (tool === "audit") return <AuditPage onBack={onBack} />;
  if (tool === "snapshots") return <SnapshotPage onBack={onBack} />;
  return <ReportsPage onBack={onBack} />;
}

function FinancePage({ onBack }: { onBack(): void }) {
  const [rows, setRows] = useState<FinanceEntry[]>([]); const [kind, setKind] = useState<"INCOME" | "EXPENSE">("INCOME"); const [selected, setSelected] = useState<FinanceEntry | null>(null); const [open, setOpen] = useState(false); const [error, setError] = useState("");
  const load = () => api<FinanceEntry[]>(`/api/v1/finance?entry_type=${kind}&include_archived=true`).then(setRows).catch((reason) => setError(reason instanceof Error ? reason.message : "Ачаалсангүй")); useEffect(() => { void load(); }, [kind]);
  useSyncRefresh(() => void load());
  async function save(event: FormEvent<HTMLFormElement>) { event.preventDefault(); const raw = Object.fromEntries(new FormData(event.currentTarget)); const payload = { entry_type: kind, amount: Number(raw.amount), entry_date: raw.entry_date, livestock_module: raw.livestock_module, category: kind === "EXPENSE" ? raw.category : null, description: raw.description, ...(selected ? { expected_version: selected.version } : {}) }; await api(selected ? `/api/v1/finance/${selected.id}` : "/api/v1/finance", { method: selected ? "PATCH" : "POST", body: JSON.stringify(payload), headers: selected ? {} : { "Idempotency-Key": crypto.randomUUID() } }); setOpen(false); setSelected(null); await load(); }
  return <main className="page-shell"><Header title="Санхүү" onBack={onBack}><button className="primary" onClick={() => setOpen(true)}><Plus /> Бүртгэх</button></Header><ErrorBox error={error} /><nav className="tabs"><button className={kind === "INCOME" ? "active" : ""} onClick={() => setKind("INCOME")}>Орлого</button><button className={kind === "EXPENSE" ? "active" : ""} onClick={() => setKind("EXPENSE")}>Зарлага</button></nav><section className="table-card"><table><thead><tr><th>Огноо</th><th>Төрөл</th><th>Тайлбар</th><th>Дүн</th><th /></tr></thead><tbody>{rows.map((row) => <tr className={row.is_archived ? "archived" : ""} key={row.id}><td>{row.entry_date}</td><td>{row.livestock_module}</td><td>{row.description}</td><td>{money(row.amount)}</td><td>{!row.is_archived && <button className="link" onClick={() => { setSelected(row); setOpen(true); }}>Засах</button>} {row.is_archived ? <button className="link" onClick={async () => { await api(`/api/v1/finance/${row.id}/restore`, { method: "POST", body: JSON.stringify({ reason: "Санхүүгийн бүртгэлийг сэргээв" }) }); await load(); }}>Сэргээх</button> : <button className="link danger-text" onClick={async () => { await api(`/api/v1/finance/${row.id}/archive`, { method: "POST", body: JSON.stringify({ archive_note: "Санхүүгийн бүртгэлийг архивлав" }) }); await load(); }}>Архив</button>}</td></tr>)}</tbody></table></section>{open && <Modal title={selected ? "Гүйлгээ засах" : "Гүйлгээ бүртгэх"} onClose={() => { setOpen(false); setSelected(null); }}><form className="form-stack" onSubmit={save}><label>Дүн<input type="number" name="amount" min="1" defaultValue={selected?.amount} required /></label><label>Огноо<input type="date" name="entry_date" defaultValue={selected?.entry_date || today} required /></label><label>Малын төрөл<select name="livestock_module" defaultValue={selected?.livestock_module}>{modules.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>{kind === "EXPENSE" && <label>Ангилал<select name="category" defaultValue={selected?.category || expenseCategories[0]}>{expenseCategories.map((category) => <option key={category}>{category}</option>)}</select></label>}<label>Тайлбар<textarea name="description" defaultValue={selected?.description} required /></label><button className="primary">Хадгалах</button></form></Modal>}</main>;
}

function HerderPage({ onBack }: { onBack(): void }) {
  const [rows, setRows] = useState<Herder[]>([]); const [selected, setSelected] = useState<Herder | null>(null); const [open, setOpen] = useState(false); const load = () => api<Herder[]>("/api/v1/herders?include_archived=true").then(setRows); useEffect(() => { void load(); }, []);
  useSyncRefresh(() => void load());
  async function save(event: FormEvent<HTMLFormElement>) { event.preventDefault(); const raw = Object.fromEntries(new FormData(event.currentTarget)); await api(selected ? `/api/v1/herders/${selected.id}` : "/api/v1/herders", { method: selected ? "PATCH" : "POST", body: JSON.stringify({ ...raw, ended_date: raw.ended_date || null, note: raw.note || null, ...(selected ? { expected_version: selected.version } : {}) }) }); setOpen(false); setSelected(null); await load(); }
  return <main className="page-shell"><Header title="Малчдын бүртгэл" onBack={onBack}><button className="primary" onClick={() => setOpen(true)}><Plus /> Малчин</button></Header><section className="card-grid">{rows.map((row) => <article className="panel" key={row.id}><h2>{row.last_name} {row.first_name}</h2><p>{row.module} · {row.registration_number}</p><p>{row.started_date} — {row.ended_date || "одоо"}</p><button className="secondary" onClick={() => { setSelected(row); setOpen(true); }}>Засах</button>{row.is_active ? <button className="danger" onClick={async () => { await api(`/api/v1/herders/${row.id}/archive`, { method: "POST", body: JSON.stringify({ reason: "Ажил дууссан" }) }); await load(); }}>Дуусгах</button> : <button className="primary" onClick={async () => { await api(`/api/v1/herders/${row.id}/restore`, { method: "POST", body: JSON.stringify({ reason: "Дахин ажилд оров" }) }); await load(); }}>Сэргээх</button>}</article>)}</section>{open && <Modal title="Малчны мэдээлэл" onClose={() => { setOpen(false); setSelected(null); }}><form className="form-stack" onSubmit={save}><label>Малын төрөл<select name="module" defaultValue={selected?.module}>{modules.slice(0, 3).map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label><label>Овог<input name="last_name" defaultValue={selected?.last_name} required /></label><label>Нэр<input name="first_name" defaultValue={selected?.first_name} required /></label><label>Регистр<input name="registration_number" defaultValue={selected?.registration_number} required /></label><label>Эхэлсэн огноо<input type="date" name="started_date" defaultValue={selected?.started_date || today} required /></label><label>Дууссан огноо<input type="date" name="ended_date" defaultValue={selected?.ended_date || ""} /></label><label>Тайлбар<textarea name="note" defaultValue={selected?.note || ""} /></label><button className="primary">Хадгалах</button></form></Modal>}</main>;
}

function AuditPage({ onBack }: { onBack(): void }) { const [rows, setRows] = useState<AuditRow[]>([]); const load = () => api<AuditRow[]>("/api/v1/audit?limit=300").then(setRows); useEffect(() => { void load(); }, []); useSyncRefresh(() => void load()); return <main className="page-shell"><Header title="Өөрчлөлтийн түүх" onBack={onBack} /><section className="audit-list">{rows.map((row) => <article className="audit-card" key={row.id}><header><strong>{row.username}</strong><span>{row.role} · {new Date(row.created_at).toLocaleString("mn-MN")}</span></header><h3>{row.action} · {row.entity_type || row.module}</h3>{row.detail && <p>{row.detail}</p>}<div className="diff-columns"><div><h4>Өмнө</h4><JsonDiff value={row.previous_data} /></div><div><h4>Дараа</h4><JsonDiff value={row.new_data} /></div></div></article>)}</section></main>; }

function SnapshotPage({ onBack }: { onBack(): void }) { const [rows, setRows] = useState<Array<Record<string, string | number>>>([]); const load = () => api<Array<Record<string, string | number>>>("/api/v1/analytics/snapshots").then(setRows); useEffect(() => { void load(); }, []); useSyncRefresh(() => void load()); async function save(event: FormEvent<HTMLFormElement>) { event.preventDefault(); const raw = Object.fromEntries(new FormData(event.currentTarget)); await api("/api/v1/analytics/snapshots", { method: "POST", body: JSON.stringify({ ...raw, count: Number(raw.count) }) }); event.currentTarget.reset(); await load(); } return <main className="page-shell"><Header title="1-р сарын 1-ний үлдэгдэл" onBack={onBack} /><section className="panel"><form className="form-grid" onSubmit={save}><label>Төрөл<select name="module">{modules.slice(0, 3).map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label><label>Огноо<input type="date" name="snapshot_date" defaultValue={`${new Date().getFullYear()}-01-01`} required /></label><label>Тоо<input name="count" type="number" min="0" required /></label><label>Баталгаажуулсан тайлбар<input name="note" required /></label><button className="primary span-2">Хадгалах</button></form></section><section className="panel">{rows.map((row) => <p key={String(row.id)}>{row.snapshot_date} · {row.module}: <strong>{row.count}</strong></p>)}</section></main>; }

function ReportsPage({ onBack }: { onBack(): void }) { const [restoreOpen, setRestoreOpen] = useState(false); const [message, setMessage] = useState(""); async function restore(event: FormEvent<HTMLFormElement>) { event.preventDefault(); const data = new FormData(event.currentTarget); const response = await fetch(`${API_URL}/api/v1/backup/restore`, { method: "POST", credentials: "include", headers: { Authorization: `Bearer ${sessionStorage.getItem("mal_access_token") || ""}` }, body: data }); if (!response.ok) { const body = await response.json() as { detail?: string }; throw new Error(body.detail || "Сэргээж чадсангүй"); } sessionStorage.removeItem("mal_access_token"); setMessage("Сэргээлт дууслаа. Аюулгүй байдлын үүднээс дахин нэвтэрнэ үү."); window.location.reload(); }
  return <main className="page-shell"><Header title="Тайлан ба нөөц" onBack={onBack} /><p className="warning">Backup файлд нууц мэдээлэл болон нэвтрэх хэш агуулагдана. Зөвхөн хамгаалалттай хадгална уу.</p><section className="tool-grid"><button className="secondary" onClick={() => download("/api/v1/reports/excel", "mal-toollogo.xlsx")}><Download /> Excel</button><button className="secondary" onClick={() => download("/api/v1/reports/pdf", "mal-toollogo.pdf")}><Download /> PDF</button><button className="secondary" onClick={() => download("/api/v1/backup", "mal-toollogo-backup-v2.zip")}><Download /> Backup</button><button className="danger" onClick={() => setRestoreOpen(true)}><Upload /> Backup сэргээх</button></section>{message && <p>{message}</p>}{restoreOpen && <Modal title="Backup сэргээх" onClose={() => setRestoreOpen(false)}><p>Энэ үйлдэл одоогийн мэдээллийг зөвхөн бүрэн шалгагдсан backup-аар солино. Сервер эхлээд өөрийн нөөц үүсгэнэ.</p><form className="form-stack" onSubmit={(event) => void restore(event).catch((reason) => setMessage(reason instanceof Error ? reason.message : "Сэргээсэнгүй"))}><label>Backup ZIP<input type="file" name="file" accept="application/zip" required /></label><label>Баталгаажуулахын тулд RESTORE гэж бичнэ үү<input name="confirmation" pattern="RESTORE" required /></label><button className="danger">Сэргээх</button></form></Modal>}</main>;
}
