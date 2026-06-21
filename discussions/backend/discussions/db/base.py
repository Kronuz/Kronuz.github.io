"""The Database interface — the persistence layer behind the self-hosted store.

A *Database* is the storage driver for everything the self-hosted form keeps: the
comment system (comments, replies, reactions, discussions), OAuth sessions, and the
tenant registry. The `SelfHostedStore`, `DbSessionStore`, and `DbTenants` all talk to
this interface, so swapping the backing database (SQLite today, MySQL/Postgres later)
is one new driver implementing these methods -- nothing above the line changes.

The github form uses none of this (its comments live in GitHub Discussions, its
sessions in an in-memory LRU, its single tenant in config), so a `Database` is only
built when something actually needs one.

Comment rows are plain dicts (see SqliteDatabase._comment_row for the shape); higher
layers (SelfHostedStore) turn them into the API comment shape.
"""
from typing import Optional


class Database:
    """Persistence operations a self-hosted deployment needs. Every driver (SQLite,
    MySQL, ...) implements these; the SQL/dialect details stay inside the driver."""

    name = "base"

    # --- lifecycle -----------------------------------------------------------
    async def init(self) -> None:
        raise NotImplementedError

    async def close(self) -> None:
        raise NotImplementedError

    # --- sessions ------------------------------------------------------------
    async def session_put(self, sid: str, data: dict, ttl: int) -> None:
        raise NotImplementedError

    async def session_get(self, sid: str) -> Optional[dict]:
        raise NotImplementedError

    async def session_del(self, sid: str) -> None:
        raise NotImplementedError

    async def session_sweep(self) -> int:
        raise NotImplementedError

    # --- tenants (raw persistence; the cache + lookups live in tenants.py) ----
    async def tenant_seed_default(self, tenant_id: str, origin: str, repo: str,
                                  repo_url: str, admins: list) -> None:
        raise NotImplementedError

    async def tenant_load_all(self) -> tuple:
        """Return (tenants, admins_by_tenant) for the in-memory registry cache:
        tenants = [{id, origin, repo, repo_url, strip_suffix, giphy_key}, ...],
        admins_by_tenant = {tenant_id: {login, ...}}."""
        raise NotImplementedError

    async def tenant_get(self, tenant_id: str) -> Optional[dict]:
        raise NotImplementedError

    async def tenant_admins(self, tenant_id: str) -> list:
        raise NotImplementedError

    async def tenant_create(self, tenant_id: str, origin: str, repo: str = "",
                            repo_url: str = "", admins: Optional[list] = None,
                            strip_suffix: str = "", giphy_key: str = "") -> None:
        raise NotImplementedError

    async def tenant_delete(self, tenant_id: str, purge: bool = False) -> None:
        raise NotImplementedError

    async def tenant_admin_add(self, tenant_id: str, login: str) -> None:
        raise NotImplementedError

    async def tenant_admin_remove(self, tenant_id: str, login: str) -> None:
        raise NotImplementedError

    async def tenant_list(self) -> list:
        raise NotImplementedError

    # --- discussions (the per-page container) --------------------------------
    async def discussion_get(self, tenant_id: str, term: str) -> Optional[dict]:
        raise NotImplementedError

    async def discussion_upsert(self, tenant_id: str, term: str, title, subtitle, url) -> None:
        raise NotImplementedError

    # --- comments ------------------------------------------------------------
    async def comment_insert(self, c: dict) -> None:
        raise NotImplementedError

    async def comment_get(self, comment_id: str) -> Optional[dict]:
        raise NotImplementedError

    async def comment_update_body(self, comment_id: str, body_md: str, body_html: str,
                                  updated_at: float) -> None:
        raise NotImplementedError

    async def comment_set_hidden(self, comment_id: str, hide: bool, reason: Optional[str],
                                 hidden_at: Optional[float]) -> None:
        raise NotImplementedError

    async def comment_delete(self, comment_id: str) -> list:
        raise NotImplementedError

    async def comments_top(self, tenant_id: str, term: str, limit: int, offset: int) -> list:
        raise NotImplementedError

    async def comments_top_count(self, tenant_id: str, term: str) -> int:
        raise NotImplementedError

    async def comments_replies(self, parent_ids: list) -> dict:
        raise NotImplementedError

    # --- reactions -----------------------------------------------------------
    async def reactions_for(self, comment_ids: list, viewer: Optional[str]) -> dict:
        raise NotImplementedError

    async def react_toggle(self, comment_id: str, login: str, content: str, on: bool,
                           tenant_id: str) -> None:
        raise NotImplementedError

    async def reactions_purge(self, comment_id: str) -> None:
        raise NotImplementedError
