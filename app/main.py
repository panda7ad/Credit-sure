from datetime import date
from pathlib import Path
from uuid import UUID
import hashlib
import json
import logging
import os
import threading
import time

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.model_service import CreditModel
from app.schemas import AssessmentRequest, ConsentRequest, DeleteAccountRequest, POLICY_VERSION
from app.security import SecurityMiddleware, limiter, production
from app.supabase_store import (
    get_assessment,
    get_history,
    get_supabase_settings,
    save_assessment,
    delete_assessment,
    verify_access_token,
    existing_request, account_status, record_consent, database_ready, delete_account, export_account,
)

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
PAGES = {
    "": "index.html",
    "signin": "auth.html",
    "signup": "auth.html",
    "workspace": "workspace.html",
    "how-it-works": "how-it-works.html",
    "terms": "terms.html",
    "privacy": "privacy.html",
}

app = FastAPI(title="Credit-Sure", version="2.0.0", docs_url=None, redoc_url=None, openapi_url=None)
hosts = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",") if h.strip()]
if "*" in hosts or (production() and not os.getenv("ALLOWED_HOSTS")):
    raise RuntimeError("Configure exact ALLOWED_HOSTS before production startup")
app.add_middleware(TrustedHostMiddleware, allowed_hosts=hosts, www_redirect=False)
app.add_middleware(SecurityMiddleware)
app.mount("/static", StaticFiles(directory=WEB), name="static")
model = CreditModel()
inference_slots = threading.BoundedSemaphore(2)
readiness_lock = threading.Lock()
readiness_cache = {"at": 0, "ready": False}


@app.exception_handler(RequestValidationError)
async def validation_error(request, error):
    # Do not echo potentially sensitive input back into logs or responses.
    details = [{"loc": e["loc"], "msg": e["msg"], "type": e["type"]} for e in error.errors()]
    return JSONResponse({"detail": details}, status_code=422)


@app.exception_handler(Exception)
async def unexpected_error(request, error):
    logging.getLogger("creditsure").error("request_failed id=%s type=%s", getattr(request.state, "request_id", "unknown"), type(error).__name__)
    return JSONResponse({"detail": "The request could not be completed. Contact support with the request ID."}, status_code=500,
                        headers={"Cache-Control": "no-store"})


def authenticated_user(request: Request, authorization: str | None = Header(default=None)):
    if production() and os.getenv("LAUNCH_SETTINGS_REVIEWED") != "true":
        raise HTTPException(503, "The research workspace is awaiting launch setup.")
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Sign in to access your workspace.")
    token = authorization[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Your sign-in session is invalid.")
    user = verify_access_token(token)
    limiter.check(f"account:{user['id']}", 120)
    return user


@app.get("/")
def home():
    return FileResponse(WEB / "index.html")


@app.get("/{page}")
def static_page(page: str):
    filename = PAGES.get(page)
    if not filename:
        raise HTTPException(status_code=404, detail="Page not found")
    return FileResponse(WEB / filename)


@app.get("/api/config")
def public_config():
    settings = get_supabase_settings()
    return {
        "configured": settings is not None,
        "supabase_url": settings[0] if settings else None,
        "supabase_anon_key": settings[1] if settings else None,
        "contact_email": "youngseldon77@gmail.com",
        "operator_name": "Adarsh-Patel",
        "policy_version": POLICY_VERSION,
        "captcha_site_key": os.getenv("TURNSTILE_SITE_KEY", "").strip(),
        "signup_enabled": (not production()) or (os.getenv("PUBLIC_SIGNUP_ENABLED") == "true" and os.getenv("LAUNCH_SETTINGS_REVIEWED") == "true" and bool(os.getenv("TURNSTILE_SITE_KEY"))),
    }


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "model_loaded": model.model is not None,
        "authentication_configured": get_supabase_settings() is not None,
    }


@app.get("/api/ready")
def ready():
    with readiness_lock:
        now = time.monotonic()
        if now - readiness_cache["at"] > 10:
            try:
                configured = bool(get_supabase_settings())
                launch = (not production()) or (os.getenv("LAUNCH_SETTINGS_REVIEWED") == "true"
                         and bool(os.getenv("TURNSTILE_SITE_KEY")) and len(os.getenv("RATE_LIMIT_SALT", "")) >= 32)
                available = configured and model.model is not None and launch and limiter.ready() and database_ready()
            except Exception:
                available = False
            readiness_cache.update(at=now, ready=bool(available))
    return JSONResponse({"status": "ready" if readiness_cache["ready"] else "not_ready"}, status_code=200 if readiness_cache["ready"] else 503)


@app.post("/api/predict")
def predict(applicant: AssessmentRequest, idempotency_key: UUID = Header(alias="Idempotency-Key"), user=Depends(authenticated_user)):
    if model.model is None:
        raise HTTPException(status_code=503, detail="The scoring model is not available.")
    limiter.check(f"predict:{user['id']}", 10)
    payload = applicant.model_dump(exclude={"research_confirmed"})
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    prior = existing_request(user["id"], str(idempotency_key))
    if prior:
        if prior["payload_sha256"] != digest:
            raise HTTPException(409, "This request identifier was already used for different input.")
        return prior["result"]
    if not account_status(user["id"]):
        raise HTTPException(403, "Accept the current research policies before saving.")
    if not inference_slots.acquire(blocking=False):
        raise HTTPException(503, "The model is busy. Retry this same request shortly.", headers={"Retry-After": "5"})
    try:
        result = model.predict(payload)
    finally:
        inference_slots.release()
    return save_assessment(user["id"], payload, result, user["access_token"], str(idempotency_key), digest, model.version)


@app.get("/api/history")
def history(
    assessed_on: date | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    user=Depends(authenticated_user),
):
    return get_history(
        user["id"],
        user["access_token"],
        assessed_on.isoformat() if assessed_on else None,
        limit,
    )


@app.get("/api/history/{record_id}")
def history_record(record_id: UUID, user=Depends(authenticated_user)):
    record = get_assessment(str(record_id), user["id"], user["access_token"])
    if record is None:
        raise HTTPException(status_code=404, detail="Assessment not found.")
    return record


@app.delete("/api/history/{record_id}", status_code=204)
def remove_history_record(record_id: UUID, user=Depends(authenticated_user)):
    delete_assessment(str(record_id), user["id"], user["access_token"])
    return Response(status_code=204)


@app.get("/api/account")
def account(user=Depends(authenticated_user)):
    return {"policy_version": POLICY_VERSION, "accepted": account_status(user["id"])}


@app.post("/api/account/consent")
def accept_consent(consent: ConsentRequest, user=Depends(authenticated_user)):
    limiter.check(f"consent:{user['id']}", 5)
    record_consent(user["id"])
    return {"accepted": True, "policy_version": POLICY_VERSION}


@app.get("/api/account/export")
def account_export(user=Depends(authenticated_user)):
    limiter.check(f"export:{user['id']}", 2, 3600)
    return JSONResponse({"account": {"id": user["id"], "email": user.get("email")}, **export_account(user["id"])},
                        headers={"Content-Disposition": 'attachment; filename="credit-sure-export.json"'})


@app.delete("/api/account", status_code=204)
def account_delete(confirm: DeleteAccountRequest, user=Depends(authenticated_user)):
    limiter.check(f"delete-account:{user['id']}", 3, 3600)
    # AMR comes from a token already verified by Supabase, not client metadata.
    now = time.time()
    fresh = any(isinstance(a, dict) and a.get("method") == "password" and isinstance(a.get("timestamp"), (float, int))
                and 0 <= now - a["timestamp"] <= 300 for a in user.get("amr", []))
    if not fresh:
        raise HTTPException(403, "Sign in again within five minutes before deleting your account.")
    delete_account(user["id"])
    return Response(status_code=204)
