import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CattlePage, HorsePage } from "./Animals";

const apiMock = vi.hoisted(() => vi.fn());
vi.mock("../api/client", async (source) => {
  const actual = await source<typeof import("../api/client")>();
  return { ...actual, api: apiMock };
});
vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({
    user: { id: "owner", username: "Шүрэнчулуун", role: "OWNER", allowed_modules: ["horses", "cattle"], must_change_code: false },
  }),
}));

const image = (id: string, kind: "MAIN" | "LAYOUT") => ({
  id,
  kind,
  original_filename: `${kind.toLowerCase()}.png`,
  url: `/api/v1/images/${id}/content?expires=9999999999&signature=test`,
  width: 600,
  height: 600,
});

const horse = {
  id: "horse-1", group_id: "group-1", group_name: "Архив", color: "Хээр", birth_year: 2020,
  age_years: 6, age_category: "Их нас", display_label: "Хээр морь", sex: "MALE", male_status: "GELDING",
  current_status: "ARCHIVED", mother_id: null, mother_label: null, father_id: null, father_label: null,
  additional_info: null, archived_at: "2026-07-16T00:00:00Z", archive_note: "test", unnatural_loss: false,
  version: 2, images: [image("horse-main", "MAIN"), image("horse-layout", "LAYOUT")],
  main_image: image("horse-main", "MAIN"), layout_image: image("horse-layout", "LAYOUT"), indent: 0, relation_note: null,
};

const cattle = {
  id: "cattle-1", ear_tag: "ARCHIVE-1", color: "Алаг", birth_year: 2020, age_years: 6,
  age_category: "Бүдүүн үнээ", sex: "FEMALE", is_bull: false, current_status: "ARCHIVED",
  mother_id: null, mother_label: null, additional_info: null, archived_at: "2026-07-16T00:00:00Z",
  archive_note: "test", unnatural_loss: false, version: 2,
  images: [image("cattle-main", "MAIN"), image("cattle-layout", "LAYOUT")],
  main_image: image("cattle-main", "MAIN"), layout_image: image("cattle-layout", "LAYOUT"),
};

describe("animal archive profiles", () => {
  beforeEach(() => {
    apiMock.mockReset();
    apiMock.mockImplementation((path: string) => {
      if (path === "/api/v1/horses/groups") return Promise.resolve([{ id: "group-1", name: "Архив", description: null, is_active: true, version: 1 }]);
      if (path.startsWith("/api/v1/horses/statistics") || path.startsWith("/api/v1/cattle/statistics")) return Promise.resolve({ total: 0, eligible_males: 0, eligible_females: 0, offspring: 0, breeding_males: 0 });
      if (path === "/api/v1/horses/horse-1") return Promise.resolve({ ...horse, main_image: { ...horse.main_image, url: `${horse.main_image.url}&refreshed=1` } });
      if (path.startsWith("/api/v1/horses?")) return Promise.resolve([horse]);
      if (path === "/api/v1/cattle/cattle-1") return Promise.resolve(cattle);
      if (path.startsWith("/api/v1/cattle?")) return Promise.resolve([cattle]);
      return Promise.resolve({ status: "deleted" });
    });
  });

  it("renders a signed horse profile, refreshes an expired URL, and confirms permanent deletion", async () => {
    render(<HorsePage onBack={vi.fn()} />);
    fireEvent.click(await screen.findByRole("button", { name: /Хээр морь/ }));
    const profile = await screen.findByAltText("Адуу үндсэн зураг");
    expect(profile).toHaveAttribute("src", expect.stringContaining("http://localhost:8000/api/v1/images/horse-main"));
    fireEvent.error(profile);
    await waitFor(() => expect(apiMock).toHaveBeenCalledWith("/api/v1/horses/horse-1"));
    fireEvent.click(screen.getByRole("button", { name: /Бүрмөсөн устгах/ }));
    const confirmation = screen.getByLabelText(/УСТГАХ гэж бичнэ үү/);
    const submit = screen.getAllByRole("button", { name: "Бүрмөсөн устгах" }).at(-1)!;
    expect(submit).toBeDisabled();
    fireEvent.change(confirmation, { target: { value: "УСТГАХ" } });
    fireEvent.click(submit);
    await waitFor(() => expect(apiMock).toHaveBeenCalledWith(
      "/api/v1/horses/horse-1/permanent",
      expect.objectContaining({ method: "DELETE", body: JSON.stringify({ confirmation: "УСТГАХ" }) }),
    ));
  });

  it("renders the cattle main and layout profile images", async () => {
    render(<CattlePage onBack={vi.fn()} />);
    fireEvent.click(await screen.findByRole("button", { name: /ARCHIVE-1/ }));
    expect(await screen.findByAltText("Үхэр үндсэн зураг")).toBeVisible();
    expect(screen.getByAltText("Үхэр зургийн нийлмэл харагдац")).toBeVisible();
    expect(screen.getByRole("button", { name: /Бүрмөсөн устгах/ })).toBeVisible();
  });
});
