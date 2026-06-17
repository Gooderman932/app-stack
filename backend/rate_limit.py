"""Rate limiting and AI-quota helpers.

Centralises rate-limit configuration so individual endpoints declare their
intent via decorators (`@limiter.limit("...")`) without duplicating the
per-user key function.

We key on the authenticated user_id when available (carried as an `X-User-Id`
header from the frontend after Google OAuth), falling back to the client IP
address. This keeps anonymous abuse separate from authenticated abuse.

For the Gemini per-user daily quota we mirror the count to MongoDB so it
survives process restarts (slowapi's default in-memory backend resets on
deploy). Tier-based limits live in `SUBSCRIPTION_TIERS` in `server.py`.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def _key_func(request: Request) -> str:
    """Prefer authenticated user over IP for rate-limit bucketing."""
    user_id = request.headers.get("x-user-id")
    if user_id:
        return f"user:{user_id}"
    return f"ip:{get_remote_address(request)}"


# Endpoint-level limiter (decorator-based)
limiter = Limiter(key_func=_key_func, default_limits=["120/minute"])


# --- Gemini per-user daily quota -------------------------------------------------

# Default daily Gemini calls per tier (analyze + generate combined).
DAILY_GEMINI_QUOTA = {
    "free": 10,
    "pro": 200,
    "team": 1000,
}


async def check_and_consume_gemini_quota(
    db, user_id: Optional[str], tier: str
) -> tuple[bool, int, int]:
    """Atomically increment today's Gemini call counter for ``user_id``.

    Returns ``(allowed, used_today, quota)``. Anonymous callers (no user_id)
    are allowed but counted at the IP layer via slowapi.
    """
    if not user_id:
        return True, 0, 0

    quota = DAILY_GEMINI_QUOTA.get(tier, DAILY_GEMINI_QUOTA["free"])
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    doc_id = f"{user_id}:{today}"

    result = await db.gemini_usage.find_one_and_update(
        {"_id": doc_id},
        {
            "$inc": {"count": 1},
            "$setOnInsert": {
                "user_id": user_id,
                "date": today,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        },
        upsert=True,
        return_document=True,  # returns post-update doc
    )
    # Older pymongo: return_document may not be available as bool.
    used = (result or {}).get("count", 1) if isinstance(result, dict) else 1

    return used <= quota, used, quota
