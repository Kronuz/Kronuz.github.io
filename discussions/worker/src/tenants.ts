/**
 * Tenant registry — resolves a request's Origin to a tenant, plus that tenant's
 * moderators and widget config.
 *
 * A port of the DbTenants path from discussions/backend/discussions/tenants.py. The Python
 * app held this in an in-process cache refreshed by a background task; a Worker has no
 * long-lived process, so we load it from D1 per request (two small indexed SELECTs). The
 * default tenant is seeded from env on first use (when it's absent), the same values the
 * Python backend seeds at startup.
 */
import type { Cfg } from "./config.js";
import type { Database, TenantRow } from "./db.js";

export class TenantRegistry {
  private byId = new Map<string, TenantRow>();
  private originToTenant = new Map<string, string>();
  private originSet = new Set<string>();
  private adminsByTenant = new Map<string, Set<string>>();

  private set(tenants: TenantRow[], admins: Record<string, Set<string>>): void {
    this.byId.clear();
    this.originToTenant.clear();
    this.originSet.clear();
    this.adminsByTenant.clear();
    for (const t of tenants) {
      this.byId.set(t.id, t);
      if (t.origin) {
        this.originToTenant.set(t.origin, t.id);
        this.originSet.add(t.origin);
      }
    }
    for (const [tid, adminSet] of Object.entries(admins)) this.adminsByTenant.set(tid, new Set(adminSet));
  }

  /** Replace the registry's contents (used by the loader). */
  replace(tenants: TenantRow[], admins: Record<string, Set<string>>): void {
    this.set(tenants, admins);
  }

  idForOrigin(origin: string | null | undefined): string | null {
    return this.originToTenant.get(origin || "") ?? null;
  }

  isAdmin(tenantId: string, login: string | null | undefined): boolean {
    return Boolean(login) && (this.adminsByTenant.get(tenantId)?.has(login as string) ?? false);
  }

  origins(): Set<string> {
    return new Set(this.originSet);
  }

  get(tenantId: string): TenantRow | null {
    return this.byId.get(tenantId) ?? null;
  }

  admins(tenantId: string): string[] {
    return [...(this.adminsByTenant.get(tenantId) ?? [])].sort();
  }
}

/** Build a registry from D1 for this request, seeding the default tenant if it's missing.
 * (Seeding only-when-absent avoids a write on every request; admin membership changes go
 * through the admin routes, not by re-seeding here.) */
export async function loadTenants(db: Database, cfg: Cfg): Promise<TenantRegistry> {
  let { tenants, admins } = await db.tenantLoadAll();
  if (!tenants.some((t) => t.id === cfg.defaultTenantId)) {
    await db.tenantSeedDefault(cfg.defaultTenantId, cfg.siteUrl, cfg.repo, cfg.repoUrl, cfg.adminLogins);
    ({ tenants, admins } = await db.tenantLoadAll());
  }
  const reg = new TenantRegistry();
  reg.replace(tenants, admins);
  return reg;
}
