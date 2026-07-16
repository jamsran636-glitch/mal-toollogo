import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

const auth = vi.hoisted(() => ({
  user: { id: "worker", username: "Адуучин", role: "HORSE_KEEPER" as const, allowed_modules: ["horses"], must_change_code: false },
  loading: false,
  login: vi.fn(),
  logout: vi.fn(),
  changeCode: vi.fn(),
}));

vi.mock("./auth/AuthContext", () => ({ useAuth: () => auth }));
vi.mock("./api/client", async (source) => {
  const actual = await source<typeof import("./api/client")>();
  return { ...actual, api: vi.fn().mockResolvedValue({ total: 7 }) };
});

describe("role-based home", () => {
  beforeEach(() => vi.clearAllMocks());

  it("shows only the horse module to the horse worker", async () => {
    render(<App />);
    expect((await screen.findByText("Адуу")).closest("button")).toHaveClass("home-card");
    expect(screen.getByAltText("Адууны модуль")).toHaveAttribute("src", "/module-icons/horse.png");
    expect(screen.queryByRole("button", { name: /Үхэр/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Анализ/ })).not.toBeInTheDocument();
  });
});
