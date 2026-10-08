# First deployment: required account-side setup

The code is hardened, but these settings cannot be applied by editing files. Keep `PUBLIC_SIGNUP_ENABLED=false` and `LAUNCH_SETTINGS_REVIEWED=false` until the checklist is complete. Never paste a secret into chat, public configuration, or GitHub.

## 1. Supabase migration and credentials

1. Back up your current Supabase database. Review `supabase/schema.sql`, then run it in SQL Editor. It removes existing policies on `credit_assessments`, allows owner-only reads, removes direct browser writes/deletes, and adds backend-only consent, quota and idempotency functions. Existing records are retained; they have no trusted model provenance until a new assessment is created. Application saving requires the migration AND the backend secret.
2. In Project Settings > API Keys, obtain the public publishable/anon key and a **separate server-only secret/service-role key**. The browser still receives only the public key. Set `SUPABASE_SECRET_KEY` in Render Environment and local `.env`; never replace `SUPABASE_ANON_KEY` with it.
3. Enable pg_cron in Database > Extensions and apply `supabase/retention.sql`. Confirm the `credit-sure-retention` job is active and its executions succeed. The job permanently deletes assessments older than 90 days; back up and review before enabling it.
4. Inspect Supabase Security Advisor, all exposed tables and storage buckets. Test with two synthetic accounts: owner-only read, forbidden direct INSERT/UPDATE/DELETE, forbidden browser calls to writer RPCs, and rejected anonymous reads. This repo's local PostgreSQL tests do not verify your actual project's policies.

## 2. Authentication and email delivery

1. Enable email/password login and email confirmation. Configure a minimum 12-character password policy at Supabase, not just in the form. Enable leaked-password protection if available on your plan.
2. Keep new user signup disabled in Supabase while preparing launch. The app's signup flag only hides its own signup flow; users can call the provider directly.
3. Create a Cloudflare Turnstile widget for your final hostname (and localhost if used). Configure its **secret** in Supabase Auth > Bot and Abuse Protection; configure only its **public site key** as `TURNSTILE_SITE_KEY` in the app. Confirm signup, sign-in and recovery succeed with challenges and fail when direct API calls omit them. Choose widget settings consistent with the form integration.
4. Review Supabase Auth request/email limits. Application request limits do not cover direct provider requests.
5. Configure a real SMTP sender. Verify its required SPF/DKIM records and publish an appropriate DMARC policy. Test delivered confirmation/reset messages, including spam folders.
6. Set Site URL to `https://YOUR-SITE.onrender.com` (or your custom domain) and allow these exact callbacks:
   - `https://YOUR-SITE.onrender.com/workspace`
   - `https://YOUR-SITE.onrender.com/signin?recovery=1`
   Keep exact localhost callbacks separately if developing locally; do not use a wildcard production callback.
7. Review access-token/session lifetime, secure email/password changes and session revocation settings. Test expired and reused confirmation/reset links. Account deletion requires a password authentication within five minutes; the UI provides a reauthentication link.

## 3. Render service and shared rate limits

1. Upload the contents of the inner `alternative_credit_scoring` directory as the root of a private GitHub repo, including `.github`, `models/credit_model.joblib`, `models/metadata.json`, `models/manifest.json`, the vendored SDK, and lockfiles. `.env` must remain excluded. GitHub now tracks the three specific model files without force-adding every model file. An extra wrapper directory prevents GitHub from discovering the nested `.github/workflows` unless you move it to the repository root and adjust paths.
2. Create a Docker Web Service using the inner application directory as the root directory if your repository includes an outer wrapper folder. The Dockerfile uses Python 3.14, verifies model assets exist, installs serving dependencies, and runs as a non-root user.
3. Create a Redis-compatible service reachable from your app. Use Render's private connection where available, or a TLS `rediss://` external connection. Do not publicly expose an unauthenticated Redis service. Set `REDIS_URL` in Render. Production fails closed when shared limiting is unavailable; in-memory limiting is development-only.
4. Configure Environment variables:

| Variable | Value |
| --- | --- |
| `APP_ENV` | `production` |
| `ALLOWED_HOSTS` | Exact hostname, e.g. `credit-sure.onrender.com,127.0.0.1`; include localhost IP for container healthchecks and any custom hostname. No `*`. |
| `SUPABASE_URL` | Your project's HTTPS `*.supabase.co` origin |
| `SUPABASE_ANON_KEY` | Public publishable/anon key |
| `SUPABASE_SECRET_KEY` | Server-only secret/service-role key |
| `REDIS_URL` | Private/TLS Redis connection string |
| `RATE_LIMIT_SALT` | Random secret of at least 32 characters, identical across app instances |
| `TRUSTED_PROXY_CIDRS` | Only the actual trusted ingress proxy networks; otherwise leave empty |
| `TURNSTILE_SITE_KEY` | Public Turnstile widget key |
| `PUBLIC_SIGNUP_ENABLED` | `false` until launch checks pass |
| `LAUNCH_SETTINGS_REVIEWED` | `false` until account-side review is complete |

5. Configure Render's health check path as `/api/ready`; it returns 503 until required model/config/database/limiter/launch checks pass. `/api/health` is liveness only. Get the target hostname from the service dashboard and complete required settings before deploying; otherwise the initial health check is expected to fail. Inspect build logs to diagnose failures. Do not claim a healthy launch from liveness alone.
6. Uvicorn does not trust forwarded IPs automatically. Without confirmed proxy CIDRs, IP limits conservatively group requests by the proxy; account limits remain separate. Do not fix this by trusting all IP ranges or arbitrary browser-supplied headers. Confirm Render's current proxy topology/header behavior before populating CIDRs.
7. Render manages TLS certificates. Verify HTTP-to-HTTPS behavior, certificate validity, no mixed content, and response security/cache headers on the deployed domain. Do not buy a separate certificate for the standard managed setup.

## 4. Privacy, backups, monitoring and owner access

- Operator: Adarsh-Patel; support/privacy contact: youngseldon77@gmail.com. The pages now describe synthetic-data-only research use, 90-day assessment retention, account export/deletion and tab-scoped sessions. This is not a compliance certification. Review actual regions, provider processing terms and applicable requirements before accepting real customer/financial information.
- Select and record hosting/database regions, provider backup/log retention and recovery objectives. Configure backups on an appropriate plan and perform a restore test with synthetic data. Live deletion does not instantly delete backups.
- The account exporter includes up to 500 saved assessments, matching the new account quota. If pre-migration accounts already have more than 500 records, export those fully in SQL Editor before migrating/using the app exporter; the legacy exporter cannot be assumed complete for those accounts.
- Enable MFA on GitHub, Render, Supabase, Cloudflare and SMTP provider accounts. Limit collaborator privileges; keep an offline recovery method.
- Set external uptime alerts, error/latency alerts, failed auth/429 monitoring, database-storage and budget alerts. No alert destination or paid service was configured automatically.
- Review provider access logs for retention and sensitive metadata. App logging records a request ID and exception type, not full financial input, passwords or bearer tokens. Avoid debug logging in production.
- If a secret leaks: close registration, revoke/rotate the leaked secret, assess data access, restore service with new secrets, document the incident and notify affected users as appropriate. Deleting a GitHub file does not remove a secret from history.

## 5. Validate and open registration

Locally run:

```powershell
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
npm ci --ignore-scripts
node scripts/test_database.mjs
npm audit
python -m pip_audit --vulnerability-service osv
npx playwright install chromium
npx playwright test
```

CI repeats tests/audits and builds/smoke-tests the Linux image. Docker is not installed on the inspected computer, so that image cannot be claimed locally verified. The CI checks become active after uploading to GitHub; verify their results before deploying.

On the deployed environment, test two-account isolation, signup/confirmation/sign-in/reset/sign-out, policy acceptance, saving/retry behavior, request limits, export, individual deletion, whole-account deletion and backup restore. Test provider outages safely with synthetic data. Update `LAUNCH_SETTINGS_REVIEWED=true` only after required provider settings are verified. Then enable Supabase signups and `PUBLIC_SIGNUP_ENABLED=true`. Start with a small research audience and synthetic assessments.
