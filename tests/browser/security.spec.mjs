import { test, expect } from "@playwright/test";

const user = { id: "00000000-0000-0000-0000-000000000001", email: "synthetic@example.test", aud: "authenticated", role: "authenticated", app_metadata: {}, user_metadata: {} };
const result = { credit_score: 700, default_probability: 0.2, risk_band: "LOW", key_factors: ["Synthetic estimate"], model: "xgboost" };
const config = { configured: true, supabase_url: "https://example.supabase.co", supabase_anon_key: "sb_publishable_dummy",
  policy_version: "2026-10-08-research-v1", captcha_site_key: "", signup_enabled: true };
async function setup(page, { session = false, enabled = true } = {}) {
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.route("https://example.supabase.co/**", route => route.fulfill({ status: 400, contentType: "application/json", body: JSON.stringify({ msg: "Invalid login credentials", error_code: "invalid_credentials" }) }));
  await page.route("**/api/config", route => route.fulfill({ json: { ...config, signup_enabled: enabled } }));
  await page.route("**/api/account", route => route.fulfill({ json: { accepted: true, policy_version: config.policy_version } }));
  await page.route("**/api/history**", route => route.fulfill({ json: [] }));
  if (session) {
    const now = Math.floor(Date.now()/1000);
    const claims = Buffer.from(JSON.stringify({ sub: user.id, exp: now+3600, role: "authenticated", aud: "authenticated" })).toString("base64url");
    await page.addInitScript(data => sessionStorage.setItem("creditsure-auth", JSON.stringify(data)), {
      access_token: `header.${claims}.signature`, refresh_token: "fake-refresh", token_type: "bearer", expires_in: 3600, expires_at: now+3600, user
    });
  }
  return errors;
}

test("local SDK passes SRI and closed registration is communicated", async ({ page }) => {
  const errors = await setup(page, { enabled: false });
  await page.goto("/signup");
  await expect(page.locator("#auth-alert")).toContainText("temporarily closed");
  await expect(page.locator("#auth-submit")).toBeDisabled();
  expect(await page.evaluate(() => Boolean(window.supabase?.createClient))).toBe(true);
  expect(errors).toEqual([]);
});

test("existing short passwords reach provider and receive safe feedback", async ({ page }) => {
  const errors = await setup(page);
  let requests = 0;
  await page.route("https://example.supabase.co/auth/v1/token**", route => {
    requests++;
    return route.fulfill({ status: 400, contentType: "application/json", body: JSON.stringify({ msg: "Invalid login credentials", error_code: "invalid_credentials" }) });
  });
  await page.goto("/signin");
  await page.locator("#email").fill(user.email);
  await page.locator("#password").fill("short");
  await page.locator("#auth-submit").click();
  await expect(page.locator("#auth-alert")).toContainText("Invalid login credentials");
  expect(requests).toBe(1);
  expect(errors).toEqual([]);
});

test("failed assessment retry preserves request ID and safe browser storage", async ({ page }) => {
  const errors = await setup(page, { session: true });
  const keys = [];
  await page.route("**/api/predict", async route => {
    keys.push(route.request().headers()["idempotency-key"]);
    expect(route.request().postDataJSON().research_confirmed).toBe(true);
    return keys.length === 1 ? route.fulfill({ status: 503, json: { detail: "Synthetic temporary outage" } }) : route.fulfill({ json: result });
  });
  await page.goto("/workspace");
  await expect(page.locator("#assess-button")).toBeEnabled();
  for (const [id,value] of Object.entries({ applicant_name: "Synthetic A", age_years: "30", annual_income: "600000", loan_amount: "250000", annuity_amount: "15000" })) await page.locator(`#${id}`).fill(value);
  await page.locator("#research-confirm").check();
  await page.locator("#assess-button").click();
  await expect(page.locator("#workspace-alert")).toContainText("Synthetic temporary outage");
  await page.locator("#assess-button").click();
  await expect(page.locator("#result-score")).toHaveText("700");
  expect(keys).toHaveLength(2); expect(keys[0]).toBe(keys[1]);
  expect(await page.evaluate(() => sessionStorage.getItem("creditsure-pending"))).toBeNull();
  expect(await page.evaluate(() => localStorage.getItem("creditsure-auth"))).toBeNull();
  expect(errors).toEqual([]);
});

test("non-JSON hosting errors are explained", async ({ page }) => {
  const errors = await setup(page);
  await page.route("**/api/config", route => route.fulfill({ status: 502, contentType: "text/html", body: "<h1>Unavailable</h1>" }));
  await page.goto("/signin");
  await expect(page.locator("#auth-alert")).toContainText("unexpected response");
  expect(errors).toEqual([]);
});

test("query parameter alone cannot enable recovery mode for an existing session", async ({ page }) => {
  const errors = await setup(page, { session: true });
  await page.goto("/signin?recovery=1");
  await expect(page.locator("#auth-alert")).toContainText("missing or expired");
  await expect(page.locator("#auth-submit")).toBeDisabled();
  expect(errors).toEqual([]);
});

test("provider recovery event enables a valid reset link", async ({ page }) => {
  const errors = await setup(page);
  let changes = 0;
  await page.route("https://example.supabase.co/auth/v1/user**", route => {
    if (route.request().method() === "PUT") changes++;
    return route.fulfill({ json: { ...user, email_confirmed_at: "2026-10-08T00:00:00Z" } });
  });
  const now = Math.floor(Date.now()/1000);
  const header = Buffer.from(JSON.stringify({ alg: "HS256", typ: "JWT" })).toString("base64url");
  const claims = Buffer.from(JSON.stringify({ sub: user.id, exp: now+3600, iat: now, role: "authenticated", aud: "authenticated" })).toString("base64url");
  const fragment = new URLSearchParams({ access_token: `${header}.${claims}.c2lnbmF0dXJl`, refresh_token: "fake-refresh", expires_in: "3600", token_type: "bearer", type: "recovery" });
  await page.goto(`/signin?recovery=1#${fragment}`);
  await expect(page.locator("#auth-submit")).toBeEnabled();
  await page.locator("#password").fill("Synthetic-new-password-123!");
  await page.locator("#confirm-password").fill("Synthetic-new-password-123!");
  await page.locator("#auth-submit").click();
  await expect(page.locator("#auth-alert")).toContainText("Your password has been updated");
  expect(changes).toBe(1); expect(errors).toEqual([]);
});
