-- The public blog's permanent, human-facing tenant path is simply /kronuz. Migration
-- 0003 may already have run locally, so preserve its history and rename in a new step.
UPDATE discussions SET tenant_id='kronuz' WHERE tenant_id='kronuz-public';
UPDATE comments SET tenant_id='kronuz' WHERE tenant_id='kronuz-public';
UPDATE reactions SET tenant_id='kronuz' WHERE tenant_id='kronuz-public';
UPDATE tenant_admins SET tenant_id='kronuz' WHERE tenant_id='kronuz-public';
UPDATE tenants SET id='kronuz' WHERE id='kronuz-public';
