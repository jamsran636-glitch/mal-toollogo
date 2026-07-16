import { useEffect, useMemo, useState, type FormEvent } from "react";
import { ArrowLeft, Camera, History, ImageOff, Pencil, Plus, RotateCcw, Trash2 } from "lucide-react";
import { API_URL, api, NetworkError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { enqueueMutation } from "../offline/queue";
import type { Cattle, Horse, HorseGroup, ImageAsset, Stats } from "../types";
import { ErrorBox, Modal } from "../components/Common";

const year = new Date().getFullYear();
const emptyHorse = { group_id: "", color: "", birth_year: year, sex: "FEMALE", male_status: "", current_status: "ACTIVE", mother_id: "", father_id: "", additional_info: "" };
type HorseForm = typeof emptyHorse;
const emptyCattle = { ear_tag: "", color: "", birth_year: year, sex: "FEMALE", is_bull: false, mother_id: "", additional_info: "" };
type CattleForm = typeof emptyCattle;

function StatGrid({ stats, animal }: { stats: Stats | null; animal: "horse" | "cattle" }) {
  if (!stats) return null;
  return <div className="stat-grid">
    <div><span>Нийт</span><strong>{stats.total}</strong></div>
    <div><span>Том эр</span><strong>{stats.eligible_males}</strong></div>
    <div><span>Том эм</span><strong>{stats.eligible_females}</strong></div>
    <div><span>{animal === "horse" ? "Унага" : "Тугал"}</span><strong>{stats.offspring}</strong></div>
  </div>;
}

export function HorsePage({ onBack }: { onBack(): void }) {
  const { user } = useAuth();
  const [groups, setGroups] = useState<HorseGroup[]>([]);
  const [rows, setRows] = useState<Horse[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [archived, setArchived] = useState(false);
  const [selected, setSelected] = useState<Horse | null>(null);
  const [form, setForm] = useState<HorseForm>(emptyHorse);
  const [editing, setEditing] = useState(false);
  const [transfers, setTransfers] = useState<Array<Record<string, string | number | null>>>([]);
  const [transferOpen, setTransferOpen] = useState(false);
  const [archiveOpen, setArchiveOpen] = useState(false);
  const [permanentOpen, setPermanentOpen] = useState(false);
  const [error, setError] = useState("");
  const load = async () => {
    try {
      const [groupData, horseData, statData] = await Promise.all([
        api<HorseGroup[]>("/api/v1/horses/groups"),
        api<Horse[]>(`/api/v1/horses?status_filter=${archived ? "ARCHIVED" : "ACTIVE"}`),
        api<Stats>("/api/v1/horses/statistics"),
      ]);
      setGroups(groupData);
      setRows(horseData);
      setStats(statData);
      setForm((current) => ({ ...current, group_id: current.group_id || groupData[0]?.id || "" }));
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Мэдээлэл ачаалсангүй"); }
  };
  useEffect(() => {
    void load();
    const refresh = () => void load();
    window.addEventListener("mal-data-refresh", refresh);
    return () => window.removeEventListener("mal-data-refresh", refresh);
  }, [archived]);
  const mares = rows.filter((row) => row.sex === "FEMALE" && !row.archived_at);
  const stallions = rows.filter((row) => row.male_status === "STALLION" && !row.archived_at);

  function beginEdit(row: Horse) {
    setSelected(row);
    setForm({ group_id: row.group_id, color: row.color, birth_year: row.birth_year, sex: row.sex, male_status: row.male_status || "", current_status: row.current_status === "PREGNANT" ? "PREGNANT" : "ACTIVE", mother_id: row.mother_id || "", father_id: row.father_id || "", additional_info: row.additional_info || "" });
    setEditing(true);
  }
  async function save(event: FormEvent) {
    event.preventDefault();
    if (!user) return;
    const payload: Record<string, unknown> = { ...form, male_status: form.sex === "MALE" ? form.male_status || null : null, mother_id: form.mother_id || null, father_id: form.father_id || null, additional_info: form.additional_info || null };
    try {
      if (selected) {
        delete payload.group_id;
        await api(`/api/v1/horses/${selected.id}`, { method: "PATCH", body: JSON.stringify({ ...payload, expected_version: selected.version }) });
      } else {
        await api("/api/v1/horses", { method: "POST", body: JSON.stringify(payload), headers: { "Idempotency-Key": crypto.randomUUID() } });
      }
      setEditing(false); setSelected(null); setForm({ ...emptyHorse, group_id: groups[0]?.id || "" }); await load();
    } catch (reason) {
      if (!selected && reason instanceof NetworkError) {
        await enqueueMutation(user.id, "/api/v1/horses", "POST", payload);
        setEditing(false); setForm({ ...emptyHorse, group_id: groups[0]?.id || "" });
        setError("Сүлжээнд холбогдоход бүртгэл автоматаар синк хийнэ.");
      } else setError(reason instanceof Error ? reason.message : "Хадгалсангүй");
    }
  }
  async function addGroup() {
    const name = (document.getElementById("group-name") as HTMLInputElement | null)?.value.trim();
    if (!name) return;
    await api("/api/v1/horses/groups", { method: "POST", body: JSON.stringify({ name }), headers: { "Idempotency-Key": crypto.randomUUID() } });
    await load();
  }
  async function restore() {
    if (!selected) return;
    await api(`/api/v1/horses/${selected.id}/restore`, { method: "POST", body: JSON.stringify({ reason: "Эзэмшигчийн баталгаатай сэргээв" }) });
    setSelected(null); await load();
  }
  async function upload(files: FileList | null) {
    if (!selected || !files?.length || !navigator.onLine) { setError("Зураг зөвхөн онлайн үед илгээгдэнэ."); return; }
    const data = new FormData();
    Array.from(files).forEach((file) => data.append("files", file));
    await api(`/api/v1/horses/${selected.id}/images`, { method: "POST", body: data });
    const fresh = await api<Horse>(`/api/v1/horses/${selected.id}`); setSelected(fresh); await load();
  }
  async function refreshSelected() {
    if (selected) setSelected(await api<Horse>(`/api/v1/horses/${selected.id}`));
  }
  async function showHistory() {
    if (!selected) return;
    setTransfers(await api(`/api/v1/horses/${selected.id}/transfers`));
  }
  return <main className="page-shell">
    <PageHeader title="Адуу" onBack={onBack} actions={<><button className="secondary" onClick={() => setArchived(!archived)}>{archived ? "Идэвхтэй" : "Архив"}</button><button className="primary" onClick={() => { setSelected(null); setEditing(true); }}><Plus /> Адуу нэмэх</button></>} />
    <ErrorBox error={error} /><StatGrid stats={stats} animal="horse" />
    {!archived && <section className="inline-create"><input id="group-name" placeholder="Азарганы шинэ бүлэг" /><button className="secondary" onClick={addGroup}>Бүлэг нэмэх</button></section>}
    <section className="animal-groups">{groups.map((group) => <article className="panel" key={group.id}><header><h2>{group.name}</h2></header>{rows.filter((row) => row.group_id === group.id).map((row) => <button className={`animal-row indent-${row.indent}`} key={row.id} onClick={() => setSelected(row)}><span>{row.sex === "FEMALE" ? "♀" : "♂"}</span><div><strong>{row.display_label}</strong><small>{row.age_category} · {row.current_status === "PREGNANT" ? "Хээлтэй" : row.relation_note || "Идэвхтэй"}</small></div></button>)}</article>)}</section>
    {editing && <Modal title={selected ? "Адуу засах" : "Адуу бүртгэх"} onClose={() => setEditing(false)} wide><HorseEditor form={form} setForm={setForm} groups={groups} mares={mares} stallions={stallions} onSubmit={save} /></Modal>}
    {selected && !editing && <Modal title={selected.display_label} onClose={() => setSelected(null)} wide>
      <div className="detail-grid"><Info label="Бүлэг" value={selected.group_name} /><Info label="Нас" value={`${selected.age_category} (${selected.age_years})`} /><Info label="Эх" value={selected.mother_label || "Тодорхойгүй"} /><Info label="Эцэг" value={selected.father_label || "Тодорхойгүй"} /></div>
      <ProfileImages animal="Адуу" main={selected.main_image} layout={selected.layout_image} images={selected.images} onExpired={refreshSelected} />
      {!selected.archived_at && <label className="file-button"><Camera /> Зураг солих<input type="file" accept="image/png,image/jpeg,image/webp" multiple onChange={(event) => void upload(event.target.files)} /></label>}
      <div className="button-row">{selected.archived_at ? <><button className="primary" onClick={restore}><RotateCcw /> Сэргээх</button>{user?.role === "OWNER" && <button className="danger" onClick={() => setPermanentOpen(true)}><Trash2 /> Бүрмөсөн устгах</button>}</> : <><button className="secondary" onClick={() => beginEdit(selected)}><Pencil /> Засах</button><button className="secondary" onClick={() => setTransferOpen(true)}>Бүлэг солих</button><button className="danger" onClick={() => setArchiveOpen(true)}>Архивлах</button></>}<button className="ghost" onClick={() => void showHistory()}><History /> Түүх</button></div>
      {transfers.length > 0 && <div className="timeline">{transfers.map((item) => <p key={String(item.id)}><strong>{item.from_group_name || "Анхны бүртгэл"} → {item.to_group_name}</strong><span>{item.reason} · {item.changed_by_name}</span></p>)}</div>}
    </Modal>}
    {transferOpen && selected && <ActionForm title="Бүлэг солих" onClose={() => setTransferOpen(false)} fields={<label>Шинэ бүлэг<select name="to_group_id" required>{groups.filter((group) => group.id !== selected.group_id).map((group) => <option value={group.id} key={group.id}>{group.name}</option>)}</select></label>} onSubmit={async (data) => { await api(`/api/v1/horses/${selected.id}/transfer`, { method: "POST", body: JSON.stringify({ ...data, expected_version: selected.version }) }); setTransferOpen(false); setSelected(null); await load(); }} />}
    {archiveOpen && selected && <ArchiveForm onClose={() => setArchiveOpen(false)} onSubmit={async (data) => { await api(`/api/v1/horses/${selected.id}/archive`, { method: "POST", body: JSON.stringify(data) }); setArchiveOpen(false); setSelected(null); await load(); }} />}
    {permanentOpen && selected && <PermanentDeleteDialog animal={selected.display_label} onClose={() => setPermanentOpen(false)} onConfirm={async () => { await api(`/api/v1/horses/${selected.id}/permanent`, { method: "DELETE", body: JSON.stringify({ confirmation: "УСТГАХ" }) }); setPermanentOpen(false); setSelected(null); await load(); }} />}
  </main>;
}

function HorseEditor({ form, setForm, groups, mares, stallions, onSubmit }: { form: HorseForm; setForm(value: HorseForm): void; groups: HorseGroup[]; mares: Horse[]; stallions: Horse[]; onSubmit(event: FormEvent): void }) {
  return <form className="form-grid" onSubmit={onSubmit}>
    <label>Бүлэг<select value={form.group_id} onChange={(event) => setForm({ ...form, group_id: event.target.value })}>{groups.map((group) => <option key={group.id} value={group.id}>{group.name}</option>)}</select></label>
    <label>Зүс<input value={form.color} onChange={(event) => setForm({ ...form, color: event.target.value })} required /></label>
    <label>Төрсөн он<input type="number" min="1980" max={year} value={form.birth_year} onChange={(event) => setForm({ ...form, birth_year: Number(event.target.value) })} required /></label>
    <label>Хүйс<select value={form.sex} onChange={(event) => setForm({ ...form, sex: event.target.value, male_status: "", current_status: "ACTIVE" })}><option value="FEMALE">Эм</option><option value="MALE">Эр</option></select></label>
    {form.sex === "MALE" && <label>Эр ангилал<select value={form.male_status} onChange={(event) => setForm({ ...form, male_status: event.target.value })}><option value="">Үрээ/морь</option><option value="STALLION">Азарга</option><option value="GELDING">Агт морь</option><option value="COLT">Үрээ</option></select></label>}
    {form.sex === "FEMALE" && <label>Төлөв<select value={form.current_status} onChange={(event) => setForm({ ...form, current_status: event.target.value })}><option value="ACTIVE">Идэвхтэй</option><option value="PREGNANT">Хээлтэй</option></select></label>}
    <label>Эх гүү<select value={form.mother_id} onChange={(event) => setForm({ ...form, mother_id: event.target.value })}><option value="">Тодорхойгүй</option>{mares.map((row) => <option key={row.id} value={row.id}>{row.display_label}</option>)}</select></label>
    <label>Эцэг азарга<select value={form.father_id} onChange={(event) => setForm({ ...form, father_id: event.target.value })}><option value="">Тодорхойгүй</option>{stallions.map((row) => <option key={row.id} value={row.id}>{row.display_label}</option>)}</select></label>
    <label className="span-2">Нэмэлт мэдээлэл<textarea value={form.additional_info} onChange={(event) => setForm({ ...form, additional_info: event.target.value })} /></label>
    <button className="primary span-2">Хадгалах</button>
  </form>;
}

export function CattlePage({ onBack }: { onBack(): void }) {
  const { user } = useAuth();
  const [rows, setRows] = useState<Cattle[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [archived, setArchived] = useState(false);
  const [selected, setSelected] = useState<Cattle | null>(null);
  const [form, setForm] = useState<CattleForm>(emptyCattle);
  const [editing, setEditing] = useState(false);
  const [archiveOpen, setArchiveOpen] = useState(false);
  const [permanentOpen, setPermanentOpen] = useState(false);
  const [error, setError] = useState("");
  const load = async () => {
    try { const [data, stat] = await Promise.all([api<Cattle[]>(`/api/v1/cattle?status_filter=${archived ? "ARCHIVED" : "ACTIVE"}`), api<Stats>("/api/v1/cattle/statistics")]); setRows(data); setStats(stat); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Мэдээлэл ачаалсангүй"); }
  };
  useEffect(() => {
    void load();
    const refresh = () => void load();
    window.addEventListener("mal-data-refresh", refresh);
    return () => window.removeEventListener("mal-data-refresh", refresh);
  }, [archived]);
  const cows = useMemo(() => rows.filter((row) => row.sex === "FEMALE" && !row.archived_at), [rows]);
  function beginEdit(row: Cattle) { setSelected(row); setForm({ ear_tag: row.ear_tag, color: row.color, birth_year: row.birth_year, sex: row.sex, is_bull: row.is_bull, mother_id: row.mother_id || "", additional_info: row.additional_info || "" }); setEditing(true); }
  async function save(event: FormEvent) {
    event.preventDefault(); if (!user) return;
    const payload: Record<string, unknown> = { ...form, mother_id: form.mother_id || null };
    try {
      if (selected) await api(`/api/v1/cattle/${selected.id}`, { method: "PATCH", body: JSON.stringify({ ...payload, expected_version: selected.version }) });
      else await api("/api/v1/cattle", { method: "POST", body: JSON.stringify(payload), headers: { "Idempotency-Key": crypto.randomUUID() } });
      setEditing(false); setSelected(null); setForm(emptyCattle); await load();
    } catch (reason) {
      if (!selected && reason instanceof NetworkError) { await enqueueMutation(user.id, "/api/v1/cattle", "POST", payload); setEditing(false); setError("Бүртгэл синк хийх дараалалд орлоо."); }
      else setError(reason instanceof Error ? reason.message : "Хадгалсангүй");
    }
  }
  async function upload(files: FileList | null) { if (!selected || !files?.length || !navigator.onLine) { setError("Зураг онлайн үед илгээгдэнэ."); return; } const data = new FormData(); Array.from(files).forEach((file) => data.append("files", file)); setSelected(await api<Cattle>(`/api/v1/cattle/${selected.id}/images`, { method: "POST", body: data })); await load(); }
  async function refreshSelected() { if (selected) setSelected(await api<Cattle>(`/api/v1/cattle/${selected.id}`)); }
  return <main className="page-shell">
    <PageHeader title="Үхэр" onBack={onBack} actions={<><button className="secondary" onClick={() => setArchived(!archived)}>{archived ? "Идэвхтэй" : "Архив"}</button><button className="primary" onClick={() => { setSelected(null); setForm(emptyCattle); setEditing(true); }}><Plus /> Үхэр нэмэх</button></>} />
    <ErrorBox error={error} /><StatGrid stats={stats} animal="cattle" />
    <section className="panel list-panel">{rows.map((row) => <button className="animal-row" key={row.id} onClick={() => setSelected(row)}><span>{row.is_bull ? "Б" : row.sex === "FEMALE" ? "♀" : "♂"}</span><div><strong>{row.ear_tag} · {row.color}</strong><small>{row.age_category}{row.mother_label ? ` · Эх: ${row.mother_label}` : ""}</small></div></button>)}</section>
    {editing && <Modal title={selected ? "Үхэр засах" : "Үхэр бүртгэх"} onClose={() => setEditing(false)}><form className="form-grid" onSubmit={save}>
      <label>Ээмэгний дугаар<input value={form.ear_tag} onChange={(event) => setForm({ ...form, ear_tag: event.target.value })} required /></label><label>Зүс<input value={form.color} onChange={(event) => setForm({ ...form, color: event.target.value })} required /></label><label>Төрсөн он<input type="number" min="1980" max={year} value={form.birth_year} onChange={(event) => setForm({ ...form, birth_year: Number(event.target.value) })} /></label><label>Хүйс<select value={form.sex} onChange={(event) => setForm({ ...form, sex: event.target.value, is_bull: false })}><option value="FEMALE">Эм</option><option value="MALE">Эр</option></select></label>{form.sex === "MALE" && <label className="check"><input type="checkbox" checked={form.is_bull} onChange={(event) => setForm({ ...form, is_bull: event.target.checked })} /> Үржлийн бух</label>}<label>Эх үнээ<select value={form.mother_id} onChange={(event) => setForm({ ...form, mother_id: event.target.value })}><option value="">Тодорхойгүй</option>{cows.map((row) => <option key={row.id} value={row.id}>{row.ear_tag}</option>)}</select></label><label className="span-2">Нэмэлт мэдээлэл<textarea value={form.additional_info} onChange={(event) => setForm({ ...form, additional_info: event.target.value })} /></label><button className="primary span-2">Хадгалах</button>
    </form></Modal>}
    {selected && !editing && <Modal title={`${selected.ear_tag} · ${selected.color}`} onClose={() => setSelected(null)}><div className="detail-grid"><Info label="Нас" value={`${selected.age_category} (${selected.age_years})`} /><Info label="Хүйс" value={selected.sex === "FEMALE" ? "Эм" : "Эр"} /><Info label="Эх" value={selected.mother_label || "Тодорхойгүй"} /><Info label="Төлөв" value={selected.current_status} /></div><ProfileImages animal="Үхэр" main={selected.main_image} layout={selected.layout_image} images={selected.images} onExpired={refreshSelected} />{!selected.archived_at && <label className="file-button"><Camera /> Зураг солих<input type="file" multiple accept="image/png,image/jpeg,image/webp" onChange={(event) => void upload(event.target.files)} /></label>}<div className="button-row">{selected.archived_at ? <><button className="primary" onClick={async () => { await api(`/api/v1/cattle/${selected.id}/restore`, { method: "POST", body: JSON.stringify({ reason: "Эзэмшигчийн баталгаатай сэргээв" }) }); setSelected(null); await load(); }}><RotateCcw /> Сэргээх</button>{user?.role === "OWNER" && <button className="danger" onClick={() => setPermanentOpen(true)}><Trash2 /> Бүрмөсөн устгах</button>}</> : <><button className="secondary" onClick={() => beginEdit(selected)}><Pencil /> Засах</button><button className="danger" onClick={() => setArchiveOpen(true)}>Архивлах</button></>}</div></Modal>}
    {archiveOpen && selected && <ArchiveForm onClose={() => setArchiveOpen(false)} onSubmit={async (data) => { await api(`/api/v1/cattle/${selected.id}/archive`, { method: "POST", body: JSON.stringify(data) }); setArchiveOpen(false); setSelected(null); await load(); }} />}
    {permanentOpen && selected && <PermanentDeleteDialog animal={`${selected.ear_tag} · ${selected.color}`} onClose={() => setPermanentOpen(false)} onConfirm={async () => { await api(`/api/v1/cattle/${selected.id}/permanent`, { method: "DELETE", body: JSON.stringify({ confirmation: "УСТГАХ" }) }); setPermanentOpen(false); setSelected(null); await load(); }} />}
  </main>;
}

function ProfileImages({ animal, main, layout, images, onExpired }: { animal: string; main: ImageAsset | null; layout: ImageAsset | null; images: ImageAsset[]; onExpired(): Promise<void> }) {
  const preferred = [main, layout].filter((image): image is ImageAsset => Boolean(image));
  const shown = preferred.length > 0 ? preferred : images;
  const [failed, setFailed] = useState<Set<string>>(new Set());
  useEffect(() => { setFailed(new Set()); }, [main?.url, layout?.url]);
  if (!shown.length) return <div className="image-placeholder"><ImageOff /><span>{animal} зураггүй</span></div>;
  return <div className="image-strip">{shown.map((image) => failed.has(image.id) ? <div className="image-placeholder compact" key={image.id}><ImageOff /><span>Зургийг шинэчилж байна…</span></div> : <img key={image.id} src={image.url.startsWith("http") ? image.url : `${API_URL}${image.url}`} alt={`${animal} ${image.kind === "MAIN" ? "үндсэн зураг" : image.kind === "LAYOUT" ? "зургийн нийлмэл харагдац" : image.original_filename}`} onError={() => { setFailed((current) => new Set(current).add(image.id)); void onExpired(); }} />)}</div>;
}

function PermanentDeleteDialog({ animal, onClose, onConfirm }: { animal: string; onClose(): void; onConfirm(): Promise<void> }) {
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  return <Modal title="Бүрмөсөн устгах" onClose={onClose}>
    <div className="destructive-warning"><Trash2 /><p><strong>{animal}</strong> бүртгэл, түүх болон ашиглагдаагүй зургууд бүрмөсөн устна. Энэ үйлдлийг буцаах боломжгүй.</p></div>
    <form className="form-stack" onSubmit={async (event) => { event.preventDefault(); setBusy(true); setError(""); try { await onConfirm(); } catch (reason) { setError(reason instanceof Error ? reason.message : "Бүрмөсөн устгаж чадсангүй"); setBusy(false); } }}>
      <label>Баталгаажуулахын тулд УСТГАХ гэж бичнэ үү<input value={confirmation} onChange={(event) => setConfirmation(event.target.value)} autoComplete="off" /></label>
      <ErrorBox error={error} />
      <button className="danger" disabled={busy || confirmation !== "УСТГАХ"}>{busy ? "Устгаж байна…" : "Бүрмөсөн устгах"}</button>
    </form>
  </Modal>;
}

function PageHeader({ title, onBack, actions }: { title: string; onBack(): void; actions: React.ReactNode }) { return <header className="page-header"><button className="icon" aria-label="Буцах" onClick={onBack}><ArrowLeft /></button><h1>{title}</h1><div>{actions}</div></header>; }
function Info({ label, value }: { label: string; value: string }) { return <div><dt>{label}</dt><dd>{value}</dd></div>; }
function ActionForm({ title, onClose, fields, onSubmit, includeReason = true }: { title: string; onClose(): void; fields?: React.ReactNode; onSubmit(data: Record<string, unknown>): Promise<void>; includeReason?: boolean }) { const [error, setError] = useState(""); return <Modal title={title} onClose={onClose}><form className="form-stack" onSubmit={async (event) => { event.preventDefault(); const raw = Object.fromEntries(new FormData(event.currentTarget)); try { await onSubmit(raw); } catch (reason) { setError(reason instanceof Error ? reason.message : "Үйлдэл амжилтгүй"); } }}>{fields}{includeReason && <label>Шалтгаан<textarea name="reason" required /></label>}<ErrorBox error={error} /><button className="primary">Баталгаажуулах</button></form></Modal>; }
function ArchiveForm({ onClose, onSubmit }: { onClose(): void; onSubmit(data: Record<string, unknown>): Promise<void> }) { return <ActionForm title="Архивлах" onClose={onClose} includeReason={false} fields={<><label>Тайлбар<textarea name="archive_note" required /></label><label className="check"><input name="unnatural_loss" type="checkbox" value="true" /> Зүй бус хорогдол</label><label className="check"><input name="deceased" type="checkbox" value="true" /> Хорогдсон</label></>} onSubmit={(raw) => onSubmit({ archive_note: raw.archive_note, unnatural_loss: raw.unnatural_loss === "true", deceased: raw.deceased === "true" })} />; }
