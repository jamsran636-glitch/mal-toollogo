import { expect, test, type Page } from "@playwright/test";

async function login(page: Page, username: string, code: string) {
  await page.goto("/");
  await page.getByLabel("Нэвтрэх нэр").fill(username);
  await page.getByLabel("Нэвтрэх код").fill(code);
  await page.getByRole("button", { name: "Нэвтрэх", exact: true }).click();
  await expect(page.getByLabel("Нэвтрэх нэр")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Мал тооллого" })).toBeVisible();
}

test("owner completes core livestock and owner workflows", async ({ page }, testInfo) => {
  test.setTimeout(90_000);
  test.skip(testInfo.project.name !== "chromium", "core mutation journey runs once on desktop");
  const pageErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  await login(page, "Шүрэнчулуун", "99104047");
  for (const label of ["Адуу", "Үхэр", "Хонь", "Анализ"]) {
    await expect(page.getByText(label, { exact: true }).first()).toBeVisible();
  }

  await page.getByText("Адуу", { exact: true }).first().click();
  await page.getByPlaceholder("Азарганы шинэ бүлэг").fill("E2E бүлэг A");
  await page.getByRole("button", { name: "Бүлэг нэмэх" }).click();
  await page.getByPlaceholder("Азарганы шинэ бүлэг").fill("E2E бүлэг B");
  await page.getByRole("button", { name: "Бүлэг нэмэх" }).click();
  await page.getByRole("button", { name: /Адуу нэмэх/ }).click();
  await page.getByLabel("Бүлэг").selectOption({ label: "E2E бүлэг A" });
  await page.getByLabel("Зүс").fill("Хээр");
  await page.getByLabel("Төрсөн он").fill("2024");
  await page.getByLabel("Хүйс").selectOption("MALE");
  await page.getByRole("button", { name: "Хадгалах" }).click();
  await page.getByText(/Хээр/).last().click();
  await page.getByRole("button", { name: /Засах/ }).click();
  await page.getByLabel("Зүс").fill("Бор хээр");
  await page.getByRole("button", { name: "Хадгалах" }).click();
  await page.getByText(/Бор хээр/).last().click();
  await page.getByRole("button", { name: "Бүлэг солих" }).click();
  await page.getByLabel("Шинэ бүлэг").selectOption({ label: "E2E бүлэг B" });
  await page.getByLabel("Шалтгаан").fill("E2E шилжүүлэг");
  await page.getByRole("button", { name: "Баталгаажуулах" }).click();
  await page.getByText(/Бор хээр/).last().click();
  await page.getByRole("button", { name: "Архивлах" }).click();
  await page.getByLabel("Тайлбар").fill("E2E архив");
  await page.getByRole("button", { name: "Баталгаажуулах" }).click();
  await page.getByRole("button", { name: "Архив", exact: true }).click();
  await page.getByText(/Бор хээр/).last().click();
  await page.getByRole("button", { name: /Сэргээх/ }).click();
  await page.getByLabel("Буцах").click();

  await page.getByText("Үхэр", { exact: true }).first().click();
  await page.getByRole("button", { name: /Үхэр нэмэх/ }).click();
  await page.getByLabel("Ээмэгний дугаар").fill("E2E-001");
  await page.getByLabel("Зүс").fill("Алаг");
  await page.getByRole("button", { name: "Хадгалах" }).click();
  await page.getByRole("button", { name: /E2E-001/ }).click();
  await page.getByRole("button", { name: /Засах/ }).click();
  await page.getByLabel("Зүс").fill("Хар алаг");
  await page.getByRole("button", { name: "Хадгалах" }).click();
  await page.getByRole("button", { name: /E2E-001/ }).click();
  await page.getByRole("button", { name: "Архивлах" }).click();
  await page.getByLabel("Тайлбар").fill("E2E cattle archive");
  await page.getByRole("button", { name: "Баталгаажуулах" }).click();
  await page.getByRole("button", { name: "Архив", exact: true }).click();
  await page.getByRole("button", { name: /E2E-001/ }).click();
  await page.getByRole("button", { name: /Сэргээх/ }).click();
  await page.getByLabel("Буцах").click();

  await page.getByText("Хонь", { exact: true }).first().click();
  await page.getByRole("button", { name: /Тооллого/ }).click();
  await page.getByLabel("Нас бие гүйцсэн эр хонь (хуц тусдаа)").fill("10");
  await page.getByRole("button", { name: "Хадгалах" }).click();
  await expect(page.getByRole("cell", { name: "10" }).first()).toBeVisible();
  await page.getByRole("button", { name: "Засах" }).first().click();
  await page.getByLabel("Нас бие гүйцсэн эр хонь (хуц тусдаа)").fill("11");
  await page.getByLabel("Зассан шалтгаан").fill("E2E correction");
  await page.getByRole("button", { name: "Хадгалах" }).click();
  await page.getByRole("button", { name: "Оройн тоо" }).click();
  await page.getByRole("button", { name: /Тооллого/ }).click();
  await page.getByLabel("Хонины нийт").fill("50");
  await page.getByLabel("Ямааны нийт").fill("20");
  await page.getByRole("button", { name: "Хадгалах" }).click();
  await page.getByLabel("Буцах").click();

  await page.getByText("Анализ", { exact: true }).first().click();
  await expect.poll(() => pageErrors).toEqual([]);
  await expect(page.getByRole("heading", { name: "Энэ жилийн ашиг" })).toBeVisible();
  const countsToggle = page.getByLabel("Малын тоо");
  await countsToggle.uncheck();
  await countsToggle.check();
  await page.getByRole("button", { name: "Орлого, зарлага" }).click();
  await page.getByRole("button", { name: /Бүртгэх/ }).click();
  await page.getByLabel("Дүн").fill("100000");
  await page.getByLabel("Тайлбар").fill("E2E income");
  await page.getByRole("button", { name: "Хадгалах" }).click();
  await page.getByRole("button", { name: "Зарлага" }).click();
  await page.getByRole("button", { name: /Бүртгэх/ }).click();
  await page.getByLabel("Дүн").fill("25000");
  await page.getByLabel("Тайлбар").fill("E2E expense");
  await page.getByRole("button", { name: "Хадгалах" }).click();
  await page.getByLabel("Буцах").click();
  await page.getByRole("button", { name: "Малчид" }).click();
  await page.getByRole("button", { name: /Малчин/ }).click();
  await page.getByLabel("Овог").fill("E2E");
  await page.getByLabel("Нэр").fill("Малчин");
  await page.getByLabel("Регистр").fill("AA00112233");
  await page.getByRole("button", { name: "Хадгалах" }).click();
  await page.getByRole("button", { name: "Засах" }).click();
  await page.getByLabel("Нэр").fill("Малчин зассан");
  await page.getByRole("button", { name: "Хадгалах" }).click();
  await page.getByLabel("Буцах").click();
  await page.getByRole("button", { name: "Өөрчлөлтийн түүх" }).click();
  await expect(page.getByRole("heading", { name: /CREATE/ }).first()).toBeVisible();
  await page.getByLabel("Буцах").click();
  await page.getByRole("button", { name: "Тайлан, backup" }).click();
  const reportDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: /Excel/ }).click();
  await reportDownload;
  const backupDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: /^Backup$/ }).click();
  await backupDownload;
  await page.getByRole("button", { name: /Backup сэргээх/ }).click();
  await page.getByLabel("Backup ZIP").setInputFiles({ name: "invalid.zip", mimeType: "application/zip", buffer: Buffer.from("invalid") });
  await page.getByLabel(/RESTORE гэж бичнэ үү/).fill("RESTORE");
  await page.getByRole("button", { name: "Сэргээх", exact: true }).click();
  await expect(page.getByText(/хүчингүй|Сэргээж чадсангүй/)).toBeVisible();
});

for (const account of [
  { username: "Адуучин", code: "00000000", visible: "Адуу", hidden: ["Үхэр", "Хонь", "Анализ"] },
  { username: "Үхэрчин", code: "00000000", visible: "Үхэр", hidden: ["Адуу", "Хонь", "Анализ"] },
  { username: "Хоньчин", code: "00000000", visible: "Хонь", hidden: ["Адуу", "Үхэр", "Анализ"] },
]) {
  test(`${account.username} sees only the allowed module`, async ({ page }) => {
    await login(page, account.username, account.code);
    await expect(page.getByText(account.visible, { exact: true }).first()).toBeVisible();
    for (const label of account.hidden) await expect(page.getByText(label, { exact: true })).toHaveCount(0);
  });
}

test("protected APIs reject cross-role access and sheep mortality", async ({ request }) => {
  const loginResponse = await request.post("http://127.0.0.1:8001/api/v1/auth/login", { data: { username: "Хоньчин", code: "00000000" } });
  const token = (await loginResponse.json()).access_token as string;
  const auth = { Authorization: `Bearer ${token}` };
  expect((await request.get("http://127.0.0.1:8001/api/v1/horses", { headers: auth })).status()).toBe(403);
  expect((await request.get("http://127.0.0.1:8001/api/v1/finance", { headers: auth })).status()).toBe(403);
  expect((await request.post("http://127.0.0.1:8001/api/v1/small-livestock/losses", { headers: auth, data: { loss_date: "2026-07-16", livestock_type: "SHEEP", animal_category: "Хонь", quantity: 1, reason: "blocked" } })).status()).toBe(403);
});

test("PWA shell works offline without caching authenticated API responses", async ({ page, context }) => {
  const pageErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  await page.goto("/");
  await expect.poll(async () => page.evaluate(() => Boolean(navigator.serviceWorker.controller))).toBe(true);
  const manifest = await page.request.get("/manifest.webmanifest");
  expect(manifest.ok()).toBeTruthy();
  const cachedBeforeOffline = await page.evaluate(async () => {
    const keys = await caches.keys();
    const requests = await Promise.all(keys.map(async (key) => (await caches.open(key)).keys()));
    return requests.flat().map((request) => request.url);
  });
  expect(cachedBeforeOffline.some((url) => url.endsWith(".js"))).toBe(true);
  expect(cachedBeforeOffline.some((url) => url.endsWith(".css"))).toBe(true);
  await context.setOffline(true);
  await expect(page.getByText(/Офлайн горим/)).toBeVisible();
  await page.reload();
  expect(pageErrors).toEqual([]);
  await expect(page.getByRole("heading", { name: "Мал тооллого" })).toBeVisible();
  const cachedUrls = await page.evaluate(async () => {
    const keys = await caches.keys();
    const requests = await Promise.all(keys.map(async (key) => (await caches.open(key)).keys()));
    return requests.flat().map((request) => request.url);
  });
  expect(cachedUrls.every((url) => !new URL(url).pathname.startsWith("/api/"))).toBe(true);
});
