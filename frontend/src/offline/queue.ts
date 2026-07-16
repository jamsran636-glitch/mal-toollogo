import { openDB, type DBSchema } from "idb";
import { api, ApiError, NetworkError } from "../api/client";

export type QueueStatus = "pending" | "syncing" | "failed" | "conflict";
export type SyncStatus = "synced" | "syncing" | "offline" | "failed";

export interface QueuedMutation {
  id: string;
  userId: string;
  path: string;
  method: "POST" | "PATCH" | "PUT";
  body: Record<string, unknown>;
  idempotencyKey: string;
  createdAt: string;
  status: QueueStatus;
  error?: string;
}

interface QueueDatabase extends DBSchema {
  mutations: {
    key: string;
    value: QueuedMutation;
    indexes: { "by-user": string };
  };
}

const APPROVED = [
  /^\/api\/v1\/horses(?:\/groups)?$/,
  /^\/api\/v1\/cattle$/,
  /^\/api\/v1\/small-livestock\/counts$/,
  /^\/api\/v1\/finance$/,
];

const db = openDB<QueueDatabase>("mal-toollogo-sync-v2", 1, {
  upgrade(database) {
    const store = database.createObjectStore("mutations", { keyPath: "id" });
    store.createIndex("by-user", "userId");
  },
});

const syncFlights = new Map<string, Promise<void>>();

function publishSyncStatus(userId: string, status: SyncStatus): void {
  window.dispatchEvent(new CustomEvent("mal-sync-status", { detail: { userId, status } }));
}

export async function enqueueMutation(
  userId: string,
  path: string,
  method: QueuedMutation["method"],
  body: Record<string, unknown>,
): Promise<QueuedMutation> {
  if (!APPROVED.some((rule) => rule.test(path))) {
    throw new Error("Энэ үйлдлийг офлайн үед хадгалах боломжгүй");
  }
  const id = crypto.randomUUID();
  const item: QueuedMutation = {
    id,
    userId,
    path,
    method,
    body,
    idempotencyKey: crypto.randomUUID(),
    createdAt: new Date().toISOString(),
    status: "pending",
  };
  await (await db).put("mutations", item);
  window.dispatchEvent(new Event("mal-queue-change"));
  return item;
}

export async function listQueue(userId: string): Promise<QueuedMutation[]> {
  return (await db).getAllFromIndex("mutations", "by-user", userId);
}

async function runQueue(userId: string): Promise<void> {
  if (!navigator.onLine) {
    publishSyncStatus(userId, "offline");
    return;
  }
  publishSyncStatus(userId, "syncing");
  const database = await db;
  const items = await database.getAllFromIndex("mutations", "by-user", userId);
  for (const item of items.filter((row) => row.status === "pending" || row.status === "failed")) {
    await database.put("mutations", { ...item, status: "syncing", error: undefined });
    try {
      await api(item.path, {
        method: item.method,
        body: JSON.stringify(item.body),
        headers: { "Idempotency-Key": item.idempotencyKey },
      });
      await database.delete("mutations", item.id);
    } catch (error) {
      if (error instanceof NetworkError) {
        await database.put("mutations", { ...item, status: "pending", error: error.message });
        break;
      }
      const conflict = error instanceof ApiError && error.status === 409;
      await database.put("mutations", {
        ...item,
        status: conflict ? "conflict" : "failed",
        error: error instanceof Error ? error.message : "Синк хийж чадсангүй",
      });
    }
  }
  const remaining = await database.getAllFromIndex("mutations", "by-user", userId);
  publishSyncStatus(
    userId,
    remaining.some((item) => item.status === "failed" || item.status === "conflict")
      ? "failed"
      : "synced",
  );
  window.dispatchEvent(new Event("mal-queue-change"));
  window.dispatchEvent(new Event("mal-data-refresh"));
}

export function retryQueue(userId: string): Promise<void> {
  const active = syncFlights.get(userId);
  if (active) return active;
  const flight = runQueue(userId)
    .catch((error) => {
      publishSyncStatus(userId, "failed");
      throw error;
    })
    .finally(() => syncFlights.delete(userId));
  syncFlights.set(userId, flight);
  return flight;
}

export async function removeQueueItem(id: string): Promise<void> {
  await (await db).delete("mutations", id);
  window.dispatchEvent(new Event("mal-queue-change"));
}
