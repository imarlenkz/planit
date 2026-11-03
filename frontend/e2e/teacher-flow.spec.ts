import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

/**
 * Teacher happy path:
 * login → create БЖБ → answer key → upload scanned PDF → automatic check → review a doubtful answer → export.
 * Requires demo data (SEED_DEMO=true): teacher@planit.kz / demo12345, class 5А, subject Математика,
 * and the seeded "Математика БЖБ №2" whose key is copied into the new assessment.
 */
const EMAIL = process.env.E2E_EMAIL || "teacher@planit.kz";
const PASSWORD = process.env.E2E_PASSWORD || "demo12345";

async function csrfHeaders(page: Page) {
  const cookies = await page.context().cookies();
  const csrf = cookies.find((c) => c.name === "csrf_token")?.value ?? "";
  return { "X-CSRF-Token": csrf };
}

async function json(req: APIRequestContext, url: string) {
  const r = await req.get(url);
  expect(r.ok(), `${url} → ${r.status()}`).toBeTruthy();
  return r.json();
}

test("teacher: create → upload → review → export", async ({ page }) => {
  // 1. login
  await page.goto("/login");
  await page.locator("input[type=email]").fill(EMAIL);
  await page.locator("input[type=password]").fill(PASSWORD);
  await page.locator("button[type=submit]").click();
  await page.waitForURL("**/dashboard");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

  // 2. create a new БЖБ through the wizard
  const title = `E2E БЖБ ${Date.now()}`;
  await page.getByRole("button", { name: /Жаңа жұмыс жасау/ }).first().click();
  const dialog = page.getByRole("dialog");
  const selects = dialog.locator("select");
  await selects.nth(0).selectOption({ label: "Математика" });
  await selects.nth(1).selectOption({ label: "5А" });
  await dialog.getByPlaceholder("Математика БЖБ №2 — Жай бөлшектер").fill(title);
  await dialog.getByRole("button", { name: "Құру" }).click();
  await page.waitForURL(/\/assessment\/\d+/);
  const newId = Number(page.url().match(/assessment\/(\d+)/)![1]);

  // 3. answer key: reuse the seeded Math БЖБ key (the key editor itself is covered by API tests)
  const req = page.request;
  const list = await json(req, "/api/assessments?size=200");
  const source = list.items.find((a: any) => a.title.startsWith("Математика БЖБ №2"));
  expect(source, "seeded Math БЖБ").toBeTruthy();
  const src = await json(req, `/api/assessments/${source.id}`);
  const questions = src.questions.map(({ id: _id, ...q }: any) => ({ ...q, descriptors: q.descriptors.map(({ id: _d, ...d }: any) => d) }));
  const put = await req.put(`/api/assessments/${newId}/questions`, { data: questions, headers: await csrfHeaders(page) });
  expect(put.ok(), await put.text()).toBeTruthy();

  // 4. upload a scanned multi-page PDF (realistic demo scan generated for this assessment)
  const scan = await req.get(`/api/demo/sample-scan/${newId}`);
  expect(scan.ok()).toBeTruthy();
  const file = path.join(os.tmpdir(), `planit-e2e-${newId}.pdf`);
  fs.writeFileSync(file, await scan.body());

  await page.goto(`/assessment/${newId}?tab=scan`);
  await page.locator("input[type=file][multiple]").setInputFiles(file);
  await page.getByRole("button", { name: /Автоматты тексеру/ }).click();

  // progress → done
  const openReview = page.getByRole("link", { name: /Тексеруге өту/ });
  await expect(openReview).toBeVisible({ timeout: 200_000 });
  await openReview.click();
  await page.waitForURL(/\/review\?assessment=/);

  // 5. review: open the first work and accept its selected answer
  const subs = await json(req, `/api/assessments/${newId}/submissions`);
  expect(subs.length).toBeGreaterThan(0);
  await page.goto(`/submissions/${subs[0].id}`);
  await expect(page.getByRole("button", { name: "Қабылдау" })).toBeVisible();
  await page.getByRole("button", { name: "Қабылдау" }).click();
  await expect(page.getByText("Сақталды").first()).toBeVisible();

  // approve all confident results in one click
  await page.goto(`/review?assessment=${newId}`);
  await page.getByRole("button", { name: /Барлық сенімді нәтижелерді бекіту/ }).click();

  // 6. results & export
  const results = await json(req, `/api/assessments/${newId}/results`);
  expect(results.students.length).toBe(subs.length);

  await page.goto(`/reports?assessment=${newId}`);
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: "Жүктеп алу" }).first().click(),
  ]);
  expect(download.suggestedFilename()).toMatch(/\.xlsx$/);

  // cleanup
  await req.delete(`/api/assessments/${newId}`, { headers: await csrfHeaders(page) });
});
