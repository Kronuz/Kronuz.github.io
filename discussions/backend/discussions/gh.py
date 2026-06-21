"""GitHub client: a shared async HTTP client, the OAuth token exchange, the /user
identity lookup, and a /markdown render helper. Opened/closed by the app lifespan
(see app.py / runtime.py).

Sign-in is always GitHub OAuth (identity only). Beyond that, what talks to GitHub
depends on the active store: the self-hosted store keeps comments locally and renders
Markdown itself, touching GitHub only for sign-in; the github store also uses this
module's graphql()/markdown() as its transport to GitHub Discussions.
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


async def markdown(token: Optional[str], text: str, context: Optional[str] = None) -> str:
    """Render Markdown to HTML via GitHub's REST /markdown API (GFM mode), so a comment
    preview matches exactly how GitHub will render the posted comment. `context` is an
    "owner/repo" used to resolve #issue / @mention autolinks. The response body is the
    HTML itself (text/html), not JSON. Returns the HTML string.
    """
    payload: dict = {"text": text, "mode": "gfm"}
    if context:
        payload["context"] = context
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = "bearer " + token
    resp = await _http.post("https://api.github.com/markdown", json=payload, headers=headers)
    if resp.status_code in (401, 403):
        raise HTTPException(status_code=resp.status_code, detail="GitHub auth failed; sign in again")
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="GitHub markdown render failed")
    return resp.text


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
