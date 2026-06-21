"""SqliteDatabase — the SQLite driver for the self-hosted store.

Implements the `Database` interface (db/base.py) with aiosqlite, which runs SQLite on
its own thread so DB calls never block the event loop. The connection is opened/closed
by the app lifespan. State lives in a small file so it survives a restart.

This module is imported only when DATABASE=sqlite (see db/__init__.py), so the github
form never pulls in aiosqlite. A MySQL/Postgres driver would be a sibling file
implementing the same interface; nothing above the Database line changes.
"""
import time
from typing import Optional

import aiosqlite

from ..config import DB_PATH, DEFAULT_TENANT_ID
from .base import Database

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
    # Local reaction store: one row per (comment, user, emoji). The self-hosted store
    # keeps reactions here, keyed by the verified login, rather than on GitHub.
    "CREATE TABLE IF NOT EXISTS reactions("
    "comment_id TEXT NOT NULL, login TEXT NOT NULL, content TEXT NOT NULL, "
    "created_at REAL NOT NULL, tenant_id TEXT NOT NULL DEFAULT '', "
    "PRIMARY KEY (comment_id, login, content))",
    "CREATE INDEX IF NOT EXISTS idx_reactions_comment ON reactions(comment_id)",
    # Tenants: one row per hosted blog. Phase 1 runs a single default tenant (seeded at
    # startup from env); the schema is ready for more. `origin` is the blog's site URL
    # (the per-request CORS/identity key); `repo`/`repo_url` are that blog's repo.
    # strip_suffix/giphy_key are that blog's widget config, served by GET /api/config.
    "CREATE TABLE IF NOT EXISTS tenants("
    "id TEXT PRIMARY KEY, origin TEXT, repo TEXT, repo_url TEXT, created_at REAL NOT NULL, "
    "strip_suffix TEXT NOT NULL DEFAULT '', giphy_key TEXT NOT NULL DEFAULT '')",
    # Per-tenant moderators (the blog owner + delegates). Seeded from ADMIN_LOGINS.
    "CREATE TABLE IF NOT EXISTS tenant_admins("
    "tenant_id TEXT NOT NULL, login TEXT NOT NULL, PRIMARY KEY (tenant_id, login))",
    _DISCUSSIONS_DDL,
    # Comments (the items). Replies point at a top-level comment via parent_id (NULL =
    # top-level). A comment belongs to its discussion by (tenant_id, term). body_html is
    # the cmark-gfm-rendered Markdown, cached so we don't re-render on every read.
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


class SqliteDatabase(Database):
    name = "sqlite"

    def __init__(self) -> None:
        self._conn: Optional[aiosqlite.Connection] = None

    async def _table_columns(self, table: str) -> set:
        cur = await self._conn.execute(f"PRAGMA table_info({table})")
        return {row[1] for row in await cur.fetchall()}

    async def init(self) -> None:
        self._conn = await aiosqlite.connect(DB_PATH)
        await self._conn.execute("PRAGMA journal_mode=WAL")
        for stmt in _SCHEMA:
            await self._conn.execute(stmt)
        # Idempotent migrations: older tables predate some columns.
        for mig in ("ALTER TABLE sessions ADD COLUMN url TEXT",
                    "ALTER TABLE comments ADD COLUMN hidden_at REAL",
                    "ALTER TABLE comments ADD COLUMN tenant_id TEXT NOT NULL DEFAULT ''",
                    "ALTER TABLE reactions ADD COLUMN tenant_id TEXT NOT NULL DEFAULT ''",
                    "ALTER TABLE tenants ADD COLUMN strip_suffix TEXT NOT NULL DEFAULT ''",
                    "ALTER TABLE tenants ADD COLUMN giphy_key TEXT NOT NULL DEFAULT ''"):
            try:
                await self._conn.execute(mig)
            except Exception:
                pass  # column already exists
        # discussions: rebuild the pre-tenant table (PK was `term`) into the composite
        # (tenant_id, term) PK. Detected by the absence of a tenant_id column.
        dcols = await self._table_columns("discussions")
        if dcols and "tenant_id" not in dcols:
            await self._conn.execute("ALTER TABLE discussions RENAME TO _discussions_old")
            await self._conn.execute(_DISCUSSIONS_DDL)
            await self._conn.execute(
                "INSERT INTO discussions(tenant_id, term, title, subtitle, url, created_at) "
                "SELECT ?, term, title, subtitle, url, created_at FROM _discussions_old",
                (DEFAULT_TENANT_ID,),
            )
            await self._conn.execute("DROP TABLE _discussions_old")
        # Backfill comments/reactions that predate tenant_id to the default tenant.
        await self._conn.execute(
            "UPDATE comments SET tenant_id=? WHERE tenant_id IS NULL OR tenant_id=''",
            (DEFAULT_TENANT_ID,))
        await self._conn.execute(
            "UPDATE reactions SET tenant_id=? WHERE tenant_id IS NULL OR tenant_id=''",
            (DEFAULT_TENANT_ID,))
        for stmt in _TENANT_INDEXES:
            await self._conn.execute(stmt)
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()

    # --- sessions ------------------------------------------------------------
    async def session_put(self, sid, data, ttl) -> None:
        await self._conn.execute(
            "INSERT OR REPLACE INTO sessions(sid, token, login, avatar_url, name, url, expires_at) "
            "VALUES(?,?,?,?,?,?,?)",
            (sid, data["token"], data["login"], data["avatarUrl"], data["name"],
             data.get("url"), time.time() + ttl),
        )
        await self._conn.commit()

    async def session_get(self, sid):
        cur = await self._conn.execute(
            "SELECT token, login, avatar_url, name, expires_at, url FROM sessions WHERE sid=?", (sid,))
        row = await cur.fetchone()
        if not row:
            return None
        if row[4] <= time.time():
            await self.session_del(sid)  # lazily drop an expired session on access
            return None
        return {"token": row[0], "login": row[1], "avatarUrl": row[2], "name": row[3], "url": row[5]}

    async def session_del(self, sid) -> None:
        await self._conn.execute("DELETE FROM sessions WHERE sid=?", (sid,))
        await self._conn.commit()

    async def session_sweep(self) -> int:
        cur = await self._conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (time.time(),))
        await self._conn.commit()
        return cur.rowcount

    # --- tenants -------------------------------------------------------------
    async def tenant_seed_default(self, tenant_id, origin, repo, repo_url, admins) -> None:
        await self._conn.execute(
            "INSERT OR IGNORE INTO tenants(id, origin, repo, repo_url, created_at) "
            "VALUES(?,?,?,?,?)", (tenant_id, origin, repo, repo_url, time.time()))
        for login in admins:
            await self._conn.execute(
                "INSERT OR IGNORE INTO tenant_admins(tenant_id, login) VALUES(?,?)",
                (tenant_id, login))
        await self._conn.commit()

    async def tenant_load_all(self):
        cur = await self._conn.execute(
            "SELECT id, origin, repo, repo_url, strip_suffix, giphy_key FROM tenants")
        tenants = [{"id": r[0], "origin": r[1], "repo": r[2], "repo_url": r[3],
                    "strip_suffix": r[4], "giphy_key": r[5]} for r in await cur.fetchall()]
        admins: dict = {}
        cur = await self._conn.execute("SELECT tenant_id, login FROM tenant_admins")
        for tid, login in await cur.fetchall():
            admins.setdefault(tid, set()).add(login)
        return tenants, admins

    async def tenant_get(self, tenant_id):
        cur = await self._conn.execute(
            "SELECT id, origin, repo, repo_url, created_at, strip_suffix, giphy_key "
            "FROM tenants WHERE id=?", (tenant_id,))
        row = await cur.fetchone()
        if not row:
            return None
        return {"id": row[0], "origin": row[1], "repo": row[2], "repo_url": row[3],
                "created_at": row[4], "strip_suffix": row[5], "giphy_key": row[6]}

    async def tenant_admins(self, tenant_id):
        cur = await self._conn.execute(
            "SELECT login FROM tenant_admins WHERE tenant_id=?", (tenant_id,))
        return [r[0] for r in await cur.fetchall()]

    async def tenant_create(self, tenant_id, origin, repo="", repo_url="",
                            admins=None, strip_suffix="", giphy_key="") -> None:
        await self._conn.execute(
            "INSERT INTO tenants(id, origin, repo, repo_url, created_at, strip_suffix, giphy_key) "
            "VALUES(?,?,?,?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET origin=excluded.origin, repo=excluded.repo, "
            "repo_url=excluded.repo_url, strip_suffix=excluded.strip_suffix, "
            "giphy_key=excluded.giphy_key",
            (tenant_id, origin, repo, repo_url, time.time(), strip_suffix, giphy_key))
        for login in (admins or []):
            await self._conn.execute(
                "INSERT OR IGNORE INTO tenant_admins(tenant_id, login) VALUES(?,?)",
                (tenant_id, login))
        await self._conn.commit()

    async def tenant_delete(self, tenant_id, purge=False) -> None:
        await self._conn.execute("DELETE FROM tenant_admins WHERE tenant_id=?", (tenant_id,))
        await self._conn.execute("DELETE FROM tenants WHERE id=?", (tenant_id,))
        if purge:
            await self._conn.execute("DELETE FROM reactions WHERE tenant_id=?", (tenant_id,))
            await self._conn.execute("DELETE FROM comments WHERE tenant_id=?", (tenant_id,))
            await self._conn.execute("DELETE FROM discussions WHERE tenant_id=?", (tenant_id,))
        await self._conn.commit()

    async def tenant_admin_add(self, tenant_id, login) -> None:
        await self._conn.execute(
            "INSERT OR IGNORE INTO tenant_admins(tenant_id, login) VALUES(?,?)", (tenant_id, login))
        await self._conn.commit()

    async def tenant_admin_remove(self, tenant_id, login) -> None:
        await self._conn.execute(
            "DELETE FROM tenant_admins WHERE tenant_id=? AND login=?", (tenant_id, login))
        await self._conn.commit()

    async def tenant_list(self):
        cur = await self._conn.execute(
            "SELECT id, origin, repo, repo_url, created_at, strip_suffix, giphy_key "
            "FROM tenants ORDER BY created_at")
        tenants = [{"id": r[0], "origin": r[1], "repo": r[2], "repo_url": r[3], "created_at": r[4],
                    "strip_suffix": r[5], "giphy_key": r[6]} for r in await cur.fetchall()]
        cur = await self._conn.execute("SELECT tenant_id, login FROM tenant_admins")
        by_t: dict = {}
        for tid, login in await cur.fetchall():
            by_t.setdefault(tid, []).append(login)
        for t in tenants:
            t["admins"] = sorted(by_t.get(t["id"], []))
        return tenants

    # --- discussions ---------------------------------------------------------
    async def discussion_get(self, tenant_id, term):
        cur = await self._conn.execute(
            "SELECT term, title, subtitle, url, created_at FROM discussions "
            "WHERE tenant_id=? AND term=?", (tenant_id, term))
        row = await cur.fetchone()
        if not row:
            return None
        return {"term": row[0], "title": row[1], "subtitle": row[2], "url": row[3], "createdAt": row[4]}

    async def discussion_upsert(self, tenant_id, term, title, subtitle, url) -> None:
        await self._conn.execute(
            "INSERT OR IGNORE INTO discussions(tenant_id, term, title, subtitle, url, created_at) "
            "VALUES(?,?,?,?,?,?)",
            (tenant_id, term, title, subtitle, url, time.time()))
        await self._conn.commit()

    # --- comments ------------------------------------------------------------
    async def comment_insert(self, c) -> None:
        await self._conn.execute(
            f"INSERT INTO comments({_COMMENT_COLS}) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (c["id"], c["term"], c.get("parent_id"), c["author_login"], c.get("author_name"),
             c.get("author_avatar"), c.get("author_url"), c["body_md"], c["body_html"],
             c["created_at"], c.get("updated_at"), 1 if c.get("is_minimized") else 0,
             c.get("min_reason"), c.get("hidden_at"), c.get("tenant_id", DEFAULT_TENANT_ID)))
        await self._conn.commit()

    async def comment_get(self, comment_id):
        cur = await self._conn.execute(
            f"SELECT {_COMMENT_COLS} FROM comments WHERE id=?", (comment_id,))
        row = await cur.fetchone()
        return _comment_row(row) if row else None

    async def comment_update_body(self, comment_id, body_md, body_html, updated_at) -> None:
        await self._conn.execute(
            "UPDATE comments SET body_md=?, body_html=?, updated_at=? WHERE id=?",
            (body_md, body_html, updated_at, comment_id))
        await self._conn.commit()

    async def comment_set_hidden(self, comment_id, hide, reason, hidden_at) -> None:
        await self._conn.execute(
            "UPDATE comments SET is_minimized=?, min_reason=?, hidden_at=? WHERE id=?",
            (1 if hide else 0, reason if hide else None, hidden_at if hide else None, comment_id))
        await self._conn.commit()

    async def comment_delete(self, comment_id):
        cur = await self._conn.execute("SELECT id FROM comments WHERE parent_id=?", (comment_id,))
        ids = [comment_id] + [r[0] for r in await cur.fetchall()]
        qs = ",".join("?" * len(ids))
        await self._conn.execute(f"DELETE FROM comments WHERE id IN ({qs})", ids)
        await self._conn.commit()
        return ids

    async def comments_top(self, tenant_id, term, limit, offset):
        cur = await self._conn.execute(
            f"SELECT {_COMMENT_COLS} FROM comments "
            f"WHERE tenant_id=? AND term=? AND parent_id IS NULL "
            f"ORDER BY created_at ASC, id ASC LIMIT ? OFFSET ?", (tenant_id, term, limit, offset))
        return [_comment_row(r) for r in await cur.fetchall()]

    async def comments_top_count(self, tenant_id, term):
        cur = await self._conn.execute(
            "SELECT COUNT(*) FROM comments WHERE tenant_id=? AND term=? AND parent_id IS NULL",
            (tenant_id, term))
        return (await cur.fetchone())[0]

    async def comments_replies(self, parent_ids):
        ids = [p for p in parent_ids if p]
        if not ids:
            return {}
        qs = ",".join("?" * len(ids))
        cur = await self._conn.execute(
            f"SELECT {_COMMENT_COLS} FROM comments WHERE parent_id IN ({qs}) "
            f"ORDER BY created_at ASC, id ASC", ids)
        out: dict = {}
        for r in await cur.fetchall():
            row = _comment_row(r)
            out.setdefault(row["parent_id"], []).append(row)
        return out

    # --- reactions -----------------------------------------------------------
    async def reactions_for(self, comment_ids, viewer):
        ids = list({c for c in comment_ids if c})
        if not ids:
            return {}
        qs = ",".join("?" * len(ids))
        cur = await self._conn.execute(
            f"SELECT comment_id, content, COUNT(*), "
            f"SUM(CASE WHEN login=? THEN 1 ELSE 0 END) "
            f"FROM reactions WHERE comment_id IN ({qs}) GROUP BY comment_id, content",
            [viewer or ""] + ids)
        out: dict = {}
        for cid, content, count, mine in await cur.fetchall():
            out.setdefault(cid, []).append(
                {"content": content, "count": count, "viewerHasReacted": bool(mine)})
        return out

    async def react_toggle(self, comment_id, login, content, on, tenant_id) -> None:
        if on:
            await self._conn.execute(
                "INSERT OR IGNORE INTO reactions(comment_id, login, content, created_at, tenant_id) "
                "VALUES(?,?,?,?,?)", (comment_id, login, content, time.time(), tenant_id))
        else:
            await self._conn.execute(
                "DELETE FROM reactions WHERE comment_id=? AND login=? AND content=?",
                (comment_id, login, content))
        await self._conn.commit()

    async def reactions_purge(self, comment_id) -> None:
        await self._conn.execute("DELETE FROM reactions WHERE comment_id=?", (comment_id,))
        await self._conn.commit()
