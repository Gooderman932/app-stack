"""Auth / ownership tests for app-stack (StackPilot).

Runs against the real FastAPI app with an in-memory fake MongoDB, so it
needs NO MongoDB, NO Gemini key and NO Google credentials:

    cd backend && python -m pytest tests/test_auth.py -v

What is verified here:
  * email-only POST /api/users is gone (404) — it let anyone log in as anyone
  * every user/project/billing route requires a Bearer session token (401)
  * a token for user A cannot read/modify/delete user B's data (403)
  * the rightful owner can still list/get/create/delete their own projects
  * POST /api/projects ignores a spoofed userId in the body
  * upload requires ownership and enforces .zip-only + 10 MB limit
  * CORS never defaults to '*' with credentials
  * Google sign-in rejects invalid tokens and unverified emails
  * POST /api/auth/logout revokes every token issued before it

What is NOT verified here (needs live services — see launch-ready doc):
  * POST /api/auth/google with a real Google ID token
  * /api/projects/{id}/analyze and /generate (need Gemini + MongoDB)
  * /api/billing/verify end-to-end (needs Google Play service account)
"""
import io
import os
import sys
import zipfile
from pathlib import Path

import pytest

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test")
os.environ.setdefault("SESSION_SECRET", "test-secret-for-local-tests-only")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-client")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


# --- In-memory fake MongoDB (only the operations server.py uses) -----------
class FakeCursor:
    def __init__(self, docs):
        self._docs = list(docs)

    def sort(self, _key, _direction=-1):
        return self

    async def to_list(self, n):
        return list(self._docs)[:n]


def _matches(doc, filt):
    return all(doc.get(k) == v for k, v in filt.items())


class FakeCollection:
    def __init__(self):
        self.docs = []

    async def find_one(self, filt, _proj=None):
        for d in self.docs:
            if _matches(d, filt):
                return dict(d)
        return None

    async def insert_one(self, doc):
        self.docs.append(dict(doc))

        class R:
            inserted_id = doc.get("id")

        return R()

    async def update_one(self, filt, update, upsert=False):
        for d in self.docs:
            if _matches(d, filt):
                for k, v in update.get("$set", {}).items():
                    d[k] = v
                for k, v in update.get("$inc", {}).items():
                    d[k] = d.get(k, 0) + v
                return
        if upsert:
            doc = dict(filt)
            doc.update(update.get("$set", {}))
            self.docs.append(doc)

    async def count_documents(self, filt):
        return sum(1 for d in self.docs if _matches(d, filt))

    def find(self, filt, _proj=None):
        return FakeCursor([dict(d) for d in self.docs if _matches(d, filt)])

    async def delete_one(self, filt):
        for i, d in enumerate(self.docs):
            if _matches(d, filt):
                del self.docs[i]
                return

    async def find_one_and_update(self, *a, **k):
        return None


class FakeDB:
    def __init__(self):
        self.users = FakeCollection()
        self.projects = FakeCollection()
        self.payment_transactions = FakeCollection()
        self.gemini_usage = FakeCollection()


def _user(uid, email):
    return {
        "id": uid, "email": email, "name": email.split("@")[0],
        "subscription": "free", "subscriptionStatus": "active",
        "projectCount": 0,
        "createdAt": "2026-01-01T00:00:00+00:00",
        "updatedAt": "2026-01-01T00:00:00+00:00",
    }


def _project(pid, uid):
    return {
        "id": pid, "name": f"project-{pid}", "sourceType": "text_only",
        "sourceUrl": None, "uploadRef": None, "textDescription": "test",
        "theme": "dark", "aiProvider": "gemini", "useEmergentKey": True,
        "detectedTechStack": {}, "buildSteps": {}, "deploymentPlans": {},
        "docs": {}, "status": "pending", "configFiles": [], "envVars": [],
        "reanalyzeCount": 0, "userId": uid,
        "createdAt": "2026-01-01T00:00:00+00:00",
        "updatedAt": "2026-01-01T00:00:00+00:00",
    }


@pytest.fixture()
def seeded():
    db = FakeDB()
    alice = _user("alice-id", "alice@example.com")
    bob = _user("bob-id", "bob@example.com")
    db.users.docs = [alice, bob]
    db.projects.docs = [_project("proj-alice", "alice-id"), _project("proj-bob", "bob-id")]
    db.payment_transactions.docs = [{
        "id": "tx-bob", "userId": "bob-id", "sessionId": "sess-bob",
        "tier": "pro", "amount": 12.0, "currency": "usd",
        "status": "paid", "paymentStatus": "paid",
    }]
    server.db = db
    client = TestClient(server.app)
    return client, db, alice, bob


def _auth(user):
    return {"Authorization": f"Bearer {server.create_session_token(user)}"}


def _zip_bytes(name="test.zip"):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("package.json", '{"name": "x"}')
    return buf.getvalue()


# --- The removed email-only login -------------------------------------------
def test_post_users_email_login_is_gone(seeded):
    client, *_ = seeded
    r = client.post("/api/users", json={"email": "alice@example.com", "name": "Alice"})
    assert r.status_code == 404, r.text


def test_get_user_by_email_is_gone(seeded):
    client, *_ = seeded
    r = client.get("/api/users/email/alice@example.com")
    assert r.status_code == 404


# --- Unauthenticated access is rejected --------------------------------------
@pytest.mark.parametrize("method,url", [
    ("GET", "/api/projects"),
    ("GET", "/api/projects/proj-alice"),
    ("GET", "/api/users/me"),
    ("GET", "/api/users/alice-id"),
    ("GET", "/api/projects/proj-alice/can-export"),
    ("DELETE", "/api/projects/proj-alice"),
    ("POST", "/api/projects"),
    ("POST", "/api/projects/proj-alice/upload"),
    ("POST", "/api/projects/proj-alice/analyze"),
    ("POST", "/api/projects/proj-alice/generate"),
    ("POST", "/api/billing/verify"),
    ("GET", "/api/checkout/status/sess-bob"),
])
def test_unauthenticated_is_401(seeded, method, url):
    client, *_ = seeded
    r = client.request(method, url, json={} if method in ("POST",) else None)
    assert r.status_code == 401, (method, url, r.status_code, r.text)


def test_tampered_token_is_401(seeded):
    client, *_ = seeded
    r = client.get("/api/projects", headers={"Authorization": "Bearer not.a.real.token"})
    assert r.status_code == 401


# --- Owner access works, cross-user access is rejected ------------------------
def test_owner_lists_only_own_projects(seeded):
    client, _, alice, _ = seeded
    r = client.get("/api/projects", headers=_auth(alice))
    assert r.status_code == 200, r.text
    ids = [p["id"] for p in r.json()]
    assert ids == ["proj-alice"]


def test_list_with_spoofed_userid_param_is_403(seeded):
    client, _, alice, bob = seeded
    r = client.get(f"/api/projects?userId={bob['id']}", headers=_auth(alice))
    assert r.status_code == 403


def test_get_other_users_project_is_403(seeded):
    client, _, alice, _ = seeded
    r = client.get("/api/projects/proj-bob", headers=_auth(alice))
    assert r.status_code == 403


def test_get_own_project_is_200(seeded):
    client, _, alice, _ = seeded
    r = client.get("/api/projects/proj-alice", headers=_auth(alice))
    assert r.status_code == 200
    assert r.json()["id"] == "proj-alice"


def test_get_other_user_profile_is_403_and_own_is_200(seeded):
    client, _, alice, bob = seeded
    assert client.get(f"/api/users/{bob['id']}", headers=_auth(alice)).status_code == 403
    r = client.get(f"/api/users/{alice['id']}", headers=_auth(alice))
    assert r.status_code == 200
    assert r.json()["email"] == "alice@example.com"
    r = client.get("/api/users/me", headers=_auth(alice))
    assert r.status_code == 200
    assert r.json()["email"] == "alice@example.com"


def test_create_project_ignores_spoofed_userid(seeded):
    client, db, alice, bob = seeded
    r = client.post("/api/projects", headers=_auth(alice), json={
        "name": "spoof-attempt", "sourceType": "text_only",
        "textDescription": "x", "userId": bob["id"],
    })
    assert r.status_code == 200, r.text
    assert r.json()["userId"] == alice["id"]
    assert db.projects.docs[-1]["userId"] == alice["id"]


def test_delete_other_users_project_is_403_and_own_is_200(seeded):
    client, db, alice, _ = seeded
    assert client.delete("/api/projects/proj-bob", headers=_auth(alice)).status_code == 403
    assert len(db.projects.docs) == 2
    r = client.delete("/api/projects/proj-alice", headers=_auth(alice))
    assert r.status_code == 200
    assert len(db.projects.docs) == 1


def test_can_export_other_users_project_is_403(seeded):
    client, _, alice, _ = seeded
    assert client.get("/api/projects/proj-bob/can-export", headers=_auth(alice)).status_code == 403
    r = client.get("/api/projects/proj-alice/can-export", headers=_auth(alice))
    assert r.status_code == 200
    assert r.json()["canExport"] is False  # free tier


# --- Billing / checkout scoping ----------------------------------------------
def test_billing_verify_for_other_user_is_403(seeded):
    client, _, alice, bob = seeded
    r = client.post("/api/billing/verify", headers=_auth(alice), json={
        "userId": bob["id"], "productId": "pro", "purchaseToken": "tok",
    })
    assert r.status_code == 403


def test_checkout_status_other_users_session_is_not_visible(seeded):
    client, _, alice, _ = seeded
    r = client.get("/api/checkout/status/sess-bob", headers=_auth(alice))
    assert r.status_code == 200
    # Same "pending" response as a missing session — no leak of Bob's paid tx.
    assert r.json()["status"] == "pending"


# --- Upload limits -------------------------------------------------------------
def test_upload_wrong_owner_is_403(seeded):
    client, _, alice, _ = seeded
    r = client.post("/api/projects/proj-bob/upload", headers=_auth(alice),
                    files={"file": ("t.zip", _zip_bytes(), "application/zip")})
    assert r.status_code == 403


def test_upload_non_zip_is_400(seeded):
    client, _, alice, _ = seeded
    r = client.post("/api/projects/proj-alice/upload", headers=_auth(alice),
                    files={"file": ("evil.exe", b"MZ" + b"x" * 100, "application/octet-stream")})
    assert r.status_code == 400


def test_upload_oversize_is_413(seeded):
    client, _, alice, _ = seeded
    big = b"PK\x03\x04" + b"x" * (server.MAX_UPLOAD_BYTES + 1)
    r = client.post("/api/projects/proj-alice/upload", headers=_auth(alice),
                    files={"file": ("big.zip", big, "application/zip")})
    assert r.status_code == 413


def test_upload_valid_zip_by_owner_is_200(seeded):
    client, _, alice, _ = seeded
    r = client.post("/api/projects/proj-alice/upload", headers=_auth(alice),
                    files={"file": ("t.zip", _zip_bytes(), "application/zip")})
    assert r.status_code == 200, r.text
    assert r.json()["message"] == "File uploaded"


# --- CORS safe default ---------------------------------------------------------
def test_cors_default_is_not_wildcard(monkeypatch):
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    assert server._cors_origins() == ["http://localhost:3000"]
    monkeypatch.setenv("CORS_ORIGINS", "*,http://localhost:3000")
    assert server._cors_origins() == ["http://localhost:3000"]
    monkeypatch.setenv("CORS_ORIGINS", "https://app.example.com")
    assert server._cors_origins() == ["https://app.example.com"]


def test_parse_uploaded_zip_rejects_zip_bomb():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        # Header claims a huge uncompressed file; total exceeds the cap.
        info = zipfile.ZipInfo("big.txt")
        info.file_size = server.MAX_UPLOAD_UNCOMPRESSED_BYTES + 1
        zf.writestr(info, b"x" * 10)
    assert server.parse_uploaded_zip(buf.getvalue()) == {}


# --- Google sign-in -------------------------------------------------------
def _fake_google(monkeypatch, verified=True):
    def verify(credential, _request, _client_id):
        if credential == "bad":
            raise ValueError("bad token")
        return {"email": credential, "email_verified": verified, "name": "Test"}

    monkeypatch.setattr(server.id_token, "verify_oauth2_token", verify)


def test_google_sign_in_rejects_an_invalid_token(seeded, monkeypatch):
    client, *_ = seeded
    _fake_google(monkeypatch)
    assert client.post("/api/auth/google", json={"credential": "bad"}).status_code == 401


def test_google_sign_in_rejects_an_unverified_email(seeded, monkeypatch):
    client, db, *_ = seeded
    _fake_google(monkeypatch, verified=False)
    r = client.post("/api/auth/google", json={"credential": "alice@example.com"})
    assert r.status_code == 401, r.text
    assert "sessionToken" not in r.text


def test_google_sign_in_issues_a_working_session(seeded, monkeypatch):
    client, *_ = seeded
    _fake_google(monkeypatch)
    r = client.post("/api/auth/google", json={"credential": "carol@example.com"})
    assert r.status_code == 200, r.text
    headers = {"Authorization": f"Bearer {r.json()['sessionToken']}"}
    me = client.get("/api/users/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == "carol@example.com"


# --- Sign-out ---------------------------------------------------------------
def test_logout_requires_a_session(seeded):
    client, *_ = seeded
    assert client.post("/api/auth/logout").status_code == 401


def test_logout_revokes_existing_tokens(seeded, monkeypatch):
    client, db, alice, _bob = seeded
    old = _auth(alice)
    assert client.get("/api/users/me", headers=old).status_code == 200

    assert client.post("/api/auth/logout", headers=old).status_code == 200
    assert client.get("/api/users/me", headers=old).status_code == 401

    # Signing in again issues a token for the new session version.
    _fake_google(monkeypatch)
    r = client.post("/api/auth/google", json={"credential": "alice@example.com"})
    assert r.status_code == 200, r.text
    fresh = {"Authorization": f"Bearer {r.json()['sessionToken']}"}
    assert client.get("/api/users/me", headers=fresh).status_code == 200
    assert client.get("/api/users/me", headers=old).status_code == 401


def test_logout_only_affects_the_caller(seeded):
    client, _db, alice, bob = seeded
    bob_headers = _auth(bob)
    assert client.post("/api/auth/logout", headers=_auth(alice)).status_code == 200
    assert client.get("/api/users/me", headers=bob_headers).status_code == 200
