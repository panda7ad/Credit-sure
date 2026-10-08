import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import fakeredis
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app import main
from app.schemas import Applicant
from app.security import RateLimiter, client_address

BASE = dict(applicant_name="Synthetic A", age_years=30, annual_income=600000, loan_amount=250000, annuity_amount=15000)
ENV = {"APP_ENV": "development", "REDIS_URL": ""}

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

    def test_model_hashes_and_prediction(self):
        self.assertIsNotNone(main.model.model)
        result = main.model.predict(Applicant(**BASE).model_dump())
        self.assertTrue(300 <= result["credit_score"] <= 900)
        self.assertTrue(0 <= result["default_probability"] <= 1)

if __name__ == "__main__":
    unittest.main()
