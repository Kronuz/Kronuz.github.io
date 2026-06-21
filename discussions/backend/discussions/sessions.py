"""Session store — where an OAuth session ({token, identity}) lives between requests,
behind a small interface so each form picks the lightest fit.

create() mints the opaque cookie value; get() resolves it back to the session dict.

- LruSessionStore: in-memory, bounded LRU + TTL (stdlib). The default for the github
  form -> no database, the token stays in server RAM. Lost on restart (re-auth), and
  tied to a single instance (not for multi-instance/edge).
- DbSessionStore: backed by the active Database (any driver). The default for the
  self-hosted form, which already runs a database; survives restarts.
- CookieSessionStore: stateless -- the session rides in a signed cookie, no server
  state, so it works on edge/scale-to-zero. Sign-only (HMAC), so the token sits base64
  in the reader's own httponly+secure cookie; encrypt it before using this in anger.
"""
import base64
import hashlib
import hmac
import json
import secrets
import time
from collections import OrderedDict
from typing import Optional

from .config import SESSION_SECRET, SESSION_TTL


class SessionStore:
    """create -> cookie value; get -> session dict; destroy/sweep manage lifetime."""

    name = "base"

    async def create(self, data: dict) -> str:
        raise NotImplementedError

    async def get(self, value: str) -> Optional[dict]:
        raise NotImplementedError

    async def destroy(self, value: str) -> None:
        raise NotImplementedError

    async def sweep(self) -> int:
        return 0


class LruSessionStore(SessionStore):
    """In-memory sessions: an OrderedDict (LRU) of sid -> (data, expires_at), bounded by
    max_size and SESSION_TTL. The event loop is single-threaded, so no locking is needed."""

    name = "lru"

    def __init__(self, max_size: int = 10000, ttl: int = SESSION_TTL) -> None:
        self._d: "OrderedDict[str, tuple]" = OrderedDict()
        self._max = max_size
        self._ttl = ttl

    async def create(self, data: dict) -> str:
        sid = secrets.token_urlsafe(24)
        self._d[sid] = (data, time.time() + self._ttl)
        self._d.move_to_end(sid)
        while len(self._d) > self._max:
            self._d.popitem(last=False)  # evict the least-recently-used
        return sid

    async def get(self, value: str) -> Optional[dict]:
        item = self._d.get(value)
        if not item:
            return None
        data, expires = item
        if expires <= time.time():
            self._d.pop(value, None)
            return None
        self._d.move_to_end(value)  # LRU touch
        return data

    async def destroy(self, value: str) -> None:
        self._d.pop(value, None)

    async def sweep(self) -> int:
        now = time.time()
        dead = [sid for sid, (_, exp) in self._d.items() if exp <= now]
        for sid in dead:
            self._d.pop(sid, None)
        return len(dead)


class DbSessionStore(SessionStore):
    """Sessions persisted by the active Database driver (works with any driver)."""

    name = "db"

    def __init__(self, db) -> None:
        self.db = db

    async def create(self, data: dict) -> str:
        sid = secrets.token_urlsafe(24)
        await self.db.session_put(sid, data, SESSION_TTL)
        return sid

    async def get(self, value: str) -> Optional[dict]:
        return await self.db.session_get(value)

    async def destroy(self, value: str) -> None:
        await self.db.session_del(value)

    async def sweep(self) -> int:
        return await self.db.session_sweep()


class CookieSessionStore(SessionStore):
    """Stateless sessions: the cookie value IS the (HMAC-signed) session, so there is no
    server state -- good for edge/scale-to-zero. Sign-only: the token is base64 in the
    payload, protected by httponly+secure but readable if the cookie is exfiltrated.
    Swap the signing for encryption (e.g. cryptography.Fernet) to keep the token opaque."""

    name = "cookie"

    def __init__(self, secret: str = SESSION_SECRET, ttl: int = SESSION_TTL) -> None:
        self._secret = secret.encode()
        self._ttl = ttl

    def _sign(self, payload: bytes) -> str:
        mac = hmac.new(self._secret, payload, hashlib.sha256).hexdigest()
        return base64.urlsafe_b64encode(payload).decode() + "." + mac

    async def create(self, data: dict) -> str:
        body = {"d": data, "exp": time.time() + self._ttl}
        return self._sign(json.dumps(body, separators=(",", ":")).encode())

    async def get(self, value: str) -> Optional[dict]:
        try:
            b64, mac = value.rsplit(".", 1)
            payload = base64.urlsafe_b64decode(b64.encode())
        except Exception:
            return None
        good = hmac.new(self._secret, payload, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(mac, good):
            return None
        try:
            body = json.loads(payload)
        except Exception:
            return None
        if float(body.get("exp", 0)) <= time.time():
            return None
        return body.get("d")

    async def destroy(self, value: str) -> None:
        return None  # stateless: the client drops the cookie

    async def sweep(self) -> int:
        return 0


def build_session_store(db=None) -> SessionStore:
    """The active session store, selected by config.SESSION_STORE. `db` is required for
    the 'db' store (the same Database the self-hosted store uses)."""
    from .config import SESSION_STORE
    if SESSION_STORE == "lru":
        return LruSessionStore()
    if SESSION_STORE == "cookie":
        return CookieSessionStore()
    if SESSION_STORE == "db":
        if db is None:
            raise RuntimeError("SESSION_STORE=db needs a Database (DATABASE must be set)")
        return DbSessionStore(db)
    raise RuntimeError(f"unknown SESSION_STORE={SESSION_STORE!r}; expected lru|db|cookie")
