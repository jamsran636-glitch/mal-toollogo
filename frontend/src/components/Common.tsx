import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { AlertTriangle, CloudOff, Download, RefreshCw, X } from "lucide-react";
import { useAuth } from "../auth/AuthContext";
import { listQueue, removeQueueItem, retryQueue, type QueuedMutation } from "../offline/queue";

export function Modal({ title, children, onClose, wide = false }: { title: string; children: ReactNode; onClose(): void; wide?: boolean }) {
  return <div className="modal" role="dialog" aria-modal="true" aria-label={title}>
    <section className={`modal-card ${wide ? "wide" : ""}`}>
      <button className="close" aria-label="Хаах" onClick={onClose}><X /></button>
      <h2>{title}</h2>
      {children}
    </section>
  </div>;
}

export function ErrorBox({ error }: { error: string }) {
  return error ? <p className="error-message" role="alert">{error}</p> : null;
}

export function LoginPage() {
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try { await login(username, code); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Нэвтэрч чадсангүй"); }
    finally { setBusy(false); }
  }
  return <main className="login-shell"><section className="login-card">
    <img src="/icon-192.png" alt="Мал тооллого" className="app-icon" />
    <p className="eyebrow">Гэр бүлийн мал аж ахуйн бүртгэл</p>
    <h1>Мал тооллого</h1>
    <form className="form-stack" onSubmit={submit}>
      <label>Нэвтрэх нэр<input autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} required /></label>
      <label>Нэвтрэх код<input autoComplete="current-password" type="password" value={code} onChange={(event) => setCode(event.target.value)} minLength={8} required /></label>
      <ErrorBox error={error} />
      <button className="primary" disabled={busy}>{busy ? "Нэвтэрч байна…" : "Нэвтрэх"}</button>
    </form>
  </section></main>;
}

export function ChangeCodeDialog() {
  const { changeCode } = useAuth();
  const [currentCode, setCurrentCode] = useState("");
  const [newCode, setNewCode] = useState("");
  const [error, setError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault();
    try { await changeCode(currentCode, newCode); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Код сольж чадсангүй"); }
  }
  return <Modal title="Нэвтрэх кодоо солино уу" onClose={() => undefined}>
    <p>Анхны кодыг хувийн, давтагдашгүй кодоор солино уу.</p>
    <form className="form-stack" onSubmit={submit}>
      <label>Одоогийн код<input type="password" value={currentCode} onChange={(event) => setCurrentCode(event.target.value)} required /></label>
      <label>Шинэ код<input type="password" value={newCode} onChange={(event) => setNewCode(event.target.value)} minLength={10} required /></label>
      <ErrorBox error={error} />
      <button className="primary">Солих</button>
    </form>
  </Modal>;
}

export function SyncPanel({ userId, online }: { userId: string; online: boolean }) {
  const [items, setItems] = useState<QueuedMutation[]>([]);
  const [open, setOpen] = useState(false);
  const load = () => listQueue(userId).then(setItems);
  useEffect(() => {
    void load();
    const handler = () => void load();
    window.addEventListener("mal-queue-change", handler);
    if (online) void retryQueue(userId);
    return () => window.removeEventListener("mal-queue-change", handler);
  }, [online, userId]);
  return <>
    {(!online || items.length > 0) && <button className="status-pill" onClick={() => setOpen(true)}>
      {online ? <RefreshCw size={16} /> : <CloudOff size={16} />}
      {online ? `${items.length} хүлээгдэж байна` : "Офлайн"}
    </button>}
    {open && <Modal title="Синк хийх үйлдлүүд" onClose={() => setOpen(false)}>
      {!items.length && <p>Хүлээгдэж буй үйлдэл алга.</p>}
      {items.map((item) => <article className="queue-item" key={item.id}>
        <div><strong>{item.method} {item.path}</strong><span className={`badge ${item.status}`}>{item.status}</span></div>
        {item.error && <p><AlertTriangle size={15} /> {item.error}</p>}
        <small>{new Date(item.createdAt).toLocaleString("mn-MN")}</small>
        {(item.status === "failed" || item.status === "conflict") && <button className="link" onClick={() => removeQueueItem(item.id)}>Устгах</button>}
      </article>)}
      <button className="secondary" disabled={!online} onClick={() => retryQueue(userId)}><Download size={17} /> Одоо синк хийх</button>
    </Modal>}
  </>;
}

export function JsonDiff({ value }: { value: unknown }) {
  if (value === null || value === undefined) return <span className="muted">—</span>;
  if (typeof value !== "object") return <span>{String(value)}</span>;
  return <dl className="json-diff">{Object.entries(value as Record<string, unknown>).map(([key, item]) => <div key={key}><dt>{key}</dt><dd>{item === null ? "—" : String(item)}</dd></div>)}</dl>;
}
