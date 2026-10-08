import json
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from fastapi.testclient import TestClient

from app import main, supabase_store


class AccountIsolationTests(unittest.TestCase):
    def test_history_query_is_limited_to_the_signed_in_account(self):
        with patch.object(supabase_store, "_request", return_value=[]) as request:
            supabase_store.get_history(
                "account-one", "access-token", assessed_on="2026-10-08", limit=25
            )

        path = request.call_args.args[0]
        query = parse_qs(urlsplit(path).query)
        self.assertEqual(query["user_id"], ["eq.account-one"])
        self.assertEqual(
            query["created_at"],
            [
                "gte.2026-10-08T00:00:00+05:30",
                "lt.2026-10-09T00:00:00+05:30",
            ],
        )
        self.assertEqual(request.call_args.kwargs["access_token"], "access-token")

    def test_saved_assessment_is_tagged_with_authenticated_account(self):
        with patch.object(supabase_store, "_request") as request:
            supabase_store.save_assessment(
                "account-one",
                {"applicant_name": "Example"},
                {"risk_band": "LOW"},
                "access-token", "request-id", "payload-hash", "model-version",
            )

        self.assertEqual(
            request.call_args.kwargs["body"]["p_user_id"], "account-one"
        )
        self.assertEqual(
            request.call_args.kwargs["body"]["p_payload"]["applicant_name"], "Example"
        )
        self.assertTrue(request.call_args.kwargs["backend"])

    def test_assessment_read_and_delete_always_filter_by_account(self):
        with patch.object(
            supabase_store, "_request", return_value=[{"id": "record-one"}]
        ) as request:
            result = supabase_store.get_assessment(
                "record-one", "account-one", "access-token"
            )
        self.assertEqual(result, {"id": "record-one"})
        query = parse_qs(urlsplit(request.call_args.args[0]).query)
        self.assertEqual(query["user_id"], ["eq.account-one"])
        self.assertEqual(query["id"], ["eq.record-one"])

        with patch.object(supabase_store, "_request") as request:
            supabase_store.delete_assessment(
                "record-one", "account-one", "access-token"
            )
        query = parse_qs(urlsplit(request.call_args.args[0]).query)
        self.assertEqual(query["user_id"], ["eq.account-one"])
        self.assertEqual(query["id"], ["eq.record-one"])
        self.assertEqual(request.call_args.kwargs["method"], "DELETE")

    def test_api_requires_authentication_before_reading_history(self):
        with TestClient(main.app) as client:
            response = client.get("/api/history")
        self.assertEqual(response.status_code, 401)

    def test_history_api_uses_verified_account_and_local_date(self):
        main.app.dependency_overrides[main.authenticated_user] = lambda: {
            "id": "account-one",
            "access_token": "access-token",
        }
        try:
            with patch.object(main, "get_history", return_value=[]) as history:
                with TestClient(main.app) as client:
                    response = client.get("/api/history?assessed_on=2026-10-08")
            self.assertEqual(response.status_code, 200)
            history.assert_called_once_with(
                "account-one", "access-token", "2026-10-08", 50
            )
        finally:
            main.app.dependency_overrides.clear()

    def test_supabase_project_key_is_not_required_or_exposed_when_unconfigured(self):
        with patch.dict(
            "os.environ",
            {"SUPABASE_URL": "", "SUPABASE_ANON_KEY": ""},
            clear=False,
        ):
            with TestClient(main.app) as client:
                response = client.get("/api/config")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["configured"])
        self.assertNotIn("service_role", json.dumps(response.json()).lower())


if __name__ == "__main__":
    unittest.main()
