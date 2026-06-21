"""Runtime wiring: builds and holds the active Database, Store, SessionStore and
TenantRegistry for the process, and runs their startup/shutdown.

This is the one place that decides *what* gets built, from the config knobs. A Database
is constructed only when something needs persistence — the self-hosted store, db-backed
sessions, or db-backed tenants. The github form needs none of those, so its deployment
never builds a DB driver and never imports aiosqlite / cmark-gfm (the lean form).

Routes and middleware reach the pieces through the accessors here (store(),
session_store(), tenants(), database()); nothing else constructs them.
"""
from typing import Optional

from . import gh
from .config import SESSION_STORE, STORE, TENANTS
from .db.base import Database
from .sessions import SessionStore, build_session_store
from .store import build_store
from .store.base import Store
from .tenants import TenantRegistry, build_tenants

_db: Optional[Database] = None
_store: Optional[Store] = None
_sessions: Optional[SessionStore] = None
_tenants: Optional[TenantRegistry] = None


def _needs_db() -> bool:
    """A Database is built only if something persists through it. The github form (store
    github, lru sessions, config tenants) needs none, so it never imports a DB driver."""
    return STORE == "selfhosted" or SESSION_STORE == "db" or TENANTS == "db"


async def startup() -> None:
    """Build every piece from config and bring it up. Called by the app lifespan."""
    global _db, _store, _sessions, _tenants
    await gh.init()  # shared httpx client (OAuth identity; github store transport)
    if _needs_db():
        from .db import build_database
        _db = build_database()
        await _db.init()  # connection + schema/migration
    _tenants = build_tenants(_db)
    _sessions = build_session_store(_db)
    _store = build_store(_db, _tenants)
    await _tenants.load()      # populate the tenant cache (env or DB)
    await _store.init()        # store-specific warmup
    await _sessions.sweep()    # drop sessions that expired while we were down


async def shutdown() -> None:
    """Tear everything down in reverse. Called by the app lifespan."""
    if _store is not None:
        await _store.close()
    await gh.close()
    if _db is not None:
        await _db.close()


def database() -> Optional[Database]:
    return _db


def store() -> Store:
    assert _store is not None, "runtime.startup() has not run"
    return _store


def session_store() -> SessionStore:
    assert _sessions is not None, "runtime.startup() has not run"
    return _sessions


def tenants() -> TenantRegistry:
    assert _tenants is not None, "runtime.startup() has not run"
    return _tenants
