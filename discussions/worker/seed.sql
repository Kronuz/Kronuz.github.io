-- Seed data for local testing. Applied with:
--   wrangler d1 execute discussions --local --file=./seed.sql
--
-- Optional: the Worker lazily seeds the `default` tenant on first request from the
-- SITE_URL / REPO / ADMIN_LOGINS vars, so a fresh deploy needs no manual seed. This file
-- just makes local tests deterministic.
--
-- Single blog for now (Kronuz.github.io). The store stays multi-tenant, so adding another
-- blog later is one more tenant row (origin -> repo + admins), nothing structural. Local
-- dev requests come from http://localhost:4321, which isn't a tenant origin; the Worker
-- falls back to the default tenant for unregistered-but-allowed dev origins, so there's no
-- need to seed localhost.

INSERT OR IGNORE INTO tenants(id, origin, repo, repo_url, created_at, strip_suffix, giphy_key)
VALUES ('default', 'https://kronuz.github.io', 'Kronuz/Kronuz.github.io',
        'https://github.com/Kronuz/Kronuz.github.io', 1700000000.0, '', '');
INSERT OR IGNORE INTO tenant_admins(tenant_id, login) VALUES ('default', 'Kronuz');

