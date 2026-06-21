"""Comments backend — application wiring.

Self-hosted blog comments with a pluggable store. The default (selfhosted) store keeps
comments, replies, edits, hides, and reactions in a Database driver (SQLite today),
keyed by GitHub login; OAuth is used only to learn who the reader is, and Markdown is
rendered locally with cmark-gfm (md.py). An alternative `github` store writes straight
to GitHub Discussions with the reader's own token (giscus-style); it needs none of the
database/Markdown machinery, so that form's deployment stays lean.

The seams that keep this swappable, all wired together by runtime.py:
    Store          (store/)     — the comment system (selfhosted | github)
    Database       (db/)        — persistence driver (sqlite; MySQL/Postgres later)
    SessionStore   (sessions.py)— signed-in reader sessions (lru | db | cookie)
    TenantRegistry (tenants.py) — Origin -> tenant, moderators, widget config (config | db)

Layout:
    config.py     settings from the environment (STORE/DATABASE/SESSION_STORE/TENANTS)
    runtime.py    builds + holds the Store/Database/SessionStore/TenantRegistry; startup/shutdown
    db/           Database drivers: base (interface) + sqlite
    sessions.py   SessionStore: lru (default for github) | db | cookie
    tenants.py    TenantRegistry: config (single tenant) | db (multi-tenant)
    md.py         local Markdown -> HTML renderer (cmark-gfm); used by the selfhosted store
    gh.py         GitHub client: OAuth token exchange + /user identity (+ github store transport)
    auth.py       OAuth + session cookie + /auth/*, /api/me, /api/config, is_admin, current_viewer
    store/        the comment store: base (interface) + selfhosted + github
    comments.py   /api/comments (+ /edit, /delete, /hide), /api/preview — thin routes
    reactions.py  /api/react — thin route
    app.py        this file: app, lifespan, CORS, origin enforcement, /api/health, static

Run:
    pip install -e .[sqlite]
    REPO=<owner>/<repo> ADMIN_LOGINS=<your-login> \
      OAUTH_CLIENT_ID=... OAUTH_CLIENT_SECRET=... \
      ALLOWED_ORIGINS="https://<your>.pages.github.io" \
      uvicorn discussions.app:app --host 0.0.0.0 --port 8443
"""
import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import auth, comments, reactions, runtime
from .config import (ALLOWED_ORIGINS, DEV_ORIGINS, LOG_LEVEL, REPO, REQUEST_MAX_BYTES,
                     WIDGET_DIR)

# How often to refresh the in-process tenant cache so a tenant added out-of-process (the
# admin CLI) becomes active without restarting the server (multi-tenant phase 3).
TENANT_REFRESH_SECONDS = 60


def _setup_logging() -> None:
    # The app logs to stdout; run.sh owns the single log file (it redirects the
    # server's stdout/stderr there under systemd, since the journal isn't readable on
    # the host). So uvicorn's output, our app logs, and any pre-logging startup
    # traceback all land in one ordered file. The format carries %(name)s so each line
    # shows which module logged it. Idempotent: don't stack handlers across reloads.
    logger = logging.getLogger("discussions")
    logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    logger.propagate = False
    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        h = logging.StreamHandler(sys.stdout)
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        logger.addHandler(h)


async def _session_sweeper() -> None:
    # Hourly background sweep of expired sessions; lazy on-read cleanup handles the rest.
    # The active SessionStore decides what (if anything) this does.
    while True:
        await asyncio.sleep(3600)
        try:
            await runtime.session_store().sweep()
        except Exception:
            pass


async def _tenant_cache_refresher() -> None:
    # Periodically reload the tenant registry so a tenant created out-of-process (the
    # admin CLI) starts resolving + passing CORS/origin checks without a server restart.
    while True:
        await asyncio.sleep(TENANT_REFRESH_SECONDS)
        try:
            await runtime.tenants().load()
        except Exception:
            pass


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _setup_logging()
    await runtime.startup()  # build + bring up store, db (if needed), sessions, tenants
    tasks = [asyncio.create_task(_session_sweeper()),
             asyncio.create_task(_tenant_cache_refresher())]
    try:
        yield
    finally:
        for t in tasks:
            t.cancel()
        for t in tasks:
            try:
                await t
            except asyncio.CancelledError:
                pass
        await runtime.shutdown()


app = FastAPI(title="discussions", lifespan=lifespan)

# Multi-tenant phase 3. CORS and origin enforcement are driven by the *live* tenant set:
# a request is allowed only if its Origin is a registered tenant's origin (resolved per
# request, so a newly-onboarded blog works without an env change or restart).
_WILDCARD = ALLOWED_ORIGINS == ["*"]  # open demo/dev mode (ALLOWED_ORIGINS=*)


class _AllowedOrigins:
    """A live membership test for CORSMiddleware: an origin is allowed iff it's a
    registered tenant's origin (read from the tenant cache) or a local dev origin.
    Starlette tests `origin in allow_origins` per request, so passing this object makes
    CORS reflect exactly the current tenant set without rebuilding the middleware. `"*"`
    is never a member, so credentials stay enabled and the origin is echoed explicitly."""

    def __contains__(self, origin: str) -> bool:
        return origin != "*" and (origin in DEV_ORIGINS or origin in runtime.tenants().origins())


def _origin_registered(origin: str) -> bool:
    return origin in DEV_ORIGINS or runtime.tenants().id_for_origin(origin) is not None


if _WILDCARD:
    # Open demo: allow any origin, but then credentials must be off (browsers reject
    # "*" + credentials) and origin enforcement is disabled.
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False,
                       allow_methods=["*"], allow_headers=["*"])
else:
    app.add_middleware(CORSMiddleware, allow_origins=_AllowedOrigins(), allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"])

app.include_router(auth.router)
app.include_router(comments.router)
app.include_router(reactions.router)


@app.middleware("http")
async def enforce_origin(request: Request, call_next):
    # Origin enforcement (multi-tenant phase 3, the security crux): a cross-origin API
    # request whose Origin is not a registered tenant is rejected server-side, so a
    # random website can't post into (or read) another blog's threads. Browsers always
    # send Origin on cross-origin requests and can't forge it. We only act when an Origin
    # is present (same-origin /demo and non-browser callers send none -> default tenant)
    # and skip the open demo mode, OPTIONS preflight (CORS handles it), and /api/health.
    if not _WILDCARD and request.method != "OPTIONS":
        origin = request.headers.get("origin")
        path = request.url.path
        if origin and path.startswith("/api/") and path != "/api/health" \
                and not _origin_registered(origin):
            return JSONResponse({"detail": "origin not registered"}, status_code=403)
    return await call_next(request)


@app.middleware("http")
async def limit_request_size(request: Request, call_next):
    # Reject an oversized body by its declared Content-Length before it's read into
    # memory. (Chunked uploads without a length still hit the per-field MAX_BODY check
    # after parsing; browsers send Content-Length for JSON, which is our only client.)
    cl = request.headers.get("content-length")
    if cl and cl.isdigit() and int(cl) > REQUEST_MAX_BYTES:
        return JSONResponse({"detail": "request too large"}, status_code=413)
    return await call_next(request)


@app.get("/api/health")
async def health() -> dict:
    return {"ok": True, "repo": REPO}


# Serve the widget (same-origin demo: cookies + the OAuth popup work without CORS).
if os.path.isdir(WIDGET_DIR):
    app.mount("/demo", StaticFiles(directory=WIDGET_DIR, html=True), name="demo")
