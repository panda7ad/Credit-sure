## Current public calculator ? 9 October 2026

The account-based flow below is historical. The current website has no signup,
login or saved history. Account/history endpoints are retired; new predictions
never call Supabase or persist assessment records. Supabase/SMTP/CAPTCHA are not
launch dependencies. Existing Supabase data is left untouched and still requires
operator-managed retention/access/deletion handling.

Public predictions retain strict input validation, body limits, two inference
slots, shared Redis network and global request budgets, no-store responses,
security headers and pinned model integrity. Production readiness requires Redis,
a 32-character minimum random salt and reviewed launch settings. Browser results
are not stored and disappear on refresh. All 23 Python checks, 6 browser checks
and 8 legacy SQL-isolation checks pass locally. The previously verified CPython
backports remain unchanged. Review the unfiltered OS findings separately; a green
only-fixed scan is not proof that all OS vulnerabilities are resolved.

# Credit-Sure pre-launch security review

## Remediation update, 8 October 2026

The findings below describe the pre-fix snapshot. Code remediation has since added patched serving dependencies and runtime pins, a locally served integrity-checked SDK, request/validation limits, shared Redis rate limits, response security/cache headers, bounded outbound/browser requests, idempotency, backend-only result creation, atomic database quotas, durable policy acceptance, model artifact integrity checks, export/deletion, retention SQL, non-root Docker serving and release checks. Operator/contact details are now Adarsh-Patel / youngseldon77@gmail.com, with synthetic-data-only policy pages. Legacy results are marked unverified.

Provider-dependent changes are documented in LAUNCH_SETUP.md and have NOT been applied to your Supabase/Render accounts. The SQL migration, server-only secret, Redis, CAPTCHA, SMTP, retention schedule, backups, owner MFA, alerts and live HTTPS/isolation checks must be configured/verified there. The hardened code is not a security/compliance certification. Docker is unavailable locally; the new GitHub workflow builds and scans the Linux image after upload.

Final local verification: 25 Python tests passed (including real trusted-model inference), 8 PostgreSQL migration/policy tests passed using PGlite, and 6 Chromium browser tests passed. Browser provider requests use synthetic mocks; they do not verify a real Supabase account or email delivery. Shared Redis behavior was exercised with a Redis-compatible test engine, including concurrent requests; a live Redis service remains to be checked. The installed Python environment scan covered 57 packages with no known advisories, and npm audit reported zero known vulnerabilities. Asset hashes, script integrity, and source secret checks passed. These results are dated 8 October 2026 and do not replace ongoing scans or the actual Linux image/provider checks.

Reviewed 8 October 2026. Scope: local application source, database setup SQL, browser code, Docker configuration, direct dependency advisories, selected framework advisories, and harmless local tests. No production deployment or Supabase dashboard was inspected. No live customer data or credentials were used. This review identifies observed issues and launch controls; it cannot establish that every vulnerability has been found.

Recommendation: fix the high-priority issues before opening registration to the public. First launch as a research demonstration using synthetic assessment data. Handling actual applicant financial data requires a separate privacy, security, and model-validation project.

## Evidence and limitations

- `python -m unittest discover -s tests -v`: all 6 existing tests passed. They verify application filters and mocked authenticated routing, not actual Supabase RLS enforcement.
- Anonymous GET requests to `/api/history` and `/api/history/{uuid}` returned 401 locally.
- `Applicant` accepted positive infinity for annual income and a 1,000,000-character education value. This is a validation gap, not proof of an account takeover.
- Local home-page responses had no Content-Security-Policy, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, or Strict-Transport-Security headers. Render may add some edge behavior; that has not been checked.
- `/openapi.json` returned 200. This is low-risk information exposure, not an authentication bypass.
- OSV was queried for all 16 pinned direct requirements. Advisory aliases were not counted as separate vulnerabilities. This was not a complete resolved-dependency or container-OS scan.
- Installed local versions differ from requirements: FastAPI 0.133.1 versus 0.115.6, Starlette 0.52.1 versus the deployment constraint below, Pydantic 2.12.5 versus 2.10.4, Uvicorn 0.41.0 versus 0.34.0, and python-multipart 0.0.29 versus 0.0.20. Local test success does not validate the Docker dependency set.
- No browser end-to-end test, Docker build, load test, real cross-account database test, provider configuration check, secret-history scan, backup restore, or certificate check was performed.

## Prioritized findings

### 1. High: deployment dependencies include a reachable file-serving advisory

Evidence: `requirements.txt` pins FastAPI 0.115.6. Its published dependency constraint is Starlette >=0.40.0,<0.42.0. That range falls within the affected range for GHSA-7f5h-v6xp-fcq8 / CVE-2025-62727, fixed in Starlette 0.49.1. `app/main.py:33,48,56` uses StaticFiles and FileResponse, the affected components. The deployment dependency chain therefore exposes the affected code path; an attack was not executed.

Impact: specially crafted unauthenticated Range headers can exhaust CPU and make the site unavailable.

Fix: upgrade FastAPI to a maintained compatible version that permits a patched Starlette; resolve and audit the complete dependency set in the exact deployment environment. Do not simply force an incompatible Starlette under the current FastAPI pin. Lock tested versions, build the Docker image, and exercise file serving, authentication, prediction, and history in it.

Source: https://github.com/Kludex/starlette/security/advisories/GHSA-7f5h-v6xp-fcq8

Additional direct dependency warnings:

| Dependency pin | Advisory | Exposure assessment / action |
| --- | --- | --- |
| python-dotenv 1.0.1 | GHSA-mf9w-mj56-hr94 | Fixed in 1.2.2. The earlier local-configuration change introduced this outdated pin. This app only calls load_dotenv, not the affected set_key/unset_key methods; the advisory is not a demonstrated remote exploit here. Upgrade the pin. |
| lightgbm 4.5.0 | GHSA-2586-f3p4-hq84 | Affected package; advisory fix is 4.6.0. Current model metadata names XGBoost. Remove LightGBM from the serving image if unnecessary, or update and test it. No reachable exploit was established. |
| python-multipart 0.0.20 | Multiple advisories, including GHSA-5rvq-cxj2-64vf and GHSA-wp53-j4wj-2cfg | Current routes accept JSON and do not define upload/form parsing. Remove this unused serving dependency, or upgrade to a version covering all current advisories. One querystring DoS advisory is fixed in 0.0.30; the arbitrary-file-write advisory requires nondefault upload configuration absent here. |
| Jinja2 3.1.5 | GHSA-cpwx-vrp4-4pq7 | Fixed in 3.1.6. App serves fixed HTML, not user-controlled templates. Remove if unused, or update. No template-injection route was found. |

Sources: https://github.com/advisories/GHSA-mf9w-mj56-hr94 ; https://github.com/advisories/GHSA-2586-f3p4-hq84 ; https://github.com/advisories/GHSA-5rvq-cxj2-64vf ; https://github.com/advisories/GHSA-wp53-j4wj-2cfg ; https://github.com/advisories/GHSA-cpwx-vrp4-4pq7

### 2. High: no application abuse limits or storage quotas

Evidence: `app/main.py` exposes prediction, history, and deletion routes without a limiter; each authenticated request makes a Supabase authentication call. Prediction also performs model inference and inserts a record. There are no account storage quotas. Signup is open in the browser; actual provider controls are unknown.

Impact: authenticated abuse can consume CPU, threads, database storage, outbound requests, and hosting budget. Invalid-token traffic also consumes upstream authentication capacity. Disabling buttons in JavaScript does not constrain API clients.

Fix: use a shared limiter for multiple workers/instances; add account limits after token verification and trusted client-IP/edge limits before expensive processing. Return 429 with Retry-After. Add daily assessment/storage quotas and concurrency limits. Configure Supabase Auth rate limits and CAPTCHA separately: app limits cannot protect direct calls to Supabase Auth or the exposed Data API. Do not trust arbitrary X-Forwarded-For headers when deriving client IPs.

Sources: https://supabase.com/docs/guides/auth/rate-limits ; https://supabase.com/docs/guides/auth/auth-captcha

### 3. High: request-size and input validation gaps

Evidence: `app/schemas.py:5,7,8,9,10` has unbounded strings and several unbounded numeric fields. Positive infinity and a million-character category were accepted in local schema probes. No application request-body cap exists. A name length check alone does not prevent a huge request from being read and parsed.

Impact: unnecessary memory/CPU consumption, malformed model inputs, unreliable estimates, and oversized stored JSON. JSON numeric overflow can produce nonfinite values even when explicit Infinity syntax is rejected by a parser.

Fix: enforce a small total request size before parsing, including streamed requests without Content-Length; return 413 for oversized bodies. Reject nonfinite numbers, impose documented numeric bounds, use category enums, cap all string lengths, and reject unexpected fields. Add meaningful tests for numeric overflow, chunked oversize requests, and invalid categories.

### 4. High for result integrity: users can insert arbitrary results directly into Supabase

Evidence: `supabase/schema.sql:25,28,36` grants INSERT to every authenticated user and only checks their user_id. `payload` and `result` are arbitrary JSONB, without shape/size/semantic constraints. The public key and a user's token enable direct Data API calls.

Impact: a user can create their own history rows containing invented model outputs, bypass application quotas/validation, and submit malformed records that break history rendering. This does NOT give permission to read another user's rows under the supplied policies, and does not alter the trained model.

Fix: decide whether history is authoritative model output. If it is, reserve writes for a backend-controlled path and preserve owner isolation explicitly. A server credential must remain server-only and requires careful authorization because it can bypass RLS. Database constraints, immutable server-set provenance, and quotas are also needed. Hiding the public key is not a fix. Do not revoke INSERT alone: the current backend writes with the same user token and would stop working.

Source: https://supabase.com/docs/guides/getting-started/api-keys

### 5. Medium: browser defenses and sensitive-response cache policy missing

Evidence: local responses lack the security headers above; `app/main.py` has no security/cache middleware. Personal assessment responses have no explicit no-store policy. `web/site.js:15` persists sessions in browser storage using the browser client defaults.

Impact: missing defense against injected scripts and framing; personal API responses can be retained by caches unless configured otherwise. If malicious JavaScript executes in this origin, it can read browser-accessible session tokens. No user-input-to-innerHTML XSS path was found in the reviewed code: dynamic data generally uses textContent.

Fix: add a tested CSP with restrictive script sources, frame-ancestors 'none', object-src 'none', and base-uri restrictions; add nosniff, frame protection, an appropriate Referrer-Policy and Permissions-Policy. Add Cache-Control: no-store to authenticated API responses. Deploy HTTPS and add HSTS after confirming production HTTPS/proxy behavior. Consider a server-mediated HttpOnly cookie session if the product's sensitivity requires it; a cookie migration also needs CSRF controls.

### 6. Medium: external script is trusted without integrity verification

Evidence: HTML pages load Supabase JS 2.117.3 from jsDelivr without an integrity attribute. `site.js` initializes authentication even on public informational pages.

Impact: compromise of the supplied script can access browser session data and page contents; CDN unavailability prevents login. The public pages also create third-party requests whose privacy implications should be documented.

Fix: bundle and serve a vetted SDK locally, or use a verified immutable asset with SRI and crossorigin plus an appropriate CSP. Scan JavaScript dependencies too. Restrict authentication initialization to where it is required if practical. Version pinning helps reproducibility but is not equivalent to integrity verification.

### 7. Medium: configuration can expose an incorrectly supplied privileged key

Evidence: `app/supabase_store.py:16` checks only that two variables are present and the URL begins with https. `app/main.py:59` returns the supplied key publicly. Neither function verifies that the configured key is actually a browser-safe publishable/anon key.

Impact: if an operator mistakenly pastes a secret/service-role key into SUPABASE_ANON_KEY, the app publishes it. This is a conditional misconfiguration risk; no real secret exposure was demonstrated.

Fix: reject recognized secret key formats and legacy JWTs identifying service_role, without logging them; validate the configured project URL as a trusted HTTPS origin. Keep privileged secrets separate. Rotate any privileged key that has ever been committed or exposed. A correctly configured publishable/anon key being visible is expected.

Source: https://supabase.com/docs/guides/getting-started/api-keys

### 8. Medium: network failure handling can mislead users and create duplicates

Evidence: `app/supabase_store.py:54` has a 12-second urllib timeout but reads responses without a byte cap, opens a new connection per request, and maps all non-401/403/404 HTTP errors including 429 to generic 502. urllib redirects are not restricted to the configured Supabase origin. Browser fetch calls have no AbortController timeout and assume JSON responses. Every predict retry creates a new row; no idempotency key exists.

Impact: slow upstream calls occupy server capacity; rate limiting is misreported; hosting error pages produce confusing parse errors; a response lost after saving can cause duplicate records if the user resubmits. No user-controlled outbound URL was identified, so this is not a demonstrated public SSRF path.

Fix: use a bounded connection pool with connect/read/total timeout budgets, cap response size, disallow cross-origin redirects carrying credentials, and handle 429/Retry-After distinctly. Add browser cancellation/timeouts and safe non-JSON fallbacks. Retry only safe/idempotent operations with bounded backoff. Use a per-account idempotency key/unique constraint for assessment creation.

### 9. Medium: incomplete deployment isolation and readiness reporting

Evidence: Dockerfile does not set USER, so it runs as root by default. It installs training/download/plotting dependencies into the serving image. The base-image tag and transitive dependencies are not locked to a tested build. `/api/health` always returns status ok even without a model/configuration and only tests variable presence, not database access.

Fix: run as a non-root account with appropriate model-file permissions; minimize runtime dependencies; scan OS packages and the final image. Separate liveness from readiness and return a non-success readiness response when required components are unavailable. Configure provider health checks accordingly. Test native-library imports and model loading in the Linux container, not just Windows. Avoid relying on runtime writes to model assets.

### 10. Medium: consent is browser-controlled, not durable evidence

Evidence: `web/auth.js:87` records acceptance in user-editable metadata with a client timestamp; `web/workspace.html:55` requires a research checkbox in the browser, but `Applicant` and `/api/predict` have no corresponding server requirement.

Impact: direct API use bypasses the research checkbox. Users can alter metadata; it cannot establish an immutable acceptance record. This is a policy/data-integrity gap, not an authorization bypass.

Fix: if acceptance is required, enforce it on the server and keep versioned, server-timestamped consent events in a table clients cannot edit. Define how updated policies are accepted. Minimize collected data instead of relying on disclaimers.

Source: https://supabase.com/docs/guides/auth/users

### 11. Launch blocker for real data: privacy and account lifecycle are incomplete

Evidence: `web/privacy.html` and `web/terms.html` explicitly contain draft operator-identity, address, retention, and account-deletion language. Only individual assessment deletion exists. There is no implemented account export/deletion workflow, approved retention period, backup-deletion explanation, or incident process in the project.

Fix: identify the operator and reliable contact; document the actual hosting/database regions, subprocessors, account and assessment data, browser storage, logs, retention, and deletion behavior. Implement account deletion/export and verified request handling; confirm deletion of auth users cascades to records, and explain backup retention. Select and test backups/restores. Before handling real personal/financial information, obtain advice tailored to the actual operation and applicable law; this review is not a compliance determination.

For a first portfolio launch, use synthetic assessment data and clearly say the score is experimental. Real account emails still need protection even when assessments are synthetic. Resolve inconsistent wording: the workspace notice currently permits real data with consent/review while legal pages forbid identifiable customer data.

### 12. Operational gaps: provider settings and response plan unverified

No evidence in this review verifies actual RLS policies, all exposed database tables/buckets, grants, email confirmation, password policy, CAPTCHA, session durations, MFA, SMTP sender, redirects, backups, organization access, region, or monitoring.

Fix: enable MFA for the owner's GitHub, Render, and Supabase accounts; use least-privilege collaborators. Configure confirmed emails, strong passwords, appropriate session limits, CAPTCHA, exact HTTPS redirect URLs, a verified SMTP sender, and sender-domain SPF/DKIM/DMARC. Monitor uptime, error rate, latency, 429s, storage, and spending. Log request identifiers and safe operational details, not bearer tokens, passwords, or full financial payloads. Prepare recovery, key rotation, user notification, and rollback procedures.

Sources: https://supabase.com/docs/guides/auth/auth-captcha ; https://supabase.com/docs/guides/auth/redirect-urls

### 13. Model artifact trust boundary

Evidence: `app/model_service.py:20` uses joblib.load on a local file. No web upload endpoint for replacing models was found. Your own trusted artifact in a restricted repository is appropriate for this prototype, but the file format is executable deserialization, not inert data.

Fix: deploy only artifacts produced by your trusted training pipeline; record the model hash/version and restrict repository/build access. Never add arbitrary model uploads followed by joblib.load. Test compatibility after dependency updates and keep score provenance tied to a trusted model version. Protecting the file format does not validate fairness, calibration, or fitness for lending.

Source: https://scikit-learn.org/stable/model_persistence.html

### 14. Low: unnecessary public internal endpoints

Evidence: `/openapi.json` is public despite disabling interactive docs; `/api/model-metrics` returns all model metadata; health exposes the best model name. These did not expose credentials or personal records in the reviewed code.

Fix: disable OpenAPI if unnecessary and return only deliberately public metrics/health fields. Do not rely on hiding routes for security.

## Controls already present

- Protected data routes verify bearer tokens with Supabase rather than trusting a submitted account ID.
- Application history/read/delete queries filter by the verified user ID.
- Supplied database SQL enables RLS and limits SELECT, INSERT, DELETE to the owner's rows; anonymous table access is revoked. This must be confirmed on the actual project, including absence of additional permissive policies.
- UUID identifiers and encoded query parameters reduce unsafe query construction; no direct SQL concatenation path was found in the active Supabase API flow.
- User-provided display values generally use textContent rather than HTML interpolation.
- The backend requires an HTTPS Supabase URL, uses default TLS verification, has an upstream timeout, and returns generic database errors.
- The backend does not receive login passwords; browser calls go directly to Supabase Auth.
- No authentication cookies or permissive cross-origin middleware were found. Conventional cookie-based CSRF is not a demonstrated issue in the current bearer-token design.
- `.env`, training data, and legacy SQLite data are excluded from Git/Docker according to the supplied ignore files. No Git repository exists locally yet, so history was not audited. Private GitHub access does not replace secret hygiene.

## Certificates and HTTPS for a first Render launch

Render provides and renews TLS certificates for its service subdomains and configured custom domains. You do not need to buy an SSL certificate for a normal Render deployment. Verify the live certificate, HTTP-to-HTTPS behavior, no mixed-content requests, HSTS policy, and Supabase HTTPS redirect allowlist once deployed. TLS protects data in transit; it does not fix application permissions or validate financial scores.

Source: https://render.com/docs/tls

## Acceptance checks before opening registration

1. Build the exact Linux Docker image with a tested resolved dependency set. Run a complete dependency/container scan and the app tests against that image. Verify native dependencies and scoring work.
2. Apply and inspect Supabase SQL. Create two synthetic test accounts A/B: verify A cannot read/delete B's record through the app AND direct Data API, cannot spoof B's user_id, and anonymous access fails. Inspect every exposed table and storage bucket, not only credit_assessments.
3. Confirm fake/expired tokens receive 401; invalid IDs, categories, infinity/overflow, oversized bodies, and unknown fields are rejected as intended without 500 responses.
4. Demonstrate application limits return 429 with Retry-After, quotas cannot be bypassed with direct writes, and a slow upstream cannot indefinitely tie up requests. Test multiple workers and trusted proxy IP handling.
5. Confirm security headers, authenticated no-store responses, script integrity/bundling, denied framing, and production HTTPS on the deployed domain.
6. Test signup/confirmation/signin/reset/signout in a fresh browser. Test expired/reused reset links and shared-device behavior. Verify actual provider password/rate/CAPTCHA settings.
7. Test duplicate submission/idempotency, Supabase outage, browser offline state, timeout, and non-JSON hosting errors with safe feedback and no silent loss or repeated writes.
8. Test account deletion/export, retention cleanup, and backup restore with synthetic data. Publish the final operator/privacy/terms information consistent with actual behavior.
9. Enable owner MFA, uptime/error/budget alerts, minimal safe logging, and a rollback/incident plan. Keep the initial audience small and accept synthetic assessments only.

Unresolved provider-dependent checks are not completed by source review. The initial audit made no application/provider changes. See the remediation update at the top for subsequent code fixes; provider-side setup remains required.
