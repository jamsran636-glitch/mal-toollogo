import { beforeEach, describe, expect, it, vi } from "vitest";
import { enqueueMutation, listQueue, removeQueueItem, retryQueue } from "./queue";

describe("offline queue", () => {
  beforeEach(async () => {
    const rows = await listQueue("test-user");
    await Promise.all(rows.map((row) => removeQueueItem(row.id)));
  });

  it("stores approved JSON mutations with a user and idempotency key", async () => {
    const row = await enqueueMutation("test-user", "/api/v1/cattle", "POST", { ear_tag: "42" });
    expect(row.status).toBe("pending");
    expect(row.idempotencyKey).toBeTruthy();
    expect((await listQueue("test-user"))).toHaveLength(1);
  });

  it("rejects auth paths", async () => {
    await expect(enqueueMutation("test-user", "/api/v1/auth/login", "POST", { code: "secret" })).rejects.toThrow(/боломжгүй/);
  });

  it("rejects permanent delete, restore, and image upload paths", async () => {
    await expect(enqueueMutation("test-user", "/api/v1/cattle/1/permanent", "POST", {})).rejects.toThrow(/боломжгүй/);
    await expect(enqueueMutation("test-user", "/api/v1/horses/1/restore", "POST", {})).rejects.toThrow(/боломжгүй/);
    await expect(enqueueMutation("test-user", "/api/v1/horses/1/images", "POST", {})).rejects.toThrow(/боломжгүй/);
  });

  it("uses one sync flight and one idempotent request for simultaneous triggers", async () => {
    await enqueueMutation("test-user", "/api/v1/cattle", "POST", { ear_tag: "single-flight" });
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      void input;
      void init;
      return new Response(JSON.stringify({ id: "server-row" }), { status: 200, headers: { "Content-Type": "application/json" } });
    });
    vi.stubGlobal("fetch", fetchMock);
    await Promise.all([retryQueue("test-user"), retryQueue("test-user"), retryQueue("test-user")]);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(new Headers(fetchMock.mock.calls[0][1]?.headers).get("Idempotency-Key")).toBeTruthy();
    expect(await listQueue("test-user")).toHaveLength(0);
    vi.unstubAllGlobals();
  });
});
