# Credit-Sure

## Security update and launch instructions

Read [LAUNCH_SETUP.md](./LAUNCH_SETUP.md) before deployment. It supersedes the older setup notes below. The app now needs Python 3.14, the updated Supabase SQL migration, a server-only `SUPABASE_SECRET_KEY`, and Redis for shared production rate limits. `.env` is loaded automatically for local development. The public key remains browser-safe; the server secret is never returned by `/api/config`.

Use `requirements.txt` for serving, `requirements-training.txt` for model training, and `requirements-dev.txt` for tests/audits. `requirements.lock` pins the resolved serving dependencies; regenerate it with `scripts/lock_runtime.py` in the verified environment after updates. The current model uses CPU-only XGBoost. `scripts/model_manifest.py` records hashes of trusted model artifacts, and all three model files must be committed together to your private repository.

New protections include strict input/body limits, shared request limits, database-enforced quotas, protected model-result writes, immutable server-timestamped consent, idempotent saves, security headers, safe error handling, tab-scoped browser sessions, export, recent-sign-in account deletion, and a 90-day assessment retention job. The SQL migration must be applied to your actual project; creating files locally does not change Supabase.

`/api/health` is liveness; `/api/ready` checks required deployment components and returns 503 until setup is complete. Public model metrics and OpenAPI endpoints are disabled. Registration defaults closed in production until account-side settings are reviewed. GitHub's security workflow tests the Linux image and scans it after upload. Real provider settings, backups and HTTPS remain launch checks, not assumptions.

For local startup after filling `.env` and applying SQL:

```powershell
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8003 --reload
```

Account/data endpoints added: `GET /api/account`, `POST /api/account/consent`, `GET /api/account/export`, and `DELETE /api/account`. Prediction now requires `Idempotency-Key` and `research_confirmed: true`; the browser supplies them. Use synthetic assessment data only.

Credit-Sure is a portfolio/research prototype for exploring affordability and repayment signals in alternative credit assessment. It is **not a lender, credit bureau, validated credit score, or production underwriting system**.

## Current application

- A small public website plus separate sign-in, sign-up, research workspace, how-it-works, terms and privacy pages.
- Supabase Auth for accounts and Supabase Postgres for saved assessments.
- Each assessment stores the signed-in account ID. `supabase/schema.sql` enables row-level security so accounts can access only their own records.
- The research form requires only applicant name, age, income, requested loan and monthly instalment. Additional details are optional; missing model inputs are imputed from training data and can reduce the usefulness of an estimate.
- The existing trained model is based on public Home Credit competition data and derived feature proxies. Its output is experimental and must not be used for decisions about real people.

Legacy records in `credit_scoring.db` are not automatically copied into customer accounts. Their owners cannot be established safely from the old shared database. The new authenticated workspace does not expose that shared database.

## Run locally

1. Create a Supabase project and apply [`supabase/schema.sql`](./supabase/schema.sql) in its SQL Editor.
2. In Supabase Auth settings, enable email/password sign-in, set the local site URL to `http://127.0.0.1:8003`, and add `http://127.0.0.1:8003/workspace` and `http://127.0.0.1:8003/signin?recovery=1` as allowed redirect URLs.
3. For persistent local configuration, copy `.env.example` to `.env` in this directory and replace its placeholders with your Supabase project URL and **publishable/anon key**. The app loads this file automatically, regardless of the terminal's working directory. `.env` is excluded from Git and Docker images. Existing environment variables take priority. Never use a service-role key. Alternatively, set variables for the current PowerShell session:

   ```powershell
   $env:SUPABASE_URL = "https://your-project-id.supabase.co"
   $env:SUPABASE_ANON_KEY = "your-public-anon-key"
   ```

4. Install dependencies and start the app:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements-training.txt
   python download_data.py
    python run_pipeline.py
    python scripts/model_manifest.py
   python -m uvicorn app.main:app --host 127.0.0.1 --port 8003 --reload
   ```

   Kaggle dataset use requires your own Kaggle account and accepted competition rules. The trained model and metadata are created locally and are excluded from Git.

5. Open `http://127.0.0.1:8003`.

Set up a real SMTP sender in Supabase before relying on email confirmation. Its default test email service is rate-limited. For any production domain, update both Supabase’s site URL and the exact allowed HTTPS callback URL.

## What you need to set up before going live

### 1. Supabase project

- Create a project in a region selected for your users and data-residency obligations.
- Apply `supabase/schema.sql`; ensure `public.credit_assessments` is exposed to the Supabase Data API, row-level security is enabled, and access is tested with two different accounts.
- Enable email/password authentication, configure email confirmation and password recovery, and set up a verified SMTP sender.
- Add the sender domain’s required SPF/DKIM DNS records so confirmation and recovery email can be delivered reliably.
- Copy the project URL and public anon/publishable key into the hosting provider’s environment settings.
- Keep the service-role/secret key private in `SUPABASE_SECRET_KEY`. Reads use the user's token and RLS; protected writes, consent and account deletion use this separate server-only credential after user verification. The public `SUPABASE_ANON_KEY` must never contain it.
- Choose backups, retention and account-deletion handling; test restore and deletion procedures.

### 2. Web hosting and domain

- Deploy the Docker application to a Python/Docker web host such as Render, Railway or Fly.io. Configure `SUPABASE_URL` and `SUPABASE_ANON_KEY` as server environment variables.
- The host needs trusted `models/credit_model.joblib`, `models/metadata.json` and `models/manifest.json` files. Commit these specific assets together to your private repository; the Dockerfile requires them. Do not include Kaggle credentials, training datasets, `.env` or customer data.
- Add a domain you own, point its DNS records to the host, enable HTTPS/TLS, and set the production site/callback URLs in Supabase Auth.
- Verify registration, email confirmation, password reset, sign-out, owner-only history, deletion, backups and health checks on the deployed domain before inviting users.

### 3. Business and legal details

- The Terms and Privacy pages describe the synthetic-data research service and supplied operator/contact information. They are not legal advice or a compliance certification. Review actual provider regions, retention and applicable requirements before launch; seek qualified advice before accepting real customer information or offering a lending product.
- Before a public launch, supply the operator’s legal name, contact/postal address, privacy/grievance contact, retention schedule and documented deletion/account-closure process.
- Do not use this prototype for real credit decisions or enter real applicant financial data. A real lending product requires a separately validated model, fairness and impact testing, meaningful explanations and human oversight, lawful data collection and consent, security assessment, and specialist legal/regulatory review.

Analytics and social links are not included: no analytics property or social profiles were supplied, and tracking is unnecessary for this private research workspace.

## API

- `GET /api/config` — public Supabase browser configuration (URL and public anon key only)
- `GET /api/health` — service/model/configuration status
- `POST /api/predict` — authenticated research estimate; saves it to the signed-in account
- `GET /api/history?assessed_on=YYYY-MM-DD` — authenticated account’s assessments; optional India-local date filter
- `GET /api/history/{id}` — read one of the signed-in account’s assessments
- `DELETE /api/history/{id}` — delete one of the signed-in account’s assessments
- `GET /api/ready` — production readiness, including migration and shared limiter
- `GET /api/account/export` — download the signed-in account's data
- `DELETE /api/account` — delete the signed-in account after recent password authentication
