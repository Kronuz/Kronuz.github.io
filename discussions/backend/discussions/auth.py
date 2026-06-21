"""OAuth sign-in, the session cookie, and the /auth/* + /api/me routes.

The session cookie (`gc_session`) is an opaque random id; the session row lives in
the DB (see db.py). SESSION_SECRET only signs the OAuth `state` (CSRF), not the cookie.
"""
import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
import urllib.parse
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from . import db, gh
from .config import (DEFAULT_TENANT_ID, DISCUSSIONS_BACKEND, COOKIE_CROSS_SITE, OAUTH_CLIENT_ID,
                     OAUTH_ENABLED, OAUTH_SCOPE, PUBLIC_BASE_URL, SESSION_SECRET)

router = APIRouter()
_log = logging.getLogger(__name__)


# --- OAuth `state` signing (CSRF) --------------------------------------------
def _sign(value: str) -> str:
    mac = hmac.new(SESSION_SECRET.encode(), value.encode(), hashlib.sha256).hexdigest()
    return value + "." + mac


def _unsign(signed: str) -> Optional[str]:
    try:
        value, mac = signed.rsplit(".", 1)
    except ValueError:
        return None
    good = hmac.new(SESSION_SECRET.encode(), value.encode(), hashlib.sha256).hexdigest()
    return value if hmac.compare_digest(mac, good) else None


def _make_state(return_url: str) -> str:
    raw = base64.urlsafe_b64encode(
        json.dumps({"r": return_url, "n": secrets.token_hex(8), "t": int(time.time())}).encode()
    ).decode()
    return _sign(raw)


def _read_state(state: str) -> Optional[dict]:
    raw = _unsign(state)
    if not raw:
        return None
    try:
        data = json.loads(base64.urlsafe_b64decode(raw.encode()))
    except Exception:
        return None
    if int(time.time()) - int(data.get("t", 0)) > 600:
        return None
    return data


async def current_session(request: Request) -> Optional[dict]:
    """The signed-in reader for this request, or None. Shared with the comment and
    reaction routes."""
    sid = request.cookies.get("gc_session")
    if not sid:
        return None
    return await db.session_get(sid)


def is_admin(tenant_id: str, login: Optional[str]) -> bool:
    """Whether `login` moderates the given tenant's blog (its owner/delegates, from the
    tenant_admins table — seeded for the default tenant from ADMIN_LOGINS). Per-tenant:
    a moderator of one hosted blog is not automatically a moderator of another."""
    return db.tenant_is_admin(tenant_id, login)


def request_tenant(request: Request) -> str:
    """The tenant this request targets, resolved from the browser's Origin header against
    the registered tenant origins. Falls back to the default tenant when the origin isn't
    registered (phase 2 resolves but does not yet reject — that lands in phase 3) or is
    absent (same-origin /demo and non-browser callers send no Origin)."""
    return db.tenant_id_for_origin(request.headers.get("origin")) or DEFAULT_TENANT_ID


async def current_viewer(request: Request) -> Optional[dict]:
    """The reader as the store sees them: identity + token + the tenant they're viewing +
    their admin flag for that tenant, or None. The store authorizes moderation against the
    *comment's* tenant; this `is_admin` is the viewer's status for the request's tenant
    (what /api/me and the widget's moderator UI use)."""
    sess = await current_session(request)
    if not sess:
        return None
    tenant_id = request_tenant(request)
    return {
        "login": sess["login"], "name": sess["name"], "avatarUrl": sess["avatarUrl"],
        "url": sess.get("url"), "token": sess["token"],
        "tenant_id": tenant_id, "is_admin": is_admin(tenant_id, sess["login"]),
    }


@router.get("/api/me")
async def api_me(request: Request) -> dict:
    sess = await current_session(request)
    base = {"oauth": OAUTH_ENABLED, "backend": DISCUSSIONS_BACKEND}
    if not sess:
        return dict(base, authenticated=False)
    tenant_id = request_tenant(request)
    return dict(base, authenticated=True, login=sess["login"],
                avatarUrl=sess["avatarUrl"], name=sess["name"],
                isAdmin=is_admin(tenant_id, sess["login"]))


@router.get("/api/config")
async def api_config(request: Request) -> dict:
    """Per-tenant widget config for the request's blog (resolved from the Origin), so a
    tenant configures once on the server instead of baking these into its static build.
    Public (no identity); behind origin enforcement, so only a registered blog gets it.
    The widget uses these only to fill values it wasn't given via data attributes."""
    t = await db.tenant_get(request_tenant(request))
    if not t:
        return {}
    return {"repo": t.get("repo") or "", "repoUrl": t.get("repo_url") or "",
            "siteUrl": t.get("origin") or "", "stripSuffix": t.get("strip_suffix") or "",
            "giphyKey": t.get("giphy_key") or ""}


@router.get("/auth/login")
async def auth_login(return_url: str = Query("/", alias="return")):
    if not OAUTH_ENABLED:
        raise HTTPException(status_code=503, detail="OAuth not configured")
    _log.info("oauth login start: requesting scope=%r (backend=%s)", OAUTH_SCOPE, DISCUSSIONS_BACKEND)
    params = urllib.parse.urlencode({
        "client_id": OAUTH_CLIENT_ID,
        "redirect_uri": PUBLIC_BASE_URL + "/auth/callback",
        "scope": OAUTH_SCOPE,
        "state": _make_state(return_url),
        "allow_signup": "false",
    })
    return RedirectResponse("https://github.com/login/oauth/authorize?" + params)


@router.get("/auth/callback")
async def auth_callback(code: str = "", state: str = ""):
    if not _read_state(state):
        raise HTTPException(status_code=400, detail="bad state")
    token, granted_scope = await gh.exchange_code(code)
    user = await gh.user(token)
    sid = secrets.token_urlsafe(24)
    # Log who signed in + the scope GitHub actually granted (never the token), so we
    # can verify a repo-scope re-auth took effect.
    _log.info("oauth callback: login=%s granted_scope=%r requested_scope=%r",
              user.get("login"), granted_scope, OAUTH_SCOPE)
    await db.session_put(sid, {
        "token": token,
        "login": user["login"],
        "avatarUrl": user["avatar_url"],
        "name": user.get("name") or user["login"],
        "url": user.get("html_url"),
    })
    html = (
        "<!doctype html><meta charset=utf-8>"
        "<body style='font-family:sans-serif;padding:2rem'>"
        "Signed in. You can close this window."
        "<script>if(window.opener){window.opener.postMessage('gc-auth-done','*')}"
        "setTimeout(function(){window.close()},300)</script>"
    )
    resp = HTMLResponse(html)
    resp.set_cookie(
        "gc_session", sid, httponly=True,
        samesite="none" if COOKIE_CROSS_SITE else "lax",
        secure=COOKIE_CROSS_SITE, max_age=7 * 24 * 3600, path="/",
    )
    return resp


@router.post("/auth/logout")
async def auth_logout(request: Request):
    sid = request.cookies.get("gc_session")
    if sid:
        await db.session_del(sid)
    resp = JSONResponse({"ok": True})
    resp.delete_cookie("gc_session", path="/")
    return resp
