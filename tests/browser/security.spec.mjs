import { test, expect } from "@playwright/test";
const result = { credit_score: 700, default_probability: 0.2, risk_band: "LOW", key_factors: ["Synthetic estimate"] };
async function fill(page, name = "Synthetic applicant") {
  for (const [id, value] of Object.entries({ applicant_name: name, age_years: "30", annual_income: "600000", loan_amount: "250000", annuity_amount: "15000" })) await page.locator(`#${id}`).fill(value);
  await page.locator("#research-confirm").check();
}
test("calculator opens without accounts", async ({ page }) => {
  const errors = []; page.on("pageerror", e => errors.push(e.message));
  await page.goto("/");
  await expect(page.getByText("Sign in", { exact: true })).toHaveCount(0);
  await page.locator(".header-actions a").click();
  await expect(page.locator("#assessment-form")).toBeVisible();
  await expect(page.locator("#history")).toHaveCount(0);
  expect(errors).toEqual([]);
});
test("real public API returns result without credentials", async ({ page }) => {
  await page.goto("/workspace"); await fill(page);
  const pending = page.waitForRequest("**/api/predict");
  await page.locator("#assess-button").click();
  expect((await pending).headers().authorization).toBeUndefined();
  await expect(page.locator("#result-output")).toBeVisible();
  await expect(page.locator("#result-score")).toHaveText(/\d{3}/);
  await expect(page.locator("#workspace-alert")).toContainText("Nothing was saved");
});
test("refresh clears result and no browser data is saved", async ({ page }) => {
  await page.route("**/api/predict", route => route.fulfill({ json: result }));
  await page.goto("/workspace"); await fill(page); await page.locator("#assess-button").click();
  await expect(page.locator("#result-output")).toBeVisible();
  expect(await page.evaluate(() => [localStorage.length, sessionStorage.length])).toEqual([0, 0]);
  await page.reload(); await expect(page.locator("#result-output")).toBeHidden();
});
test("untrusted result text does not execute", async ({ page }) => {
  await page.route("**/api/predict", route => route.fulfill({ json: { ...result, key_factors: ['<img src=x onerror="window.injected=true">'] } }));
  await page.goto("/workspace"); await fill(page, '<script>window.injected=true</script>'); await page.locator("#assess-button").click();
  await expect(page.locator("#result-name")).toHaveText('<script>window.injected=true</script>');
  await expect(page.locator("#result-factors img")).toHaveCount(0);
  expect(await page.evaluate(() => window.injected)).toBeUndefined();
});
test("rate limit shows retry guidance and restores control", async ({ page }) => {
  await page.route("**/api/predict", route => route.fulfill({ status: 429, headers: { "Retry-After": "60" }, json: { detail: "Too many requests." } }));
  await page.goto("/workspace"); await fill(page); await page.locator("#assess-button").click();
  await expect(page.locator("#workspace-alert")).toContainText("60 seconds");
  await expect(page.locator("#assess-button")).toBeEnabled();
  await expect(page.locator("#result-output")).toBeHidden();
});
test("old signup link redirects to calculator", async ({ page }) => {
  await page.goto("/signup"); await expect(page).toHaveURL(/\/workspace$/);
  await expect(page.locator("#assessment-form")).toBeVisible();
});
