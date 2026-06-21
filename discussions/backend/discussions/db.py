"""SQLite-backed session + reaction store.

Uses aiosqlite, which runs SQLite on its own thread so DB calls never block the
event loop. The connection is opened/closed by the app lifespan (see app.py).
State lives in a small file so it survives a restart (an in-memory dict logged
everyone out on every deploy).
"""
import time
from typing import Optional

import aiosqlite

from .config import DB_PATH, SESSION_TTL, DEFAULT_TENANT_ID

# GitHub's eight reaction emoji (the ReactionContent enum); we whitelist these.
REACTION_CONTENT = {
    "THUMBS_UP", "THUMBS_DOWN", "LAUGH", "HOORAY", "CONFUSED", "HEART", "ROCKET", "EYES",
}

# discussions table DDL, reused by the schema and by the migration that rebuilds the
# old single-`term`-PK table into the composite (tenant_id, term) PK.
_DISCUSSIONS_DDL = (
    "CREATE TABLE IF NOT EXISTS discussions("
    "tenant_id TEXT NOT NULL, term TEXT NOT NULL, title TEXT, subtitle TEXT, url TEXT, "
    "created_at REAL NOT NULL, PRIMARY KEY (tenant_id, term))"
)

_SCHEMA = (
    # Sessions: sid -> {token, login, avatarUrl, name} + expires_at. Expired rows are
    # swept lazily on read, once at startup, and hourly by a background task.
    "CREATE TABLE IF NOT EXISTS sessions("
    "sid TEXT PRIMARY KEY, token TEXT NOT NULL, login TEXT NOT NULL, "
    "avatar_url TEXT, name TEXT, expires_at REAL NOT NULL)",
    "CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at)",
    # Local reaction store: one row per (comment, user, emoji). GitHub's own reactions
    # need the reader's token to reach the (private) repo, which the org's OAuth App
    # restrictions block — so reactions live here, keyed by the verified login.
    "CREATE TABLE IF NOT EXISTS reactions("
    "comment_id TEXT NOT NULL, login TEXT NOT NULL, content TEXT NOT NULL, "
    "created_at REAL NOT NULL, tenant_id TEXT NOT NULL DEFAULT '', "
    "PRIMARY KEY (comment_id, login, content))",
    "CREATE INDEX IF NOT EXISTS idx_reactions_comment ON reactions(comment_id)",
    # Tenants: one row per hosted blog. Phase 1 runs a single default tenant (seeded at
    # startup from env); the schema is ready for more. `origin` is the blog's site URL
    # (the future per-request CORS/identity key); `repo`/`repo_url` are that blog's repo.
    # strip_suffix/giphy_key are that blog's widget config, served by GET /api/config so a
    # tenant configures once on the server instead of baking it into its static build.
    "CREATE TABLE IF NOT EXISTS tenants("
    "id TEXT PRIMARY KEY, origin TEXT, repo TEXT, repo_url TEXT, created_at REAL NOT NULL, "
    "strip_suffix TEXT NOT NULL DEFAULT '', giphy_key TEXT NOT NULL DEFAULT '')",
    # Per-tenant moderators (the blog owner + delegates). Replaces a single global admin
    # list; is_admin becomes per-tenant in a later phase. Seeded from ADMIN_LOGINS.
    "CREATE TABLE IF NOT EXISTS tenant_admins("
    "tenant_id TEXT NOT NULL, login TEXT NOT NULL, PRIMARY KEY (tenant_id, login))",
    # One discussion per (tenant, page): the per-page container, keyed by `term` (the
    # post slug) WITHIN a tenant, so two blogs can share a slug without colliding. Holds
    # the page metadata the widget sends on first comment; comments below belong to it
    # by (tenant_id, term).
    _DISCUSSIONS_DDL,
    # Comments (the items). One row per comment; replies point at a top-level comment via
    # parent_id (NULL = top-level), and a comment + its replies form a thread. A comment
    # belongs to its discussion by (tenant_id, term). body_html is the cmark-gfm-rendered
    # Markdown, cached so we don't re-render on every read. Reactions live in `reactions`.
    "CREATE TABLE IF NOT EXISTS comments("
    "id TEXT PRIMARY KEY, term TEXT NOT NULL, parent_id TEXT, "
    "author_login TEXT NOT NULL, author_name TEXT, author_avatar TEXT, author_url TEXT, "
    "body_md TEXT NOT NULL, body_html TEXT NOT NULL, "
    "created_at REAL NOT NULL, updated_at REAL, "
    "is_minimized INTEGER NOT NULL DEFAULT 0, min_reason TEXT, hidden_at REAL, "
    "tenant_id TEXT NOT NULL DEFAULT '')",
    "CREATE INDEX IF NOT EXISTS idx_comments_term ON comments(term, parent_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_comments_parent ON comments(parent_id)",
)

# Indexes that reference tenant_id, created only after the migration has added that
# column (an existing pre-tenant `comments` table lacks it during the _SCHEMA pass).
_TENANT_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_comments_tenant_term "
    "ON comments(tenant_id, term, parent_id, created_at)",
)

_conn: Optional[aiosqlite.Connection] = None

# In-process tenant cache, so per-request tenant resolution and the CORS allowlist don't
# hit SQLite on every call (multi-tenant phase 2). Loaded at startup and refreshed on any
# tenant write (tenant_seed_default, and the phase-3 admin CLI). See ROADMAP.md.
_origin_to_tenant: dict = {}   # origin -> tenant id
_admins_by_tenant: dict = {}   # tenant id -> {login, ...}
_tenant_origins: set = set()   # all registered origins


async def _table_columns(table: str) -> set:
    cur = await _conn.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in await cur.fetchall()}


async def init() -> None:
    global _conn
    _conn = await aiosqlite.connect(DB_PATH)
    await _conn.execute("PRAGMA journal_mode=WAL")
    for stmt in _SCHEMA:
        await _conn.execute(stmt)
    # Idempotent migrations: older tables predate some columns.
    # - sessions.url: the signed-in user's GitHub profile URL (the comment author link).
    # - comments.hidden_at: when a comment was hidden (shown on the collapse bar).
    # - comments/reactions.tenant_id: the tenant a row belongs to (multi-tenant phase 1).
    for mig in ("ALTER TABLE sessions ADD COLUMN url TEXT",
                "ALTER TABLE comments ADD COLUMN hidden_at REAL",
                "ALTER TABLE comments ADD COLUMN tenant_id TEXT NOT NULL DEFAULT ''",
                "ALTER TABLE reactions ADD COLUMN tenant_id TEXT NOT NULL DEFAULT ''",
                "ALTER TABLE tenants ADD COLUMN strip_suffix TEXT NOT NULL DEFAULT ''",
                "ALTER TABLE tenants ADD COLUMN giphy_key TEXT NOT NULL DEFAULT ''"):
        try:
            await _conn.execute(mig)
        except Exception:
            pass  # column already exists
    # discussions: rebuild the pre-tenant table (PK was `term`) into the composite
    # (tenant_id, term) PK, assigning existing rows to the default tenant. Detected by
    # the absence of a tenant_id column; a no-op on fresh DBs (created with the new shape)
    # and on already-migrated DBs.
    dcols = await _table_columns("discussions")
    if dcols and "tenant_id" not in dcols:
        await _conn.execute("ALTER TABLE discussions RENAME TO _discussions_old")
        await _conn.execute(_DISCUSSIONS_DDL)
        await _conn.execute(
            "INSERT INTO discussions(tenant_id, term, title, subtitle, url, created_at) "
            "SELECT ?, term, title, subtitle, url, created_at FROM _discussions_old",
            (DEFAULT_TENANT_ID,),
        )
        await _conn.execute("DROP TABLE _discussions_old")
    # Backfill any comments/reactions that predate tenant_id (NULL or empty) to the
    # default tenant, so the tenant-scoped read paths still find them.
    await _conn.execute(
        "UPDATE comments SET tenant_id=? WHERE tenant_id IS NULL OR tenant_id=''",
        (DEFAULT_TENANT_ID,))
    await _conn.execute(
        "UPDATE reactions SET tenant_id=? WHERE tenant_id IS NULL OR tenant_id=''",
        (DEFAULT_TENANT_ID,))
    # Now that tenant_id exists on comments, create the indexes that reference it.
    for stmt in _TENANT_INDEXES:
        await _conn.execute(stmt)
    await _conn.commit()


# --- tenants -----------------------------------------------------------------
async def tenant_seed_default(tenant_id: str, origin: str, repo: str, repo_url: str,
                              admins: list) -> None:
    """Create (or leave) the default tenant and its moderators from this instance's env.
    Idempotent: INSERT OR IGNORE never clobbers an edited tenant row."""
    await _conn.execute(
        "INSERT OR IGNORE INTO tenants(id, origin, repo, repo_url, created_at) "
        "VALUES(?,?,?,?,?)", (tenant_id, origin, repo, repo_url, time.time()))
    for login in admins:
        await _conn.execute(
            "INSERT OR IGNORE INTO tenant_admins(tenant_id, login) VALUES(?,?)",
            (tenant_id, login))
    await _conn.commit()
    await tenant_cache_load()  # reflect the seed in the per-request cache


async def tenant_cache_load() -> None:
    """(Re)load the in-process tenant cache from the tenants/tenant_admins tables. Cheap
    (two small table scans); call after any tenant write so reads stay current."""
    global _origin_to_tenant, _admins_by_tenant, _tenant_origins
    o2t: dict = {}
    origins: set = set()
    cur = await _conn.execute("SELECT id, origin FROM tenants")
    for tid, origin in await cur.fetchall():
        if origin:
            o2t[origin] = tid
            origins.add(origin)
    admins: dict = {}
    cur = await _conn.execute("SELECT tenant_id, login FROM tenant_admins")
    for tid, login in await cur.fetchall():
        admins.setdefault(tid, set()).add(login)
    _origin_to_tenant, _admins_by_tenant, _tenant_origins = o2t, admins, origins


def tenant_id_for_origin(origin: Optional[str]) -> Optional[str]:
    """The tenant whose registered origin matches `origin`, or None. In-memory cache read."""
    return _origin_to_tenant.get(origin or "")


def tenant_is_admin(tenant_id: str, login: Optional[str]) -> bool:
    """Whether `login` moderates `tenant_id` (its blog owner/delegates). Cache read.
    Per-tenant: a moderator of one blog is not a moderator of another."""
    return bool(login) and login in _admins_by_tenant.get(tenant_id, ())


def tenant_origins() -> set:
    """All registered tenant origins (the CORS/identity allowlist). Cache read (a copy)."""
    return set(_tenant_origins)


async def tenant_get(tenant_id: str) -> Optional[dict]:
    cur = await _conn.execute(
        "SELECT id, origin, repo, repo_url, created_at, strip_suffix, giphy_key "
        "FROM tenants WHERE id=?", (tenant_id,))
    row = await cur.fetchone()
    if not row:
        return None
    return {"id": row[0], "origin": row[1], "repo": row[2], "repo_url": row[3],
            "created_at": row[4], "strip_suffix": row[5], "giphy_key": row[6]}


async def tenant_admins(tenant_id: str) -> list:
    cur = await _conn.execute(
        "SELECT login FROM tenant_admins WHERE tenant_id=?", (tenant_id,))
    return [r[0] for r in await cur.fetchall()]


# --- tenant administration (used by the admin CLI; each refreshes the cache) ----------
async def tenant_create(tenant_id: str, origin: str, repo: str = "", repo_url: str = "",
                        admins: Optional[list] = None, strip_suffix: str = "",
                        giphy_key: str = "") -> None:
    """Create or update a tenant and (additively) its moderators. Upsert on id, keeping
    the original created_at. strip_suffix/giphy_key are the blog's widget config served by
    GET /api/config. Refreshes the in-process cache so the running server picks the tenant
    up immediately."""
    await _conn.execute(
        "INSERT INTO tenants(id, origin, repo, repo_url, created_at, strip_suffix, giphy_key) "
        "VALUES(?,?,?,?,?,?,?) "
        "ON CONFLICT(id) DO UPDATE SET origin=excluded.origin, repo=excluded.repo, "
        "repo_url=excluded.repo_url, strip_suffix=excluded.strip_suffix, "
        "giphy_key=excluded.giphy_key",
        (tenant_id, origin, repo, repo_url, time.time(), strip_suffix, giphy_key))
    for login in (admins or []):
        await _conn.execute(
            "INSERT OR IGNORE INTO tenant_admins(tenant_id, login) VALUES(?,?)",
            (tenant_id, login))
    await _conn.commit()
    await tenant_cache_load()


async def tenant_delete(tenant_id: str, purge: bool = False) -> None:
    """Remove a tenant from the registry (its row + moderators). With purge=True also
    delete its discussions/comments/reactions; otherwise that data is left in place but
    orphaned (the tenant no longer resolves). Refreshes the cache."""
    await _conn.execute("DELETE FROM tenant_admins WHERE tenant_id=?", (tenant_id,))
    await _conn.execute("DELETE FROM tenants WHERE id=?", (tenant_id,))
    if purge:
        await _conn.execute("DELETE FROM reactions WHERE tenant_id=?", (tenant_id,))
        await _conn.execute("DELETE FROM comments WHERE tenant_id=?", (tenant_id,))
        await _conn.execute("DELETE FROM discussions WHERE tenant_id=?", (tenant_id,))
    await _conn.commit()
    await tenant_cache_load()


async def tenant_admin_add(tenant_id: str, login: str) -> None:
    await _conn.execute(
        "INSERT OR IGNORE INTO tenant_admins(tenant_id, login) VALUES(?,?)", (tenant_id, login))
    await _conn.commit()
    await tenant_cache_load()


async def tenant_admin_remove(tenant_id: str, login: str) -> None:
    await _conn.execute(
        "DELETE FROM tenant_admins WHERE tenant_id=? AND login=?", (tenant_id, login))
    await _conn.commit()
    await tenant_cache_load()


async def tenant_list() -> list:
    """Every tenant with its moderators, for the admin CLI's `tenant list`."""
    cur = await _conn.execute(
        "SELECT id, origin, repo, repo_url, created_at, strip_suffix, giphy_key "
        "FROM tenants ORDER BY created_at")
    tenants = [{"id": r[0], "origin": r[1], "repo": r[2], "repo_url": r[3], "created_at": r[4],
                "strip_suffix": r[5], "giphy_key": r[6]} for r in await cur.fetchall()]
    cur = await _conn.execute("SELECT tenant_id, login FROM tenant_admins")
    by_t: dict = {}
    for tid, login in await cur.fetchall():
        by_t.setdefault(tid, []).append(login)
    for t in tenants:
        t["admins"] = sorted(by_t.get(t["id"], []))
    return tenants


async def close() -> None:
    if _conn is not None:
        await _conn.close()


# --- sessions ----------------------------------------------------------------
async def session_put(sid: str, data: dict, ttl: int = SESSION_TTL) -> None:
    await _conn.execute(
        "INSERT OR REPLACE INTO sessions(sid, token, login, avatar_url, name, url, expires_at) "
        "VALUES(?,?,?,?,?,?,?)",
        (sid, data["token"], data["login"], data["avatarUrl"], data["name"],
         data.get("url"), time.time() + ttl),
    )
    await _conn.commit()


async def session_get(sid: str) -> Optional[dict]:
    cur = await _conn.execute(
        "SELECT token, login, avatar_url, name, expires_at, url FROM sessions WHERE sid=?", (sid,)
    )
    row = await cur.fetchone()
    if not row:
        return None
    if row[4] <= time.time():
        await session_del(sid)  # lazily drop an expired session on access
        return None
    return {"token": row[0], "login": row[1], "avatarUrl": row[2], "name": row[3], "url": row[5]}


async def session_del(sid: str) -> None:
    await _conn.execute("DELETE FROM sessions WHERE sid=?", (sid,))
    await _conn.commit()


async def session_sweep() -> int:
    cur = await _conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (time.time(),))
    await _conn.commit()
    return cur.rowcount


# --- reactions ---------------------------------------------------------------
async def reactions_for(comment_ids: list, viewer: Optional[str]) -> dict:
    """Map each comment id -> [{content, count, viewerHasReacted}] from the store."""
    ids = list({c for c in comment_ids if c})
    if not ids:
        return {}
    qs = ",".join("?" * len(ids))
    cur = await _conn.execute(
        f"SELECT comment_id, content, COUNT(*), "
        f"SUM(CASE WHEN login=? THEN 1 ELSE 0 END) "
        f"FROM reactions WHERE comment_id IN ({qs}) GROUP BY comment_id, content",
        [viewer or ""] + ids,
    )
    rows = await cur.fetchall()
    out: dict = {}
    for cid, content, count, mine in rows:
        out.setdefault(cid, []).append(
            {"content": content, "count": count, "viewerHasReacted": bool(mine)}
        )
    return out


async def react_toggle(comment_id: str, login: str, content: str, on: bool,
                       tenant_id: str = DEFAULT_TENANT_ID) -> None:
    if on:
        await _conn.execute(
            "INSERT OR IGNORE INTO reactions(comment_id, login, content, created_at, tenant_id) "
            "VALUES(?,?,?,?,?)",
            (comment_id, login, content, time.time(), tenant_id),
        )
    else:
        await _conn.execute(
            "DELETE FROM reactions WHERE comment_id=? AND login=? AND content=?",
            (comment_id, login, content),
        )
    await _conn.commit()


async def reactions_purge(comment_id: str) -> None:
    """Drop all reactions for a comment (called when the comment is deleted)."""
    await _conn.execute("DELETE FROM reactions WHERE comment_id=?", (comment_id,))
    await _conn.commit()


# --- discussions (the per-page container) ------------------------------------
async def discussion_get(tenant_id: str, term: str) -> Optional[dict]:
    """Return {term, title, subtitle, url, createdAt} for a page, or None if no
    discussion exists for it yet."""
    cur = await _conn.execute(
        "SELECT term, title, subtitle, url, created_at FROM discussions "
        "WHERE tenant_id=? AND term=?", (tenant_id, term)
    )
    row = await cur.fetchone()
    if not row:
        return None
    return {"term": row[0], "title": row[1], "subtitle": row[2], "url": row[3], "createdAt": row[4]}


async def discussion_upsert(tenant_id: str, term: str, title, subtitle, url) -> None:
    # INSERT OR IGNORE: the first comment creates the discussion and fixes its metadata;
    # later comments don't clobber the title/url.
    await _conn.execute(
        "INSERT OR IGNORE INTO discussions(tenant_id, term, title, subtitle, url, created_at) "
        "VALUES(?,?,?,?,?,?)",
        (tenant_id, term, title, subtitle, url, time.time()),
    )
    await _conn.commit()


# --- self-hosted comments (SQLite store) -------------------------------------
_COMMENT_COLS = ("id, term, parent_id, author_login, author_name, author_avatar, author_url, "
                 "body_md, body_html, created_at, updated_at, is_minimized, min_reason, "
                 "hidden_at, tenant_id")


def _comment_row(row) -> dict:
    return {
        "id": row[0], "term": row[1], "parent_id": row[2],
        "author_login": row[3], "author_name": row[4], "author_avatar": row[5],
        "author_url": row[6], "body_md": row[7], "body_html": row[8],
        "created_at": row[9], "updated_at": row[10],
        "is_minimized": bool(row[11]), "min_reason": row[12], "hidden_at": row[13],
        "tenant_id": row[14],
    }


async def comment_insert(c: dict) -> None:
    await _conn.execute(
        f"INSERT INTO comments({_COMMENT_COLS}) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (c["id"], c["term"], c.get("parent_id"), c["author_login"], c.get("author_name"),
         c.get("author_avatar"), c.get("author_url"), c["body_md"], c["body_html"],
         c["created_at"], c.get("updated_at"), 1 if c.get("is_minimized") else 0,
         c.get("min_reason"), c.get("hidden_at"), c.get("tenant_id", DEFAULT_TENANT_ID)),
    )
    await _conn.commit()


async def comment_get(comment_id: str) -> Optional[dict]:
    cur = await _conn.execute(
        f"SELECT {_COMMENT_COLS} FROM comments WHERE id=?", (comment_id,))
    row = await cur.fetchone()
    return _comment_row(row) if row else None


async def comment_update_body(comment_id: str, body_md: str, body_html: str, updated_at: float) -> None:
    await _conn.execute(
        "UPDATE comments SET body_md=?, body_html=?, updated_at=? WHERE id=?",
        (body_md, body_html, updated_at, comment_id))
    await _conn.commit()


async def comment_set_hidden(comment_id: str, hide: bool, reason: Optional[str],
                             hidden_at: Optional[float]) -> None:
    await _conn.execute(
        "UPDATE comments SET is_minimized=?, min_reason=?, hidden_at=? WHERE id=?",
        (1 if hide else 0, reason if hide else None, hidden_at if hide else None, comment_id))
    await _conn.commit()


async def comment_delete(comment_id: str) -> list:
    """Delete a comment and (if it's top-level) its replies. Returns all deleted ids
    so the caller can purge their reactions."""
    cur = await _conn.execute("SELECT id FROM comments WHERE parent_id=?", (comment_id,))
    ids = [comment_id] + [r[0] for r in await cur.fetchall()]
    qs = ",".join("?" * len(ids))
    await _conn.execute(f"DELETE FROM comments WHERE id IN ({qs})", ids)
    await _conn.commit()
    return ids


async def comments_top(tenant_id: str, term: str, limit: int, offset: int) -> list:
    cur = await _conn.execute(
        f"SELECT {_COMMENT_COLS} FROM comments "
        f"WHERE tenant_id=? AND term=? AND parent_id IS NULL "
        f"ORDER BY created_at ASC, id ASC LIMIT ? OFFSET ?", (tenant_id, term, limit, offset))
    return [_comment_row(r) for r in await cur.fetchall()]


async def comments_top_count(tenant_id: str, term: str) -> int:
    cur = await _conn.execute(
        "SELECT COUNT(*) FROM comments WHERE tenant_id=? AND term=? AND parent_id IS NULL",
        (tenant_id, term))
    return (await cur.fetchone())[0]


async def comments_replies(parent_ids: list) -> dict:
    """Map each parent id -> [reply rows] (oldest first)."""
    ids = [p for p in parent_ids if p]
    if not ids:
        return {}
    qs = ",".join("?" * len(ids))
    cur = await _conn.execute(
        f"SELECT {_COMMENT_COLS} FROM comments WHERE parent_id IN ({qs}) "
        f"ORDER BY created_at ASC, id ASC", ids)
    out: dict = {}
    for r in await cur.fetchall():
        row = _comment_row(r)
        out.setdefault(row["parent_id"], []).append(row)
    return out

