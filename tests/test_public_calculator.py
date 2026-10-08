import os
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app import main, supabase_store

PAYLOAD = dict(applicant_name="Synthetic", age_years=30, annual_income=600000,
               loan_amount=250000, annuity_amount=15000, research_confirmed=True)

class PublicCalculatorTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, APP_ENV="development", REDIS_URL="")
        self.env.start()
        main.limiter._local.clear()
        main.readiness_cache["at"] = 0
        self.client = TestClient(main.app, raise_server_exceptions=False)

    def tearDown(self):
        self.env.stop()

    def test_public_prediction_never_uses_database(self):
        with patch.object(supabase_store, "_request", side_effect=AssertionError("No database")):
            response = self.client.post("/api/predict", json=PAYLOAD)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(300 <= response.json()["credit_score"] <= 900)
        self.assertNotIn("id", response.json())
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_research_confirmation_required(self):
        for value in (None, False, "true"):
            self.assertEqual(self.client.post("/api/predict", json=PAYLOAD | {"research_confirmed": value}).status_code, 422)

    def test_account_routes_retired(self):
        for path in ("/api/history", "/api/account", "/api/account/export", "/static/auth.html"):
            self.assertEqual(self.client.get(path).status_code, 404)
        for path in ("/signin", "/signup"):
            r = self.client.get(path, follow_redirects=False)
            self.assertEqual(r.status_code, 303)
            self.assertEqual(r.headers["Location"], "/workspace")

    def test_public_config_ignores_secrets(self):
        with patch.dict(os.environ, SUPABASE_URL="invalid", SUPABASE_ANON_KEY="sb_secret_private", SUPABASE_SECRET_KEY="private-secret"):
            r = self.client.get("/api/config")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json()["accounts_enabled"])
        self.assertNotIn("private", r.text)
        self.assertNotIn("supabase", r.text)

    def test_readiness_requires_no_auth_provider(self):
        with patch.dict(os.environ, APP_ENV="production", LAUNCH_SETTINGS_REVIEWED="true", RATE_LIMIT_SALT="x" * 32), patch.object(main.limiter, "ready", return_value=True), patch.object(supabase_store, "_request", side_effect=AssertionError("No database")):
            self.assertEqual(self.client.get("/api/ready").status_code, 200)

    def test_readiness_fails_on_missing_redis_or_launch_review(self):
        with patch.dict(os.environ, APP_ENV="production", LAUNCH_SETTINGS_REVIEWED="false", RATE_LIMIT_SALT="x" * 32), patch.object(main.limiter, "ready", return_value=True):
            self.assertEqual(self.client.get("/api/ready").status_code, 503)
        main.readiness_cache["at"] = 0
        with patch.object(main.limiter, "ready", return_value=False):
            self.assertEqual(self.client.get("/api/ready").status_code, 503)

    def test_prediction_rate_limit_stops_inference(self):
        with patch.object(main.model, "predict", return_value={"credit_score": 700}) as inference:
            responses = [self.client.post("/api/predict", json=PAYLOAD) for _ in range(11)]
        self.assertEqual(inference.call_count, 10)
        self.assertEqual(responses[-1].status_code, 429)
        self.assertIn("Retry-After", responses[-1].headers)

    def test_global_budget_enforced(self):
        for _ in range(60):
            main.limiter.check("predict-global", 60)
        with patch.object(main.model, "predict") as inference:
            self.assertEqual(self.client.post("/api/predict", json=PAYLOAD).status_code, 429)
            inference.assert_not_called()

    def test_busy_model_and_exception_release_capacity(self):
        with patch.object(main, "inference_slots") as slots:
            slots.acquire.return_value = False
            self.assertEqual(self.client.post("/api/predict", json=PAYLOAD).status_code, 503)
            slots.release.assert_not_called()
            slots.acquire.return_value = True
            with patch.object(main.model, "predict", side_effect=RuntimeError("private input")):
                r = self.client.post("/api/predict", json=PAYLOAD)
            slots.release.assert_called_once()
        self.assertEqual(r.status_code, 500)
        self.assertNotIn("private input", r.text)
        self.assertIn("Content-Security-Policy", r.headers)
