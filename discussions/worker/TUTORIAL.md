# Deploying and operating the multi-tenant comments Worker

This is the end-to-end procedure for the first multi-tenant cutover, adding another
public-comments tenant later, and replacing a tenant's complete configuration.

For routine database inspection, backups, migrations, logs, recovery, and incident
checks after deployment, use [OPERATIONS.md](./OPERATIONS.md).

The examples use these tenants:

| tenant | backend URL | OAuth callback |
| --- | --- | --- |
| `kronuz` | `https://discussions.kronuz.workers.dev/kronuz` | `https://discussions.kronuz.workers.dev/kronuz/auth/callback` |
| `gmendezb-pages` | `https://discussions.kronuz.workers.dev/gmendezb-pages` | `https://discussions.kronuz.workers.dev/gmendezb-pages/auth/callback` |

## 1. Know which files contain secrets

The following files are deliberately gitignored and must remain local:

```text
secrets.sh
tenant-config.kronuz.json
tenant-config.gmendezb-pages.json
.dev.vars
```

`secrets.sh` contains deployment-wide secrets:

```bash
SESSION_SECRET=
CONFIG_MASTER_KEY=<64-character random value>
SERVICE_ADMIN_TOKEN=<64-character random value>
```

- An empty `SESSION_SECRET` tells `deploy.sh` to preserve the value already stored in
  Cloudflare. On a new service, the script generates one.
- `CONFIG_MASTER_KEY` encrypts the complete tenant documents in D1.
- `SERVICE_ADMIN_TOKEN` authorizes `PUT /:tenant/config`.

Each `tenant-config.*.json` is the complete editable source of truth for that tenant,
including its OAuth client secret, webhook, and feed token. `GET /:tenant/config` is
intentionally public and redacted, so it cannot reconstruct this private document.

## 2. Find or create the GitHub OAuth Apps

These are **OAuth Apps**, not GitHub Apps.

For an app owned by your personal account:

1. Sign into the GitHub account that owns it.
2. Click the profile picture in the upper-right.
3. Open **Settings**.
4. Open **Developer settings** in the left sidebar.
5. Open **OAuth apps**.
6. Select the application whose Client ID matches `oauth.clientId` in the tenant JSON.

The direct personal-account page is <https://github.com/settings/developers>.

For an organization-owned app:

1. Open **Your organizations** from the profile menu.
2. Open **Settings** for the owning organization.
3. Open **Developer settings**, then **OAuth apps**.
4. Match the Client ID to the tenant JSON.

If the app is not visible, the usual cause is being signed into the wrong personal,
managed-user, or organization owner account. GitHub documents both ownership locations in
[Creating an OAuth app](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/creating-an-oauth-app)
and the edit path in
[Modifying an OAuth app](https://docs.github.com/en/apps/oauth-apps/maintaining-oauth-apps/modifying-an-oauth-app).

An OAuth App created by an Enterprise Managed User or by an organization with managed
users can only be accessed by members of that enterprise. That makes such an app the right
identity provider for the internal tenant, even though comment privacy itself is a
separate, deferred feature. See
[GitHub's OAuth App best practices](https://docs.github.com/en/enterprise-cloud@latest/apps/oauth-apps/building-oauth-apps/best-practices-for-creating-an-oauth-app).

OAuth Apps support one configured callback URL. The Worker also sends the tenant callback
as `redirect_uri`, so configure the exact URL shown in the table above.

## 3. Finish and check the tenant documents

Every tenant document must include all fields. Start from `tenant-config.example.json` for
a new tenant. For the two current tenants, the prepared files are:

```text
tenant-config.kronuz.json
tenant-config.gmendezb-pages.json
```

Before deployment, make sure neither OAuth secret is blank:

```bash
jq -e '.oauth.clientId != "" and .oauth.clientSecret != ""' \
  tenant-config.kronuz.json tenant-config.gmendezb-pages.json
```

Also verify that each canonical and development origin is present. Both current tenants
allow their deployed origin plus:

```text
http://localhost:4321
http://127.0.0.1:4321
```

Those aliases let `npm run dev` use the production Worker and production comments.

## 4. Validate before touching production

```bash
npm run typecheck
npm test
npx wrangler deploy --dry-run
```

For a full local API validation, run `npm run dev`, then submit the documents to the local
Worker with the `SERVICE_ADMIN_TOKEN` from `.dev.vars`.

## 5. Deploy the Worker

Authenticate once if needed:

```bash
npx wrangler login
```

Then deploy:

```bash
./deploy.sh
```

The script:

1. Verifies Cloudflare authentication.
2. Creates D1 if this is a new service.
3. Applies all remote migrations.
4. Preserves an existing `SESSION_SECRET`.
5. Creates missing `CONFIG_MASTER_KEY` and `SERVICE_ADMIN_TOKEN` bindings using the
   values from `secrets.sh`.
6. Deploys the Worker.

There is a short cutover interval after deployment when a tenant returns `404` until its
complete configuration is submitted. Have both JSON files ready before running the script.

## 6. Submit both complete configurations

Load the service-administrator token into the shell:

```bash
set -a
source ./secrets.sh
set +a
```

Create or replace both tenants:

```bash
curl --fail-with-body -X PUT \
  https://discussions.kronuz.workers.dev/kronuz/config \
  -H "Authorization: Bearer $SERVICE_ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  --data-binary @tenant-config.kronuz.json

curl --fail-with-body -X PUT \
  https://discussions.kronuz.workers.dev/gmendezb-pages/config \
  -H "Authorization: Bearer $SERVICE_ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  --data-binary @tenant-config.gmendezb-pages.json
```

`201 Created` means a new tenant. `200 OK` means an existing tenant was completely
replaced. Both are successful.

## 7. Update the OAuth callback URLs

In the GitHub OAuth App settings found in step 2, change **Authorization callback URL**:

```text
Public:   https://discussions.kronuz.workers.dev/kronuz/auth/callback
Internal: https://discussions.kronuz.workers.dev/gmendezb-pages/auth/callback
```

Click **Update application** after each change.

Update each callback immediately after submitting that tenant's configuration and before
switching its static site to the Worker.

## 8. Verify the service

Check global health and both public configuration projections:

```bash
curl --fail https://discussions.kronuz.workers.dev/health
curl --fail https://discussions.kronuz.workers.dev/kronuz/config
curl --fail https://discussions.kronuz.workers.dev/gmendezb-pages/config
```

Then verify in a browser for each tenant:

1. Open a post.
2. Confirm existing comments load.
3. Sign in through the expected GitHub identity system.
4. Post a comment.
5. Edit it, react to it, and delete it.
6. Confirm the configured webhook and feed, when enabled.
7. Repeat from `npm run dev` on `localhost:4321`.

## 9. Switch the blogs

The public blog uses:

```text
https://discussions.kronuz.workers.dev/kronuz
```

The internal blog uses:

```text
https://discussions.kronuz.workers.dev/gmendezb-pages
```

Build both sites before publishing. Import any existing production Python/SQLite comments
into D1 before publishing the internal switch; the local checkout has no production
`discussions.db` to migrate.

## 10. Remove legacy Cloudflare secrets

Only after both tenants have passed OAuth and comment testing:

```bash
npx wrangler secret delete OAUTH_CLIENT_ID
npx wrangler secret delete OAUTH_CLIENT_SECRET
npx wrangler secret delete NOTIFY_WEBHOOK
npx wrangler secret delete NOTIFY_FEED_TOKEN
```

Keep:

```text
SESSION_SECRET
CONFIG_MASTER_KEY
SERVICE_ADMIN_TOKEN
```

Confirm the final bindings:

```bash
npx wrangler secret list
```

## Adding or changing a tenant later

1. Create or find its OAuth App.
2. Register `https://discussions.kronuz.workers.dev/<tenant>/auth/callback`.
3. Copy `tenant-config.example.json` to a gitignored private file.
4. Fill every field and keep that file as the private source of truth.
5. Send a complete authenticated `PUT /<tenant>/config`.
6. Point the blog widget at `https://discussions.kronuz.workers.dev/<tenant>`.
7. Verify production and localhost login/comment flows.

There is no tenant delete operation. To take one offline without deleting comments, send
its complete configuration with `"active": false`.
