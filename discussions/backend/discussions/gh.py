"""GitHub OAuth client: a shared async HTTP client plus the OAuth token exchange and
the /user identity lookup. Opened/closed by the app lifespan (see app.py).

This is the ONLY place the backend talks to GitHub, and only for sign-in/identity:
comments live in our SQLite store and Markdown is rendered locally (md.py), so there
is no server-side GitHub token anymore.
"""
import json
from typing import Optional

import httpx
from fastapi import HTTPException

from .config import OAUTH_CLIENT_ID, OAUTH_CLIENT_SECRET, PUBLIC_BASE_URL

# One shared async HTTP client (connection pooling) for the OAuth calls, opened for
# the app's lifetime by the lifespan.
_http: Optional[httpx.AsyncClient] = None


async def init() -> None:
    global _http
    _http = httpx.AsyncClient(timeout=15.0, headers={"User-Agent": "blog-comments"})


async def close() -> None:
    if _http is not None:
        await _http.aclose()


async def exchange_code(code: str) -> tuple:
    """Exchange an OAuth code for (access_token, granted_scope). The scope string is
    what GitHub actually granted (may differ from what we requested)."""
    resp = await _http.post(
        "https://github.com/login/oauth/access_token",
        data={
            "client_id": OAUTH_CLIENT_ID,
            "client_secret": OAUTH_CLIENT_SECRET,
            "code": code,
            "redirect_uri": PUBLIC_BASE_URL + "/auth/callback",
        },
        headers={"Accept": "application/json"},
    )
    data = resp.json()
    if "access_token" not in data:
        raise HTTPException(status_code=502, detail="oauth exchange failed: " + json.dumps(data))
    return data["access_token"], data.get("scope", "")


async def user(token: str) -> dict:
    resp = await _http.get(
        "https://api.github.com/user",
        headers={"Authorization": "bearer " + token, "Accept": "application/vnd.github+json"},
    )
    return resp.json()


async def graphql(token: str, query: str, variables: dict) -> dict:
    """POST a GraphQL query/mutation to GitHub with `token` and return its `data`.

    Used only by the github store. Raises HTTPException for transport and GraphQL
    errors, mapping permission/access failures (e.g. the org's OAuth-App restriction,
    or editing someone else's comment) to 403 so the widget shows a clean "not
    allowed" rather than a 500.
    """
    resp = await _http.post(
        "https://api.github.com/graphql",
        json={"query": query, "variables": variables},
        headers={"Authorization": "bearer " + token, "Accept": "application/vnd.github+json"},
    )
    if resp.status_code in (401, 403):
        raise HTTPException(status_code=resp.status_code, detail="GitHub auth failed; sign in again")
    try:
        payload = resp.json()
    except Exception:
        raise HTTPException(status_code=502, detail="GitHub returned a non-JSON response")
    errors = payload.get("errors")
    if errors:
        msg = errors[0].get("message", "GraphQL error")
        etype = (errors[0].get("type") or "").upper()
        denied = etype == "FORBIDDEN" or "not accessible" in msg.lower() or "permission" in msg.lower()
        raise HTTPException(status_code=403 if denied else 502, detail="GitHub: " + msg)
    return payload.get("data") or {}
