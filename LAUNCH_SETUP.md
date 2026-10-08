# Launch the public calculator

No signup, login, saved history, Supabase, SMTP or Turnstile is required for new assessments.
The public calculator processes synthetic scenario inputs in memory. Existing Supabase
accounts/records are not deleted automatically and are not served through the public app.
Disable new registrations in that former Supabase project and retain access to handle
legitimate data access/deletion requests. Keep its retention job active if configured.

1. Check GitHub Actions on the current commit: application and browser tests, Docker
   security regressions, model integrity and blocking dependency/container scans must pass.
   Review the separate unfiltered OS findings report; the blocking only-fixed policy
   does not mean the image has no remaining vulnerabilities.
2. Render web service: main branch, Dockerfile path Dockerfile, context ., health /api/ready.
3. Create Render Key Value in the same region/workspace. Choose noeviction. Copy the
   private internal connection URL. Review charges before choosing a compute plan.
4. Add these Render environment variables, using Save only while completing setup:

| Name | Value |
|---|---|
| APP_ENV | production |
| ALLOWED_HOSTS | credit-sure.onrender.com,127.0.0.1 |
| REDIS_URL | Complete internal Key Value URL |
| RATE_LIMIT_SALT | Random private value of at least 32 characters |
| LAUNCH_SETTINGS_REVIEWED | true after the checks below |

Generate the salt with: `python -c "import secrets; print(secrets.token_hex(32))"`.
Leave TRUSTED_PROXY_CIDRS unset until the real proxy ranges are verified. The global
inference budgets remain effective even if proxy clients share a network identity.
Remove unused SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SECRET_KEY,
TURNSTILE_SITE_KEY and PUBLIC_SIGNUP_ENABLED from the Render web service.
Never put secrets in GitHub or chat. No local .env needs to be uploaded.

5. Before setting LAUNCH_SETTINGS_REVIEWED=true, confirm operator/contact privacy
   details, synthetic-only usage, hosting region and log retention, account MFA,
   Key Value private access/noeviction, a 32+ character salt and review of outstanding
   OS findings. Existing legacy records require their own retention/deletion handling.
6. Save and deploy once all variables are ready. /api/ready must return status ready.
   Missing Redis or launch configuration deliberately fails closed.
7. Test /workspace from an incognito browser: no signup, generate a synthetic result,
   refresh to clear it, check no saved history, and verify overloads show a clear error.
   The model is experimental and unsuitable for real credit decisions.

The server enforces 10 predictions/minute per observed network identity, shared global
budgets of 60/minute and 600/hour, two concurrent model calls, bounded inputs and 16 KiB
request bodies. These limits mitigate abuse but do not guarantee protection from all traffic.
