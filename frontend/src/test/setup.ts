import "@testing-library/jest-dom/vitest";
import "fake-indexeddb/auto";

Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: () => ({ matches: false, addEventListener: () => undefined, removeEventListener: () => undefined }),
});

Object.defineProperty(navigator, "onLine", { configurable: true, value: true });
