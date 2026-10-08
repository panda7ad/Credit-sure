import { defineConfig } from "@playwright/test";
import { existsSync } from "node:fs";
const local = process.platform === "win32" ? ".venv-security/Scripts/python.exe" : ".venv-security/bin/python";
const python = existsSync(local) ? local : "python";
const command = process.platform === "win32" ? `"${python.replaceAll("/", "\\")}"` : python;
export default defineConfig({
  testDir: "./tests/browser", workers: 1, timeout: 30000,
  use: { baseURL: "http://127.0.0.1:8765", browserName: "chromium" },
  webServer: { command: `${command} -m uvicorn app.main:app --host 127.0.0.1 --port 8765`,
    url: "http://127.0.0.1:8765/api/health", timeout: 60000, reuseExistingServer: false,
    env: { APP_ENV: "development", ALLOWED_HOSTS: "127.0.0.1", SUPABASE_URL: "", SUPABASE_ANON_KEY: "", SUPABASE_SECRET_KEY: "", REDIS_URL: "" } }
});
