import { describe, expect, it } from "vitest";
import { money } from "./Operations";

describe("Mongolian currency", () => {
  it("formats tugrik without fractional noise", () => {
    const formatted = money(1250000);
    expect(formatted).toContain("1,250,000");
    expect(formatted).toMatch(/₮|MNT/);
  });
});
