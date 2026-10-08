# Credit-Sure

Public research calculator for exploring synthetic alternative-credit scenarios.
No signup, login, SMTP, Supabase connection or saved assessment history is required.
The XGBoost model is experimental and must not be used for real credit decisions.

## Run locally

Use Python 3.14 and install `requirements.txt` in a virtual environment. Copy
`.env.example` to `.env` if needed; keep it private. Run:

```powershell
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-proxy-headers
```

Open http://127.0.0.1:8000/workspace. Development supports in-memory request limits;
production requires shared Redis. Trusted model, metadata and manifest are included
in `models/`; changing model artifacts requires regenerating the trusted manifest.

## Deploy

Follow [LAUNCH_SETUP.md](LAUNCH_SETUP.md). Render needs APP_ENV, ALLOWED_HOSTS,
REDIS_URL, RATE_LIMIT_SALT and LAUNCH_SETTINGS_REVIEWED. `/api/health` is liveness;
`/api/ready` verifies model, launch configuration and Redis. It deliberately returns
503 until all required production settings are complete. No accounts are created.

Predictions validate synthetic research confirmation and bounded inputs, process
in memory, return directly and never write assessment records. Refreshing clears
the browser result. Redis stores short-lived rate counters; provider operational
logs may retain network metadata. See the site's privacy notice and terms.

The legacy `app/supabase_store.py` and SQL migrations are retained to support
operator-managed legacy records. They are not used by the public serving routes.
Existing Supabase data is not automatically deleted. Disable old registrations and
handle prior access/deletion requests separately. The public app exposes no account
or history API; old signin/signup links redirect to the calculator.

## Checks

```powershell
python scripts/check_release.py
python -m unittest discover -s tests -v
node scripts/test_database.mjs
npx playwright test
```

Install `requirements-dev.txt` and run `npm ci --ignore-scripts` for the tests.
GitHub Actions also builds the non-root Linux image, tests the official CPython
backports, smoke-tests model inference and scans the image. The blocking scan
retains its only-fixed policy; read the separate report for unfixed OS findings.
See [SECURITY_REVIEW.md](SECURITY_REVIEW.md) and `vendor/cpython_security/README.md`.
