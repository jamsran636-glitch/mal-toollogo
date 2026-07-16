import { beforeEach, describe, expect, it } from "vitest";
import { enqueueMutation, listQueue, removeQueueItem } from "./queue";

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
});
