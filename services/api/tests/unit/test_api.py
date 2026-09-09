import unittest
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from services.api.app.auth import AuthenticatedUser, AuthenticationError
from services.api.app.config import Settings
from services.api.app.main import create_app

USER_ID = "11111111-1111-1111-1111-111111111111"


class FakeVerifier:
    def verify(self, token):
        if token != "valid-token":
            raise AuthenticationError("Invalid token")
        return AuthenticatedUser(USER_ID, "officer@example.test", {"sub": USER_ID})

    def sign_in(self, email, password):
        if email != "officer@example.test" or password != "correct-password":
            raise AuthenticationError("Invalid email or password")
        return {
            "access_token": "valid-token",
            "refresh_token": "refresh-token",
            "token_type": "bearer",
            "expires_in": 3600,
        }


class FakeDatabase:
    def __init__(self):
        self.cases = {}
        self.documents = []
        self.runs = {}

    def create_case(self, owner_id, title, description):
        now = datetime.now(UTC)
        item = {
            "id": uuid4(),
            "created_by": UUID(owner_id),
            "tender_title": title,
            "description": description,
            "status": "draft",
            "created_at": now,
            "updated_at": now,
        }
        self.cases[item["id"]] = item
        return item

    def get_case(self, case_id, owner_id):
        item = self.cases.get(case_id)
        return item if item and item["created_by"] == UUID(owner_id) else None

    def create_document(self, document):
        item = {
            key: document[key]
            for key in (
                "id",
                "case_id",
                "kind",
                "original_filename",
                "content_type",
                "size_bytes",
                "sha256",
            )
        }
        item.update(processing_status="uploaded", created_at=datetime.now(UTC))
        self.documents.append(item)
        return item

    def list_documents(self, case_id, owner_id):
        if self.get_case(case_id, owner_id) is None:
            return []
        return [item for item in self.documents if item["case_id"] == case_id]

    def get_documents_for_run(self, case_id, owner_id):
        if self.get_case(case_id, owner_id) is None:
            return []
        return [item for item in self.documents if item["case_id"] == case_id]

    def create_verification_run(self, case_id, owner_id):
        if self.get_case(case_id, owner_id) is None:
            return None
        now = datetime.now(UTC)
        run = {
            "id": uuid4(),
            "case_id": UUID(str(case_id)),
            "status": "queued",
            "policy_version": "tender-evidence-quota-v2",
            "score": None,
            "result": None,
            "error_message": None,
            "created_at": now,
            "started_at": None,
            "completed_at": None,
        }
        self.runs[run["id"]] = run
        return dict(run)

    def get_verification_run(self, run_id, owner_id):
        run = self.runs.get(run_id)
        if run and self.get_case(run["case_id"], owner_id):
            return run
        return None

    def mark_verification_running(self, run_id):
        self.runs[run_id].update(status="running", started_at=datetime.now(UTC))

    def complete_verification_run(self, run_id, criteria, report):
        self.runs[run_id].update(
            status="completed",
            score=report["score"],
            result=report,
            completed_at=datetime.now(UTC),
        )

    def fail_verification_run(self, run_id, message):
        self.runs[run_id].update(
            status="failed", error_message=message, completed_at=datetime.now(UTC)
        )


class FakeStorage:
    def __init__(self):
        self.uploads = {}
        self.removed = []

    def upload(self, path, content, content_type):
        self.uploads[path] = (content, content_type)

    def remove(self, paths):
        self.removed.extend(paths)


class FakeRunner:
    def run(self, documents, *, force_ocr_bidder=False, top_k=5):
        return {"criteria": [{"id": "C1"}]}, {
            "score": 100,
            "results": [],
            "review_required": False,
            "recommendation": "qualify",
        }


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.database = FakeDatabase()
        self.storage = FakeStorage()
        settings = Settings(max_upload_bytes=32, cors_origins="http://localhost:3000")
        self.client = TestClient(
            create_app(
                settings=settings,
                database=self.database,
                storage=self.storage,
                verifier=FakeVerifier(),
                runner=FakeRunner(),
            )
        )
        self.headers = {"Authorization": "Bearer valid-token"}

    def create_case(self):
        response = self.client.post(
            "/v1/cases", json={"tender_title": "Road works tender"}, headers=self.headers
        )
        self.assertEqual(response.status_code, 201)
        return response.json()["id"]

    def test_health_and_authentication(self):
        self.assertEqual(self.client.get("/health").json(), {"status": "ok", "configured": True})
        self.assertEqual(self.client.get("/v1/me").status_code, 401)
        response = self.client.get("/v1/me", headers=self.headers)
        self.assertEqual(response.json()["email"], "officer@example.test")

    def test_login_returns_a_token_for_swagger_authorization(self):
        response = self.client.post(
            "/v1/auth/login",
            json={"email": "officer@example.test", "password": "correct-password"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["access_token"], "valid-token")
        rejected = self.client.post(
            "/v1/auth/login",
            json={"email": "officer@example.test", "password": "wrong-password"},
        )
        self.assertEqual(rejected.status_code, 401)

    def test_create_get_upload_and_list(self):
        case_id = self.create_case()
        fetched = self.client.get(f"/v1/cases/{case_id}", headers=self.headers)
        self.assertEqual(fetched.json()["tender_title"], "Road works tender")
        uploaded = self.client.post(
            f"/v1/cases/{case_id}/documents",
            headers=self.headers,
            data={"kind": "tender"},
            files={"file": ("tender.pdf", b"%PDF-1.7\nfixture", "application/pdf")},
        )
        self.assertEqual(uploaded.status_code, 201, uploaded.text)
        self.assertEqual(uploaded.json()["kind"], "tender")
        self.assertEqual(len(self.storage.uploads), 1)
        listed = self.client.get(f"/v1/cases/{case_id}/documents", headers=self.headers)
        self.assertEqual(len(listed.json()), 1)

    def test_upload_rejects_wrong_type_invalid_pdf_and_oversize(self):
        case_id = self.create_case()
        url = f"/v1/cases/{case_id}/documents"
        wrong_type = self.client.post(
            url,
            headers=self.headers,
            data={"kind": "bidder"},
            files={"file": ("bidder.txt", b"hello", "text/plain")},
        )
        self.assertEqual(wrong_type.status_code, 415)
        invalid = self.client.post(
            url,
            headers=self.headers,
            data={"kind": "bidder"},
            files={"file": ("bidder.pdf", b"not a pdf", "application/pdf")},
        )
        self.assertEqual(invalid.status_code, 400)
        oversize = self.client.post(
            url,
            headers=self.headers,
            data={"kind": "bidder"},
            files={"file": ("bidder.pdf", b"%PDF-" + b"x" * 40, "application/pdf")},
        )
        self.assertEqual(oversize.status_code, 413)

    def test_unknown_case_is_not_exposed(self):
        response = self.client.get(f"/v1/cases/{uuid4()}", headers=self.headers)
        self.assertEqual(response.status_code, 404)

    def test_verification_run_requires_documents_then_returns_report(self):
        case_id = self.create_case()
        missing = self.client.post(
            f"/v1/cases/{case_id}/verification-runs", json={}, headers=self.headers
        )
        self.assertEqual(missing.status_code, 409)
        for kind in ("tender", "bidder"):
            uploaded = self.client.post(
                f"/v1/cases/{case_id}/documents",
                headers=self.headers,
                data={"kind": kind},
                files={"file": (f"{kind}.pdf", b"%PDF-1.7\nfixture", "application/pdf")},
            )
            self.assertEqual(uploaded.status_code, 201)
        started = self.client.post(
            f"/v1/cases/{case_id}/verification-runs",
            json={"force_ocr_bidder": True, "top_k": 5},
            headers=self.headers,
        )
        self.assertEqual(started.status_code, 202, started.text)
        run_id = started.json()["id"]
        result = self.client.get(f"/v1/verification-runs/{run_id}", headers=self.headers)
        self.assertEqual(result.json()["status"], "completed")
        self.assertEqual(result.json()["score"], 100)


if __name__ == "__main__":
    unittest.main()
