import { render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useAutoSync } from "./useAutoSync";

const retryQueue = vi.hoisted(() => vi.fn(() => Promise.resolve()));
vi.mock("./queue", () => ({ retryQueue }));

function Harness({ userId = "owner" }: { userId?: string }) {
  useAutoSync(userId);
  return null;
}

describe("automatic sync triggers", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    retryQueue.mockClear();
    Object.defineProperty(navigator, "onLine", { configurable: true, value: true });
    Object.defineProperty(document, "visibilityState", { configurable: true, value: "visible" });
  });

  afterEach(() => vi.useRealTimers());

  it("syncs on startup, online, focus, mutation, visibility, and polling", () => {
    render(<Harness />);
    expect(retryQueue).toHaveBeenCalledTimes(1);
    window.dispatchEvent(new Event("online"));
    window.dispatchEvent(new Event("focus"));
    window.dispatchEvent(new Event("mal-mutation-success"));
    document.dispatchEvent(new Event("visibilitychange"));
    expect(retryQueue).toHaveBeenCalledTimes(5);
    vi.advanceTimersByTime(30_000);
    expect(retryQueue).toHaveBeenCalledTimes(6);
  });

  it("pauses while offline or hidden", () => {
    Object.defineProperty(navigator, "onLine", { configurable: true, value: false });
    render(<Harness />);
    expect(retryQueue).not.toHaveBeenCalled();
    Object.defineProperty(navigator, "onLine", { configurable: true, value: true });
    Object.defineProperty(document, "visibilityState", { configurable: true, value: "hidden" });
    window.dispatchEvent(new Event("focus"));
    vi.advanceTimersByTime(60_000);
    expect(retryQueue).not.toHaveBeenCalled();
  });
});
