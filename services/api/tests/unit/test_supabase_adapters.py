import unittest
from pathlib import Path

import jwt

from services.api.app.auth import AuthenticationError, SupabaseJWTVerifier
from services.api.app.storage import StorageError, SupabaseStorage


class FakeResponse:
    def __init__(self, status_code=200, body=None):
        self.status_code = status_code
        self.body = body or {}

    def json(self):
        return self.body


class FakeHttpClient:
    def __init__(self):
        self.response = FakeResponse()
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        return self.response

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        return self.response

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.response


class SupabaseAdapterTests(unittest.TestCase):
    def test_password_login_and_legacy_token_verification(self):
        client = FakeHttpClient()
        verifier = SupabaseJWTVerifier(
            "https://project.supabase.co", "publishable", http_client=client
        )
        client.response = FakeResponse(
            body={
                "access_token": "access",
                "refresh_token": "refresh",
                "token_type": "bearer",
                "expires_in": 3600,
            }
        )
        self.assertEqual(
            verifier.sign_in("officer@example.test", "password")["access_token"], "access"
        )
        self.assertEqual(client.calls[0][2]["params"], {"grant_type": "password"})

        client.response = FakeResponse(
            body={"id": "11111111-1111-1111-1111-111111111111", "email": "officer@example.test"}
        )
        token = jwt.encode(
            {"sub": "ignored"}, "test-secret-with-at-least-32-bytes", algorithm="HS256"
        )
        user = verifier.verify(token)
        self.assertEqual(user.email, "officer@example.test")
        self.assertEqual(client.calls[-1][2]["headers"]["apikey"], "publishable")

    def test_login_rejection_is_generic(self):
        client = FakeHttpClient()
        client.response = FakeResponse(status_code=400)
        verifier = SupabaseJWTVerifier(
            "https://project.supabase.co", "publishable", http_client=client
        )
        with self.assertRaisesRegex(AuthenticationError, "Invalid email or password"):
            verifier.sign_in("officer@example.test", "wrong")

    def test_private_storage_upload_and_cleanup(self):
        client = FakeHttpClient()
        storage = SupabaseStorage(
            "https://project.supabase.co", "server-secret", "mosaic-documents", http_client=client
        )
        storage.upload("user/case/a file.pdf", b"%PDF-fixture", "application/pdf")
        method, url, options = client.calls[-1]
        self.assertEqual(method, "POST")
        self.assertIn("a%20file.pdf", url)
        self.assertEqual(options["headers"]["Authorization"], "Bearer server-secret")
        storage.remove(["user/case/a file.pdf"])
        self.assertEqual(client.calls[-1][2]["json"], {"prefixes": ["user/case/a file.pdf"]})

        client.response = FakeResponse(status_code=500)
        with self.assertRaises(StorageError):
            storage.upload("user/case/b.pdf", b"%PDF-fixture", "application/pdf")

    def test_migration_contains_security_storage_and_vector_contracts(self):
        repository = Path(__file__).resolve().parents[4]
        sql = (repository / "supabase/migrations/202609080001_initial_backend.sql").read_text()
        for contract in (
            "extensions.vector(1024)",
            "using hnsw",
            "enable row level security",
            "audit_events is append-only",
            "'mosaic-documents'",
            "auth.uid()",
        ):
            self.assertIn(contract, sql)


if __name__ == "__main__":
    unittest.main()
