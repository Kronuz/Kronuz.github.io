#!/usr/bin/env bash
#
# Guided deploy of the discussions Worker to Cloudflare (D1 + secrets + OAuth + deploy).
#
# Safe to re-run: each step checks whether it's already done. Requires `wrangler login`
# to have been run once (an authenticated Cloudflare account).
#
#   ./deploy.sh
#
set -uo pipefail
cd "$(dirname "$0")"

WRANGLER="npx wrangler"
say()  { printf '\n\033[1;32m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m%s\033[0m\n' "$*"; }
die()  { printf '\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

# portable in-place sed (BSD/macOS + GNU)
sedi() { sed -i.bak "$@" && rm -f "${@: -1}.bak" 2>/dev/null || true; }

# --- 0. preflight ------------------------------------------------------------
command -v npx >/dev/null || die "node/npx not found."
$WRANGLER whoami >/dev/null 2>&1 || die "Not logged in. Run: npx wrangler login"
say "Authenticated with Cloudflare as: $($WRANGLER whoami 2>/dev/null | grep -oE '[^ ]+@[^ ]+' | head -1 || echo '(account ok)')"

# --- 1. D1 database ----------------------------------------------------------
if grep -q 'database_id = "local-dev-placeholder"' wrangler.toml; then
  say "Creating D1 database 'discussions'"
  out=$($WRANGLER d1 create discussions) || die "d1 create failed"
  echo "$out"
  id=$(printf '%s' "$out" | grep -oiE '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}' | head -1)
  [ -n "$id" ] || die "Could not parse database_id from the output above; paste it into wrangler.toml by hand."
  sedi "s/database_id = \"local-dev-placeholder\"/database_id = \"$id\"/" wrangler.toml
  say "Set database_id = $id in wrangler.toml"
else
  say "D1 database already configured (skipping create)"
fi

# --- 2. migrations (remote) --------------------------------------------------
say "Applying migrations to the remote D1 database"
$WRANGLER d1 migrations apply discussions --remote || die "migrations failed"

# --- 3. session secret -------------------------------------------------------
if $WRANGLER secret list 2>/dev/null | grep -q "SESSION_SECRET"; then
  say "SESSION_SECRET already set (skipping)"
else
  say "Generating and storing SESSION_SECRET"
  if command -v openssl >/dev/null; then secret=$(openssl rand -hex 32); else secret=$(head -c 32 /dev/urandom | xxd -p | tr -d '\n'); fi
  printf '%s' "$secret" | $WRANGLER secret put SESSION_SECRET || die "failed to set SESSION_SECRET"
fi

# --- 4. first deploy (to learn the Worker's URL) -----------------------------
say "Deploying (first pass, to obtain the Worker URL)"
if ! dout=$($WRANGLER deploy 2>&1); then
  echo "$dout"
  if printf '%s' "$dout" | grep -qiE "workers\.dev subdomain|register a workers\.dev|/workers/onboarding"; then
    cat <<'TXT'

Your Cloudflare account has no workers.dev subdomain yet (required before the first deploy).
Register one (the onboarding link Cloudflare prints often 404s — navigate manually instead):
  1. Open https://dash.cloudflare.com and pick your account.
  2. In the sidebar open "Workers & Pages" (newer dashboards label it "Compute").
  3. On first visit it prompts to choose a subdomain, e.g. "kronuz" -> *.kronuz.workers.dev.
Then re-run ./deploy.sh — it resumes (the earlier steps are idempotent).
TXT
    exit 1
  fi
  die "First deploy failed (see the output above)."
fi
echo "$dout"
url=$(printf '%s' "$dout" | grep -oE 'https://[a-zA-Z0-9.-]+\.workers\.dev' | head -1)
[ -n "$url" ] || warn "Could not auto-detect the Worker URL from the deploy output above."

# --- 5. set PUBLIC_BASE_URL (fill the placeholder, or fix a stale workers.dev URL) ----
cur=$(grep -oE 'PUBLIC_BASE_URL = "[^"]*"' wrangler.toml | sed 's/.*"\(.*\)"/\1/')
if printf '%s' "$cur" | grep -q 'CHANGE-ME'; then
  if [ -n "$url" ]; then
    sedi "s#PUBLIC_BASE_URL = \".*\"#PUBLIC_BASE_URL = \"$url\"#" wrangler.toml
    say "Set PUBLIC_BASE_URL = $url in wrangler.toml"
  else
    warn "Edit wrangler.toml and set PUBLIC_BASE_URL to your Worker (or custom domain) URL, then re-run."
  fi
elif [ -n "$url" ] && printf '%s' "$cur" | grep -q '\.workers\.dev' && [ "$cur" != "$url" ]; then
  # A stale *.workers.dev URL (e.g. after changing the account subdomain) — self-correct.
  sedi "s#PUBLIC_BASE_URL = \".*\"#PUBLIC_BASE_URL = \"$url\"#" wrangler.toml
  warn "PUBLIC_BASE_URL was $cur but the Worker is at $url — updated it."
  warn "Remember to update the GitHub OAuth App callback URL to $url/auth/callback."
else
  say "PUBLIC_BASE_URL = ${cur:-<unset>} (respecting it; a custom domain?)"
  url="${cur:-$url}"
fi

# --- 6. GitHub OAuth App -----------------------------------------------------
say "GitHub OAuth App"
cat <<TXT
Create (or reuse) a GitHub OAuth App: https://github.com/settings/developers -> "New OAuth App"
  Application name:            Kronuz blog comments   (anything)
  Homepage URL:               https://kronuz.github.io
  Authorization callback URL: ${url:-<your Worker URL>}/auth/callback
Then generate a client secret and have the Client ID + secret ready.
TXT

if $WRANGLER secret list 2>/dev/null | grep -q "OAUTH_CLIENT_ID"; then
  say "OAUTH_CLIENT_ID already set. Re-enter to update it, or leave blank to keep."
fi
printf 'OAuth Client ID (blank to skip OAuth setup this run): '
read -r CID
if [ -n "$CID" ]; then
  printf '%s' "$CID" | $WRANGLER secret put OAUTH_CLIENT_ID || die "failed to set OAUTH_CLIENT_ID"
  say "Now paste the OAuth Client secret when prompted (input hidden):"
  $WRANGLER secret put OAUTH_CLIENT_SECRET || die "failed to set OAUTH_CLIENT_SECRET"
else
  warn "Skipped OAuth secrets. Sign-in stays disabled until OAUTH_CLIENT_ID + OAUTH_CLIENT_SECRET are set."
fi

# --- 6b. GIF picker (optional): the composer's GIPHY picker ------------------
say "GIF picker (optional)"
cat <<'TXT'
A public GIPHY API key enables the comment composer's GIF picker. The key is served to
browsers via /api/config, so use one you're comfortable exposing on a public site.
TXT
def_tenant=$(grep -oE 'DEFAULT_TENANT_ID = "[^"]*"' wrangler.toml | sed 's/.*"\(.*\)"/\1/'); def_tenant=${def_tenant:-default}
printf 'GIPHY API key (blank to skip; leaves any existing key unchanged): '
read -r GKEY
if [ -n "$GKEY" ]; then
  gkey_esc=$(printf '%s' "$GKEY" | sed "s/'/''/g")
  $WRANGLER d1 execute discussions --remote \
    --command "UPDATE tenants SET giphy_key='$gkey_esc' WHERE id='$def_tenant'" \
    && say "GIF picker enabled for tenant '$def_tenant'." \
    || warn "Could not set giphy_key (set it later with a d1 execute UPDATE)."
else
  warn "Skipped the GIF picker (existing giphy_key, if any, left unchanged)."
fi

# --- 7. final deploy (applies PUBLIC_BASE_URL + any new secrets) --------------
say "Deploying (final)"
$WRANGLER deploy || die "deploy failed"

# --- 8. wire the blog --------------------------------------------------------
say "Done. Backend is live at: ${url:-<your Worker URL>}"
cat <<TXT

Last step, in the blog (this repo):
  set  DISCUSSIONS_BACKEND = '${url:-<your Worker URL>}'  in  src/consts.ts
  then rebuild + deploy the site (GitHub Pages).

That flips blog posts from giscus to this self-hosted widget. Verify:
  curl ${url:-<your Worker URL>}/api/health
TXT
