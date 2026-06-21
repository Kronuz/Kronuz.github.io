"""Tenant registry — resolves a request's Origin to a tenant, plus that tenant's
moderators and widget config. Lookups are sync reads of an in-memory cache (hit on
every request), populated by one of:

- ConfigTenants: a single default tenant from this instance's env. No database. The
  default for the github form.
- DbTenants: loaded from the active Database (multi-tenant), refreshed on tenant writes.

Both share the cache + the sync lookups (origin->tenant, is_admin, origins, get); they
differ only in how load() fills it.
"""
from typing import Optional

from .config import (ADMIN_LOGINS, DEFAULT_TENANT_ID, DISCUSSIONS_GIPHY_KEY,
                     DISCUSSIONS_STRIP_SUFFIX, REPO, REPO_URL, SITE_URL)


class TenantRegistry:
    def __init__(self) -> None:
        self._by_id: dict = {}            # tenant_id -> {id, origin, repo, repo_url, strip_suffix, giphy_key}
        self._origin_to_tenant: dict = {}  # origin -> tenant_id
        self._origins: set = set()         # all registered origins
        self._admins: dict = {}            # tenant_id -> {login, ...}

    def _set(self, tenants: list, admins: dict) -> None:
        self._by_id = {t["id"]: t for t in tenants}
        self._origin_to_tenant = {t["origin"]: t["id"] for t in tenants if t.get("origin")}
        self._origins = {t["origin"] for t in tenants if t.get("origin")}
        self._admins = {tid: set(v) for tid, v in admins.items()}

    async def load(self) -> None:
        raise NotImplementedError

    # --- sync lookups (hot path) ---------------------------------------------
    def id_for_origin(self, origin: Optional[str]) -> Optional[str]:
        return self._origin_to_tenant.get(origin or "")

    def is_admin(self, tenant_id: str, login: Optional[str]) -> bool:
        return bool(login) and login in self._admins.get(tenant_id, ())

    def origins(self) -> set:
        return set(self._origins)

    def get(self, tenant_id: str) -> Optional[dict]:
        return self._by_id.get(tenant_id)

    def admins(self, tenant_id: str) -> list:
        return sorted(self._admins.get(tenant_id, ()))


class ConfigTenants(TenantRegistry):
    """One tenant, from this instance's env. No database (the github/lean form)."""

    name = "config"

    async def load(self) -> None:
        tenant = {"id": DEFAULT_TENANT_ID, "origin": SITE_URL, "repo": REPO,
                  "repo_url": REPO_URL, "strip_suffix": DISCUSSIONS_STRIP_SUFFIX,
                  "giphy_key": DISCUSSIONS_GIPHY_KEY}
        self._set([tenant], {DEFAULT_TENANT_ID: set(ADMIN_LOGINS)})


class DbTenants(TenantRegistry):
    """Tenants loaded from the active Database (multi-tenant). Seeds the default tenant
    from env on first load; call load() again after any tenant write to refresh."""

    name = "db"

    def __init__(self, db) -> None:
        super().__init__()
        self.db = db

    async def load(self) -> None:
        await self.db.tenant_seed_default(DEFAULT_TENANT_ID, SITE_URL, REPO, REPO_URL, ADMIN_LOGINS)
        tenants, admins = await self.db.tenant_load_all()
        self._set(tenants, admins)


def build_tenants(db=None) -> TenantRegistry:
    """The active tenant registry, selected by config.TENANTS. `db` is required for the
    'db' registry."""
    from .config import TENANTS
    if TENANTS == "config":
        return ConfigTenants()
    if TENANTS == "db":
        if db is None:
            raise RuntimeError("TENANTS=db needs a Database (DATABASE must be set)")
        return DbTenants(db)
    raise RuntimeError(f"unknown TENANTS={TENANTS!r}; expected config|db")
