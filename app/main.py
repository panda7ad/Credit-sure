from pathlib import Path
import logging
import os
import threading
import time

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)

from app.model_service import CreditModel
from app.schemas import AssessmentRequest
from app.security import SecurityMiddleware, limiter, production, client_address


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
PAGES = {
    "": "index.html",
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


@app.get("/")
def home():
    return FileResponse(WEB / "index.html")


@app.get("/{page}")
def static_page(page: str):
    if page in ("signin", "signup"):
        return RedirectResponse("/workspace", status_code=303)
    filename = PAGES.get(page)
    if not filename:
        raise HTTPException(status_code=404, detail="Page not found")
    return FileResponse(WEB / filename)


@app.get("/api/config")
def public_config():
    return {"accounts_enabled": False, "history_enabled": False,
            "contact_email": "youngseldon77@gmail.com", "operator_name": "Adarsh-Patel"}


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "model_loaded": model.model is not None,
        "accounts_enabled": False,
    }


@app.get("/api/ready")
def ready():
    with readiness_lock:
        now = time.monotonic()
        if now - readiness_cache["at"] > 10:
            try:
                launch = (not production()) or (os.getenv("LAUNCH_SETTINGS_REVIEWED") == "true"
                         and len(os.getenv("RATE_LIMIT_SALT", "")) >= 32)
                available = model.model is not None and launch and limiter.ready()
            except Exception:
                available = False
            readiness_cache.update(at=now, ready=bool(available))
    return JSONResponse({"status": "ready" if readiness_cache["ready"] else "not_ready"}, status_code=200 if readiness_cache["ready"] else 503)


@app.post("/api/predict")
def predict(applicant: AssessmentRequest, request: Request):
    if production() and (os.getenv("LAUNCH_SETTINGS_REVIEWED") != "true"
                         or len(os.getenv("RATE_LIMIT_SALT", "")) < 32):
        raise HTTPException(503, "The calculator is awaiting launch setup.")
    if model.model is None:
        raise HTTPException(503, "The scoring model is not available.")
    limiter.check(f"predict-ip:{client_address(request.scope)}", 10)
    # A global budget protects the small instance even when clients change IPs.
    limiter.check("predict-global", 60)
    limiter.check("predict-global-hour", 600, 3600)
    if not inference_slots.acquire(blocking=False):
        raise HTTPException(503, "The model is busy. Try again shortly.", headers={"Retry-After": "5"})
    try:
        return model.predict(applicant.model_dump(exclude={"research_confirmed"}))
    finally:
        inference_slots.release()
