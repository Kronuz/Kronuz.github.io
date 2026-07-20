-- Move the original single-tenant deployment to its permanent URL tenant ID without
-- touching comment IDs or bodies. Fresh databases simply update zero rows.
UPDATE discussions SET tenant_id='kronuz-public' WHERE tenant_id='default';
UPDATE comments SET tenant_id='kronuz-public' WHERE tenant_id='default';
UPDATE reactions SET tenant_id='kronuz-public' WHERE tenant_id='default';
UPDATE tenant_admins SET tenant_id='kronuz-public' WHERE tenant_id='default';
UPDATE tenants SET id='kronuz-public' WHERE id='default';

-- New comments authorize against the OAuth provider's stable subject. Legacy comments
-- retain the login fallback until their author next writes them.
ALTER TABLE comments ADD COLUMN author_subject TEXT NOT NULL DEFAULT '';
