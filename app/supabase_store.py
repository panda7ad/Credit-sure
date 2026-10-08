import json
import os
import base64
import time as clock
from uuid import UUID
from pathlib import Path
from datetime import date, datetime, time, timedelta, timezone
from urllib.parse import quote, urlencode, urlsplit
import httpx

from fastapi import HTTPException
from dotenv import load_dotenv
from app.schemas import POLICY_VERSION

# Local settings survive terminal restarts; hosting environment values take priority.
load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)

MAX_RESPONSE_BYTES = 2 * 1024 * 1024
http_client = httpx.Client(timeout=httpx.Timeout(8, connect=3, pool=2),
                           limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
                           follow_redirects=False, trust_env=False)


def jwt_claims(token):
    try:
        part = token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
        return claims if isinstance(claims, dict) else {}
    except (ValueError, IndexError, TypeError):
        return {}


def check_key(key, privileged=False):
    role = jwt_claims(key).get("role")
    valid = (key.startswith("sb_secret_") or role == "service_role") if privileged else (key.startswith("sb_publishable_") or role == "anon")
    if not valid or len(key) > 4096:
        raise HTTPException(503, "Supabase key configuration is invalid. Check the public and server-only keys.")


def get_supabase_settings():
    url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    anon_key = os.getenv("SUPABASE_ANON_KEY", "").strip()
    if not url or not anon_key:
        return None
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError:
        raise HTTPException(503, "Supabase URL configuration is invalid.") from None
    if (parsed.scheme != "https" or not parsed.hostname or not parsed.hostname.endswith(".supabase.co")
            or parsed.username or parsed.password or port not in (None, 443)
            or parsed.path or parsed.query or parsed.fragment):
        raise HTTPException(
            status_code=503,
            detail="SUPABASE_URL must be your project's HTTPS supabase.co origin.",
        )
    check_key(anon_key)
    return url, anon_key


def get_server_key():
    key = os.getenv("SUPABASE_SECRET_KEY", "").strip()
    check_key(key, privileged=True)
    return key


def _request(path, access_token=None, body=None, method="GET", prefer=None, backend=False):
    settings = get_supabase_settings()
    if settings is None:
        raise HTTPException(
            status_code=503,
            detail="Authentication is not configured. Set up Supabase to continue.",
        )
    url, anon_key = settings
    if backend:
        anon_key = get_server_key()
        access_token = anon_key if not anon_key.startswith("sb_secret_") else None
    headers = {
        "apikey": anon_key,
        "Accept": "application/json",
    }
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    if body is not None:
        headers["Content-Type"] = "application/json"
    if prefer:
        headers["Prefer"] = prefer
    if not path.startswith(("/rest/v1/", "/auth/v1/")):
        raise ValueError("Unexpected upstream path")
    try:
        started = clock.monotonic()
        with http_client.stream(method, f"{url}{path}", headers=headers, json=body) as response:
            chunks, size = [], 0
            for chunk in response.iter_bytes(chunk_size=16384):
                size += len(chunk)
                if size > MAX_RESPONSE_BYTES or clock.monotonic() - started > 12:
                    raise HTTPException(503, "The secure service response exceeded its limits.")
                chunks.append(chunk)
            response_body = b"".join(chunks)
            status = response.status_code
            if status == 429:
                retry = response.headers.get("Retry-After", "60")
                retry = retry if retry.isdigit() and 0 < int(retry) <= 3600 else "60"
                raise HTTPException(429, "The secure service is busy. Try again later.", headers={"Retry-After": retry})
            if status in (401, 403):
                raise HTTPException(503 if backend else 401, "Secure service authorization failed." if backend else "Your sign-in session has expired.")
            if status == 404:
                raise HTTPException(503, "The database migration is not ready. Apply supabase/schema.sql.")
            if status >= 300:
                try:
                    upstream = json.loads(response_body)
                except (ValueError, UnicodeError):
                    upstream = {}
                messages = {"quota_exceeded": (429, "Assessment quota reached. Delete old records or try tomorrow."),
                            "consent_required": (403, "Accept the current research policies before saving."),
                            "idempotency_conflict": (409, "This request identifier was already used for different input.")}
                code = upstream.get("message") if isinstance(upstream, dict) else None
                if code in messages:
                    status_code, detail = messages[code]
                    raise HTTPException(status_code, detail, headers={"Retry-After": "3600"} if status_code == 429 else None)
                raise HTTPException(502, "The secure service could not complete the request.")
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=503,
            detail="The secure service is temporarily unavailable.",
        ) from error
    if not response_body:
        return None
    try:
        return json.loads(response_body)
    except (json.JSONDecodeError, UnicodeError) as error:
        raise HTTPException(
            status_code=502,
            detail="The secure database returned an invalid response.",
        ) from error


def verify_access_token(access_token):
    user = _request("/auth/v1/user", access_token=access_token)
    if not isinstance(user, dict) or not user.get("id"):
        raise HTTPException(status_code=401, detail="Your sign-in session is invalid.")
    try:
        identifier = str(UUID(user["id"]))
    except (ValueError, TypeError):
        raise HTTPException(401, "Your sign-in session is invalid.") from None
    claims = jwt_claims(access_token)  # Supabase has already verified this token above.
    if claims.get("sub") != identifier or claims.get("role") != "authenticated":
        raise HTTPException(401, "Your sign-in session is invalid.")
    if not user.get("email_confirmed_at"):
        raise HTTPException(403, "Confirm your email address before using the workspace.")
    return {"id": identifier, "access_token": access_token, "email": user.get("email"), "amr": claims.get("amr", [])}


def save_assessment(user_id, payload, result, access_token, request_id, payload_hash, model_version):
    return _request(
        "/rest/v1/rpc/save_research_assessment",
        backend=True,
        method="POST",
        body={
            "p_user_id": user_id, "p_request_id": request_id,
            "p_payload_hash": payload_hash, "p_payload": payload,
            "p_result": result, "p_model_version": model_version,
        },
    )


def existing_request(user_id, request_id):
    query = urlencode({"select": "payload_sha256,result", "user_id": f"eq.{user_id}",
                       "request_id": f"eq.{request_id}", "limit": "1"})
    rows = _request(f"/rest/v1/credit_assessments?{query}", backend=True)
    return rows[0] if rows else None


def account_status(user_id):
    query = urlencode({"select": "policy_version,accepted_at", "user_id": f"eq.{user_id}",
                       "policy_version": f"eq.{POLICY_VERSION}", "limit": "1"})
    return bool(_request(f"/rest/v1/account_consents?{query}", backend=True))


def record_consent(user_id):
    return _request("/rest/v1/rpc/accept_research_policy", method="POST", backend=True,
                    body={"p_user_id": user_id, "p_policy_version": POLICY_VERSION})


def database_ready():
    return _request("/rest/v1/rpc/research_schema_version", method="POST", backend=True, body={}) == 2


def delete_account(user_id):
    _request(f"/auth/v1/admin/users/{quote(user_id, safe='')}", method="DELETE", backend=True)


def export_account(user_id):
    records = []
    for offset in range(0, 500, 50):
        query = urlencode({"select": "id,created_at,applicant_name,payload,result,model_version",
                           "user_id": f"eq.{user_id}", "order": "created_at.asc,id.asc", "offset": str(offset), "limit": "50"})
        batch = _request(f"/rest/v1/credit_assessments?{query}", backend=True)
        records.extend(batch)
        if len(batch) < 50:
            break
    query = urlencode({"select": "policy_version,accepted_at", "user_id": f"eq.{user_id}"})
    if len(records) == 500:
        overflow_query = urlencode({"select": "id", "user_id": f"eq.{user_id}", "offset": "500", "limit": "1"})
        if _request(f"/rest/v1/credit_assessments?{overflow_query}", backend=True):
            raise HTTPException(409, "This legacy account exceeds the export limit. Contact support for a complete export.")
    return {"assessments": records, "consents": _request(f"/rest/v1/account_consents?{query}", backend=True)}


def get_history(user_id, access_token, assessed_on=None, limit=50):
    params = {
        "select": "id,created_at,applicant_name,result,model_version",
        "user_id": f"eq.{user_id}",
        "order": "created_at.desc",
        "limit": str(limit),
    }
    if assessed_on:
        selected_date = date.fromisoformat(assessed_on)
        india = timezone(timedelta(hours=5, minutes=30))
        start = datetime.combine(selected_date, time.min, tzinfo=india)
        try:
            end = start + timedelta(days=1)
        except OverflowError:
            raise HTTPException(422, "Choose a valid assessment date.") from None
        query = urlencode(
            params
        )
        query += f"&created_at=gte.{quote(start.isoformat(), safe='')}"
        query += f"&created_at=lt.{quote(end.isoformat(), safe='')}"
    else:
        query = urlencode(params)
    return _request(
        f"/rest/v1/credit_assessments?{query}",
        access_token=access_token,
    )


def get_assessment(record_id, user_id, access_token):
    query = urlencode(
        {
            "select": "id,created_at,applicant_name,payload,result,model_version",
            "id": f"eq.{record_id}",
            "user_id": f"eq.{user_id}",
            "limit": "1",
        }
    )
    records = _request(
        f"/rest/v1/credit_assessments?{query}",
        access_token=access_token,
    )
    return records[0] if records else None


def delete_assessment(record_id, user_id, access_token):
    query = urlencode(
        {"id": f"eq.{record_id}", "user_id": f"eq.{user_id}"}
    )
    _request(
        f"/rest/v1/credit_assessments?{query}",
        backend=True,
        method="DELETE",
        prefer="return=minimal",
    )
