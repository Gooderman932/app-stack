"""Google Play subscription verification and expiry.

The Play Developer API is replaced by a fake, so these need no Google
credentials. What is verified:
  * the tier comes from the product Google says the token bought
  * one purchase token pays for one account (stored claim + obfuscated id)
  * canceled-but-paid-through subscriptions keep access until expiry
  * a lapsed subscription is re-checked with Google: renewed -> stays paid,
    ended -> free; an outage keeps the tier for a short window only
  * profile responses never include the purchase token
"""
import asyncio
import os
from datetime import datetime, timedelta, timezone

import pytest

# Same test settings as test_auth.py, set before server is imported so this
# file also runs on its own.
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test")
os.environ.setdefault("SESSION_SECRET", "test-secret-for-local-tests-only")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-client")

import server  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from tests.test_auth import FakeDB, _auth, _user  # noqa: E402


def _now():
    return datetime.now(timezone.utc)


def _play_time(dt):
    # Play returns RFC 3339 UTC with up to nine fractional digits.
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "123Z"


def play_result(product="pro", state="SUBSCRIPTION_STATE_ACTIVE",
                expires_in=timedelta(days=30), account_for=None, **extra):
    result = {
        "subscriptionState": state,
        "lineItems": [{"productId": product, "expiryTime": _play_time(_now() + expires_in)}],
    }
    if account_for:
        result["externalAccountIdentifiers"] = {
            "obfuscatedExternalAccountId": server.play_account_id(account_for)}
    result.update(extra)
    return result


@pytest.fixture()
def play(monkeypatch):
    db = FakeDB()
    alice = _user("alice-id", "alice@example.com")
    bob = _user("bob-id", "bob@example.com")
    db.users.docs = [alice, bob]
    server.db = db
    monkeypatch.setattr(server, "PLAY_SERVICE_ACCOUNT_FILE", "/fake/service-account.json")
    google = {"result": play_result(account_for="alice-id"), "error": None, "calls": []}

    async def fake_fetch(token):
        google["calls"].append(token)
        if google["error"]:
            raise google["error"]
        return google["result"]

    monkeypatch.setattr(server, "_fetch_play_subscription", fake_fetch)
    return TestClient(server.app), db, alice, bob, google


def _verify(client, user, product="pro", token="tok-1"):
    return client.post("/api/billing/verify", headers=_auth(user), json={
        "userId": user["id"], "productId": product, "purchaseToken": token,
    })


def _doc(db, uid):
    return next(d for d in db.users.docs if d["id"] == uid)


# --- Account binding -------------------------------------------------------------
def test_account_id_matches_the_purchase_plugin():
    # Expected values come from cordova-plugin-purchase's own md5toUUID
    # ('uuid' obfuscator), run on the same inputs.
    assert server.play_account_id("alice-id") == "218f7a1b-24e1-32a6-85ce-12316d33a660"
    assert (server.play_account_id("3f2b8c1e-7d4a-4e9b-9a51-2c6d8e0f1a23")
            == "d4b79a25-db2f-3a2b-896b-34a32958decc")


def test_purchase_made_for_another_account_is_refused(play):
    client, db, alice, _, google = play
    google["result"] = play_result(account_for="bob-id")
    assert _verify(client, alice).status_code == 403
    assert _doc(db, "alice-id")["subscription"] == "free"


def test_token_claimed_by_another_account_is_refused_without_calling_google(play):
    client, db, alice, _, google = play
    db.payment_transactions.docs = [{"id": "tx-1", "userId": "bob-id", "sessionId": "tok-1"}]
    assert _verify(client, alice, token="tok-1").status_code == 409
    assert google["calls"] == []
    assert _doc(db, "alice-id")["subscription"] == "free"


def test_purchase_without_an_account_id_is_accepted(play):
    client, _, alice, _, google = play
    google["result"] = play_result()  # made before the app sent an account id
    assert _verify(client, alice).status_code == 200


# --- What was bought ---------------------------------------------------------------
def test_verify_grants_the_tier_google_reports_until_expiry(play):
    client, db, alice, _, google = play
    r = _verify(client, alice, "pro")
    assert r.status_code == 200
    assert r.json()["tier"] == "pro"
    doc = _doc(db, "alice-id")
    assert doc["subscription"] == "pro"
    assert doc["playPurchaseToken"] == "tok-1"
    expires = datetime.fromisoformat(doc["subscriptionExpiresAt"])
    assert timedelta(days=29) < expires - _now() < timedelta(days=31)
    (tx,) = db.payment_transactions.docs
    assert (tx["userId"], tx["sessionId"], tx["tier"]) == ("alice-id", "tok-1", "pro")
    assert tx["metadata"]["productId"] == "pro"


def test_a_cheaper_token_cannot_claim_a_higher_tier(play):
    client, db, alice, _, google = play
    google["result"] = play_result(product="pro", account_for="alice-id")
    r = _verify(client, alice, "team")
    assert r.status_code == 400
    assert _doc(db, "alice-id")["subscription"] == "free"


def test_unknown_product_is_refused(play):
    client, _, alice, _, google = play
    assert _verify(client, alice, "enterprise").status_code == 400
    assert google["calls"] == []


def test_canceled_but_paid_through_keeps_access_until_expiry(play):
    client, db, alice, _, google = play
    google["result"] = play_result(state="SUBSCRIPTION_STATE_CANCELED",
                                   expires_in=timedelta(days=10), account_for="alice-id")
    assert _verify(client, alice).status_code == 200
    expires = datetime.fromisoformat(_doc(db, "alice-id")["subscriptionExpiresAt"])
    assert timedelta(days=9) < expires - _now() < timedelta(days=11)


@pytest.mark.parametrize("state,expires_in", [
    ("SUBSCRIPTION_STATE_EXPIRED", timedelta(days=-1)),
    ("SUBSCRIPTION_STATE_CANCELED", timedelta(days=-1)),
    ("SUBSCRIPTION_STATE_ON_HOLD", timedelta(days=-1)),
])
def test_subscription_without_access_is_refused(play, state, expires_in):
    client, db, alice, _, google = play
    google["result"] = play_result(state=state, expires_in=expires_in, account_for="alice-id")
    assert _verify(client, alice).status_code == 400
    assert _doc(db, "alice-id")["subscription"] == "free"


def test_profile_never_exposes_the_purchase_token(play):
    client, _, alice, _, _ = play
    assert _verify(client, alice).status_code == 200
    me = client.get("/api/users/me", headers=_auth(alice)).json()
    assert me["subscription"] == "pro"
    assert "playPurchaseToken" not in me


# --- Expiry and renewal ---------------------------------------------------------------
def _lapsed(db, uid, tier="pro", ago=timedelta(hours=1)):
    _doc(db, uid).update({
        "subscription": tier,
        "subscriptionExpiresAt": (_now() - ago).isoformat(),
        "playPurchaseToken": "tok-1",
    })


def test_lapsed_subscription_that_renewed_stays_paid(play):
    client, db, alice, _, google = play
    _lapsed(db, "alice-id")
    google["result"] = play_result(expires_in=timedelta(days=30))
    me = client.get("/api/users/me", headers=_auth(alice)).json()
    assert me["subscription"] == "pro"
    assert google["calls"] == ["tok-1"]
    expires = datetime.fromisoformat(_doc(db, "alice-id")["subscriptionExpiresAt"])
    assert expires > _now() + timedelta(days=29)


def test_lapsed_subscription_that_ended_drops_to_free_once(play):
    client, db, alice, _, google = play
    _lapsed(db, "alice-id")
    google["result"] = play_result(state="SUBSCRIPTION_STATE_EXPIRED", expires_in=timedelta(hours=-1))
    me = client.get("/api/users/me", headers=_auth(alice)).json()
    assert me["subscription"] == "free"
    assert me["tierLimits"] == server.SUBSCRIPTION_TIERS["free"]
    assert _doc(db, "alice-id")["subscriptionStatus"] == "expired"
    client.get("/api/users/me", headers=_auth(alice))
    assert google["calls"] == ["tok-1"]  # downgrade stored; Google not asked again


def test_grace_period_keeps_access_and_checks_again_tomorrow(play):
    client, db, alice, _, google = play
    _lapsed(db, "alice-id")
    google["result"] = play_result(state="SUBSCRIPTION_STATE_IN_GRACE_PERIOD",
                                   expires_in=timedelta(hours=-1))
    assert client.get("/api/users/me", headers=_auth(alice)).json()["subscription"] == "pro"
    expires = datetime.fromisoformat(_doc(db, "alice-id")["subscriptionExpiresAt"])
    assert timedelta(hours=23) < expires - _now() <= timedelta(days=1)


def test_google_outage_keeps_the_tier_only_briefly(play):
    client, db, alice, _, google = play
    google["error"] = RuntimeError("Play API unavailable")
    _lapsed(db, "alice-id", ago=timedelta(hours=1))
    assert client.get("/api/users/me", headers=_auth(alice)).json()["subscription"] == "pro"
    _lapsed(db, "alice-id", ago=timedelta(days=4))
    assert client.get("/api/users/me", headers=_auth(alice)).json()["subscription"] == "free"


def test_grants_without_an_expiry_are_left_alone(play):
    client, db, alice, _, google = play
    _doc(db, "alice-id")["subscription"] = "team"
    assert client.get("/api/users/me", headers=_auth(alice)).json()["subscription"] == "team"
    assert google["calls"] == []


def test_tier_limits_follow_the_effective_tier(play):
    _, db, _, _, google = play
    _lapsed(db, "alice-id")
    google["result"] = play_result(state="SUBSCRIPTION_STATE_EXPIRED", expires_in=timedelta(hours=-1))
    limits = asyncio.run(server.get_user_tier_limits("alice-id"))
    assert limits == server.SUBSCRIPTION_TIERS["free"]


def test_play_timestamps_parse_with_nanoseconds():
    parsed = server._parse_play_time("2026-12-01T10:00:00.123456789Z")
    assert parsed == datetime(2026, 12, 1, 10, 0, 0, 123456, tzinfo=timezone.utc)
    assert server._parse_play_time("2026-12-01T10:00:00Z").tzinfo is not None
    assert server._parse_play_time("not a time") is None
    assert server._parse_play_time(None) is None
