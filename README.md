# Credit-Sure

A full-stack machine learning portfolio project that estimates credit risk from financial and alternative-credit inputs. Built with **FastAPI, XGBoost, pandas, scikit-learn, and vanilla JavaScript**.

Enter a synthetic applicant profile to see a default-probability estimate, a 300-900 score, a risk band, and explanatory factors. The calculator requires no account and saves no assessment history.

> Educational research demo: alternative-credit signals are synthetic and the model is not validated for lending decisions. Use fictional inputs, not personal financial information.

## Run in five minutes

You need **Python 3.14**, Git, and an internet connection to install packages. The trained model is included; no training, Docker, database, API keys, or Redis setup is needed locally.

### Windows (PowerShell or VS Code terminal)

```powershell
git clone https://github.com/panda7ad/Credit-sure.git
cd Credit-sure
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-proxy-headers
```

### macOS / Linux

```bash
git clone https://github.com/panda7ad/Credit-sure.git
cd Credit-sure
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-proxy-headers
```

Open **http://127.0.0.1:8000/workspace**, enter fictional values, confirm the research notice, and select the calculation button. Stop the server with **Ctrl+C**. These commands use the virtual environment directly, so activating it or changing PowerShell execution policy is unnecessary.

If Python is not found, install Python 3.14 and reopen your terminal. If port 8000 is busy, use `--port 8001` and open the matching URL. If you reused an old `.env`, remove production settings for local development or start with `.env.example`. A fresh clone runs with development defaults without an `.env` file.

## How it works

```text
Browser form -> validated FastAPI request -> feature engineering
             -> trusted XGBoost model -> JSON result -> browser display
```

- Input validation rejects non-finite numbers, out-of-range values, and unexpected fields.
- Model artifacts are checked against a SHA-256 manifest before loading.
- Prediction and global rate limits, bounded request sizes, and inference concurrency limits protect the API.
- The browser renders results as text and clears them on refresh. Assessments are processed in memory, without a database.
- Production uses shared Redis rate counters; hosting providers may retain operational network logs.

## Project structure

| Path | Purpose |
| --- | --- |
| `app/` | FastAPI routes, validation, model inference, security middleware |
| `web/` | Responsive calculator, result display, privacy notice and terms |
| `models/` | Included trained model, metadata and integrity manifest |
| `src/` | Dataset preparation, feature engineering, EDA and model training |
| `reports/` | Recorded experiment metrics and EDA summary |
| `tests/` | API/security tests and Playwright browser tests |
| `scripts/` | Model integrity, dependency locking and release checks |
| `vendor/cpython_security/` | Verified upstream security backports used by Docker |

## Optional: reproduce model experiments

The serving app and training pipeline are separate. The optional pipeline uses the Kaggle Home Credit Default Risk competition. Accept its competition rules and configure Kaggle credentials, then run `python download_data.py`, or place `application_train.csv`, `previous_application.csv`, `installments_payments.csv`, and `credit_card_balance.csv` in `data/raw/`. Data and credentials are excluded from Git. Training requires additional dependencies and can take substantially longer than running the included model.

```bash
python -m pip install -r requirements-training.txt
python run_pipeline.py
python scripts/model_manifest.py
```

Use your virtual environment's Python executable in these commands. Regenerate the model manifest after intentionally changing model artifacts. `reports/model_results.json` and `models/metadata.json` contain recorded evaluation metrics; these do not establish real-world lending accuracy.

## Optional: tests

```bash
python -m pip install -r requirements-dev.txt
python scripts/check_release.py
python -m unittest discover -s tests -v
npm ci --ignore-scripts
npx playwright install chromium
npm test
```

Node.js is only required for browser tests. Use the virtual environment's Python executable. GitHub Actions also audits dependencies, builds the non-root Docker image, smoke-tests inference, and scans it for vulnerabilities.

## Optional: deploy on Render

Local use is enough to review this project. For hosting, follow the complete checklist in [LAUNCH_SETUP.md](LAUNCH_SETUP.md). Production needs an exact allowed hostname and shared Redis configuration. Signup and SMTP setup are unnecessary.

See [SECURITY_REVIEW.md](SECURITY_REVIEW.md) for current protections and limitations. The image scan reports unfixed OS findings separately; passing CI does not mean the image has zero vulnerabilities.

**Author:** Adarsh-Patel
