"""Every user-specific route must require a session and stay inside it."""

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test")
os.environ["GOOGLE_CLIENT_ID"] = "test-client"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402
from mongomock_motor import AsyncMongoMockClient  # noqa: E402

import server  # noqa: E402


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(server, "db", AsyncMongoMockClient()["test"])

    def fake_verify(credential, _request, _client_id):
        # The test "credential" is just the email to sign in as.
        if credential == "bad":
            raise ValueError("bad token")
        return {"email": credential, "email_verified": credential != "unverified@x.com"}

    monkeypatch.setattr(server.id_token, "verify_oauth2_token", fake_verify)
    with TestClient(server.app) as c:
        yield c


def sign_in(client, email):
    r = client.post("/api/auth/google", json={"credential": email})
    assert r.status_code == 200, r.text
    body = r.json()
    return body["id"], {"Authorization": f"Bearer {body['sessionToken']}"}


def make_project(client, headers, name="p"):
    r = client.post(
        "/api/projects",
        headers=headers,
        json={"name": name, "sourceType": "text_only", "textDescription": "x"},
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_email_only_sign_in_is_gone(client):
    assert client.post("/api/users", json={"email": "a@x.com"}).status_code in (404, 405)
    assert client.get("/api/users/email/a@x.com").status_code in (401, 404)


def test_google_sign_in_rejects_bad_and_unverified(client):
    assert client.post("/api/auth/google", json={"credential": "bad"}).status_code == 401
    assert client.post("/api/auth/google", json={"credential": "unverified@x.com"}).status_code == 401


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/projects"),
        ("post", "/api/projects"),
        ("get", "/api/projects/p1"),
        ("delete", "/api/projects/p1"),
        ("get", "/api/projects/p1/can-export"),
        ("post", "/api/projects/p1/analyze"),
        ("get", "/api/checkout/status/s1"),
        ("get", "/api/auth/me"),
        ("get", "/api/users/u1"),
        ("post", "/api/billing/verify"),
    ],
)
def test_routes_need_a_session(client, method, path):
    kwargs = {}
    if method == "post" and path in ("/api/projects", "/api/billing/verify"):
        kwargs["json"] = (
            {"name": "p", "sourceType": "text_only"}
            if path == "/api/projects"
            else {"userId": "u1", "productId": "pro", "purchaseToken": "t"}
        )
    assert getattr(client, method)(path, **kwargs).status_code == 401
    bad = {"Authorization": "Bearer not-a-session"}
    assert getattr(client, method)(path, headers=bad, **kwargs).status_code == 401


def test_projects_are_private_to_their_owner(client):
    _, alice = sign_in(client, "alice@x.com")
    _, bob = sign_in(client, "bob@x.com")
    pid = make_project(client, alice)

    # Bob sees nothing of Alice's, even when he passes her id.
    assert client.get("/api/projects", headers=bob).json() == []
    alice_id = client.get("/api/auth/me", headers=alice).json()["id"]
    assert client.get(f"/api/projects?userId={alice_id}", headers=bob).json() == []
    assert client.get(f"/api/projects/{pid}", headers=bob).status_code == 404
    assert client.get(f"/api/projects/{pid}/can-export", headers=bob).status_code == 404
    assert client.delete(f"/api/projects/{pid}", headers=bob).status_code == 404
    up = client.post(f"/api/projects/{pid}/upload", headers=bob, files={"file": ("a.zip", b"x")})
    assert up.status_code == 404

    # Alice still has it and can delete it.
    assert [p["id"] for p in client.get("/api/projects", headers=alice).json()] == [pid]
    assert client.get(f"/api/projects/{pid}", headers=alice).status_code == 200
    assert client.delete(f"/api/projects/{pid}", headers=alice).status_code == 200
    assert client.get("/api/projects", headers=alice).json() == []


def test_project_owner_comes_from_session_not_body(client):
    alice_id, alice = sign_in(client, "alice@x.com")
    _, bob = sign_in(client, "bob@x.com")
    r = client.post(
        "/api/projects",
        headers=bob,
        json={"name": "p", "sourceType": "text_only", "userId": alice_id},
    )
    assert r.status_code == 200
    assert client.get("/api/projects", headers=alice).json() == []


def test_user_record_is_self_only(client):
    alice_id, alice = sign_in(client, "alice@x.com")
    bob_id, _ = sign_in(client, "bob@x.com")
    assert client.get(f"/api/users/{alice_id}", headers=alice).status_code == 200
    assert client.get(f"/api/users/{bob_id}", headers=alice).status_code == 404


def test_billing_only_for_own_account(client):
    _, alice = sign_in(client, "alice@x.com")
    bob_id, _ = sign_in(client, "bob@x.com")
    r = client.post(
        "/api/billing/verify",
        headers=alice,
        json={"userId": bob_id, "productId": "pro", "purchaseToken": "t"},
    )
    assert r.status_code == 403


def test_logout_ends_the_session(client):
    _, alice = sign_in(client, "alice@x.com")
    assert client.get("/api/auth/me", headers=alice).status_code == 200
    assert client.post("/api/auth/logout", headers=alice).status_code == 200
    assert client.get("/api/auth/me", headers=alice).status_code == 401


def test_cors_has_no_wildcard():
    cors = [m for m in server.app.user_middleware if m.cls.__name__ == "CORSMiddleware"][0]
    assert "*" not in cors.kwargs["allow_origins"]
