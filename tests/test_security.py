import base64
import hashlib
import json
import os
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from uuid import uuid4

import fakeredis
import httpx
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app import main, supabase_store as store
from app.schemas import Applicant, POLICY_VERSION
from app.security import RateLimiter, client_address

BASE = dict(applicant_name="Synthetic A", age_years=30, annual_income=600000, loan_amount=250000, annuity_amount=15000)
ACCOUNT = str(uuid4())
ENV = {"APP_ENV": "development", "REDIS_URL": "", "SUPABASE_URL": "https://example.supabase.co",
       "SUPABASE_ANON_KEY": "sb_publishable_dummy", "SUPABASE_SECRET_KEY": "sb_secret_dummy"}


def jwt(claims):
    segment = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    return "header." + segment + ".signature"


class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, ENV)
        self.env.start()
        main.limiter._local.clear()
        main.app.dependency_overrides.clear()
        self.client = TestClient(main.app)

    def tearDown(self):
        main.app.dependency_overrides.clear()
        self.env.stop()

    def user(self, **extra):
        user = {"id": ACCOUNT, "access_token": "verified", "email": "synthetic@example.test", **extra}
        main.app.dependency_overrides[main.authenticated_user] = lambda: user

    def test_invalid_input_is_rejected(self):
        for change in [dict(annual_income=float("inf")), dict(loan_amount=float("nan")),
                       dict(education="x" * 1000000), dict(extra_field="value"),
                       dict(age_years=30.5), dict(applicant_name="\n"), dict(prior_loans=1001)]:
            with self.subTest(change=list(change)), self.assertRaises(ValidationError):
                Applicant(**(BASE | change))

    def test_oversize_content_length_and_chunked_bodies(self):
        for content in [b"x" * 17000, iter([b"x" * 9000, b"x" * 9000])]:
            response = self.client.post("/api/predict", content=content, headers={"Content-Type": "application/json"})
            self.assertEqual(response.status_code, 413)
            self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")

    def test_browser_headers_and_private_cache_policy(self):
        response = self.client.get("/")
        self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        self.assertEqual(response.headers["Referrer-Policy"], "no-referrer")
        self.assertEqual(self.client.get("/api/history").headers["Cache-Control"], "no-store")
        self.assertEqual(self.client.get("/openapi.json").status_code, 404)
        self.assertEqual(self.client.get("/api/model-metrics").status_code, 404)

    def test_host_and_range_protection(self):
        self.assertEqual(self.client.get("/", headers={"Host": "attacker.example"}).status_code, 400)
        self.assertEqual(self.client.get("/", headers={"Range": "bytes=0-1,3-4"}).status_code, 400)
        self.assertEqual(self.client.get("/", headers={"Range": "bytes=" + "0" * 300}).status_code, 400)

    def test_privileged_key_never_reaches_public_config(self):
        for key in ["sb_secret_do-not-publish", jwt({"role": "service_role"})]:
            with patch.dict(os.environ, SUPABASE_ANON_KEY=key):
                response = self.client.get("/api/config")
                self.assertEqual(response.status_code, 503)
                self.assertNotIn(key, response.text)

    def test_invalid_urls_are_rejected(self):
        for url in ["http://example.supabase.co", "https://example.supabase.co/redirect", "https://example.supabase.co@evil.test", "https://127.0.0.1"]:
            with patch.dict(os.environ, SUPABASE_URL=url), self.assertRaises(HTTPException):
                store.get_supabase_settings()

    def test_shared_limiter_is_atomic_and_expires(self):
        shared = fakeredis.FakeRedis()
        first, second = RateLimiter(), RateLimiter()
        with patch.object(first, "redis_client", return_value=shared), patch.object(second, "redis_client", return_value=shared):
            def request(i):
                try:
                    (first if i % 2 else second).check("same-account", 10)
                    return 200
                except HTTPException as error:
                    return error.status_code
            with ThreadPoolExecutor(max_workers=8) as pool:
                statuses = list(pool.map(request, range(30)))
            self.assertEqual(statuses.count(200), 10)
            self.assertEqual(statuses.count(429), 20)
            for key in shared.keys():
                self.assertGreater(shared.ttl(key), 0)
                self.assertNotIn(b"same-account", key)

    def test_production_without_shared_limiter_fails_closed(self):
        with patch.dict(os.environ, APP_ENV="production", REDIS_URL=""), self.assertRaises(HTTPException) as error:
            RateLimiter().check("account", 5)
        self.assertEqual(error.exception.status_code, 503)

    def test_untrusted_forwarded_ip_is_ignored(self):
        scope = {"client": ("203.0.113.2", 1), "headers": [(b"x-forwarded-for", b"1.2.3.4")]}
        with patch.dict(os.environ, TRUSTED_PROXY_CIDRS=""):
            self.assertEqual(client_address(scope), "203.0.113.2")

    def test_idempotent_retry_skips_model(self):
        self.user()
        payload = BASE | {"research_confirmed": True}
        normalized = Applicant(**BASE).model_dump()
        digest = hashlib.sha256(json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        with patch.object(main, "existing_request", return_value={"payload_sha256": digest, "result": {"credit_score": 700}}), patch.object(main.model, "predict") as inference:
            response = self.client.post("/api/predict", json=payload, headers={"Idempotency-Key": str(uuid4())})
            self.assertEqual(response.status_code, 200)
            inference.assert_not_called()

    def test_reused_key_with_changed_input_is_conflict(self):
        self.user()
        with patch.object(main, "existing_request", return_value={"payload_sha256": "different", "result": {}}):
            response = self.client.post("/api/predict", json=BASE | {"research_confirmed": True}, headers={"Idempotency-Key": str(uuid4())})
        self.assertEqual(response.status_code, 409)

    def test_consent_and_research_confirmation_are_enforced(self):
        self.user()
        headers = {"Idempotency-Key": str(uuid4())}
        self.assertEqual(self.client.post("/api/predict", json=BASE, headers=headers).status_code, 422)
        with patch.object(main, "existing_request", return_value=None), patch.object(main, "account_status", return_value=False):
            response = self.client.post("/api/predict", json=BASE | {"research_confirmed": True}, headers=headers)
        self.assertEqual(response.status_code, 403)

    def test_account_delete_requires_recent_verified_password_auth(self):
        self.user(amr=[{"method": "password", "timestamp": time.time() - 1000}])
        with patch.object(main, "delete_account") as deletion:
            self.assertEqual(self.client.request("DELETE", "/api/account", json={"confirmation": "DELETE MY ACCOUNT"}).status_code, 403)
            deletion.assert_not_called()
        self.user(amr=[{"method": "password", "timestamp": time.time()}])
        with patch.object(main, "delete_account") as deletion:
            self.assertEqual(self.client.request("DELETE", "/api/account", json={"confirmation": "DELETE MY ACCOUNT"}).status_code, 204)
            deletion.assert_called_once_with(ACCOUNT)

    def test_export_uses_verified_owner_only(self):
        self.user()
        with patch.object(main, "export_account", return_value={"assessments": [], "consents": []}) as export:
            response = self.client.get("/api/account/export")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["Cache-Control"], "no-store")
            export.assert_called_once_with(ACCOUNT)

    def test_upstream_redirects_rate_limits_and_oversize(self):
        for status, headers, content, expected in [
            (302, {"Location": "https://evil.test"}, b"", 502),
            (429, {"Retry-After": "30"}, b"{}", 429),
            (200, {}, b"x" * (store.MAX_RESPONSE_BYTES + 1), 503),
            (200, {}, b"not json", 502),
        ]:
            calls = []
            def handler(request):
                calls.append(request)
                return httpx.Response(status, headers=headers, content=content)
            with httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False) as client, patch.object(store, "http_client", client):
                with self.assertRaises(HTTPException) as error:
                    store._request("/auth/v1/user", access_token="dummy")
                self.assertEqual(error.exception.status_code, expected)
                self.assertEqual(len(calls), 1)

    def test_model_hashes_and_prediction(self):
        self.assertIsNotNone(main.model.model)
        result = main.model.predict(Applicant(**BASE).model_dump())
        self.assertTrue(300 <= result["credit_score"] <= 900)
        self.assertTrue(0 <= result["default_probability"] <= 1)

    def test_readiness_fails_on_missing_database_setup(self):
        main.readiness_cache["at"] = 0
        with patch.object(main, "database_ready", side_effect=HTTPException(503)):
            self.assertEqual(self.client.get("/api/ready").status_code, 503)

    def test_unexpected_errors_are_sanitized_and_keep_headers(self):
        self.user()
        with patch.object(main, "account_status", side_effect=RuntimeError("private input must not appear")):
            response = self.client.get("/api/account")
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("private input", response.text)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertIn("X-Request-ID", response.headers)
        self.assertIn("Content-Security-Policy", response.headers)

    def test_verified_token_must_match_account_and_confirmed_email(self):
        account = {"id": ACCOUNT, "email_confirmed_at": "2026-10-08T00:00:00Z"}
        with patch.object(store, "_request", return_value=account):
            valid = store.verify_access_token(jwt({"sub": ACCOUNT, "role": "authenticated"}))
            self.assertEqual(valid["id"], ACCOUNT)
            with self.assertRaises(HTTPException):
                store.verify_access_token(jwt({"sub": str(uuid4()), "role": "authenticated"}))
        with patch.object(store, "_request", return_value={"id": ACCOUNT}), self.assertRaises(HTTPException) as error:
            store.verify_access_token(jwt({"sub": ACCOUNT, "role": "authenticated"}))
        self.assertEqual(error.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
