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
dout=$($WRANGLER deploy 2>&1); echo "$dout"
url=$(printf '%s' "$dout" | grep -oE 'https://[a-zA-Z0-9.-]+\.workers\.dev' | head -1)
[ -n "$url" ] || warn "Could not auto-detect the Worker URL from the deploy output above."

# --- 5. set PUBLIC_BASE_URL (unless a custom domain is already configured) ----
if grep -q 'PUBLIC_BASE_URL = ".*CHANGE-ME.*"' wrangler.toml; then
  if [ -n "$url" ]; then
    sedi "s#PUBLIC_BASE_URL = \".*\"#PUBLIC_BASE_URL = \"$url\"#" wrangler.toml
    say "Set PUBLIC_BASE_URL = $url in wrangler.toml"
  else
    warn "Edit wrangler.toml and set PUBLIC_BASE_URL to your Worker (or custom domain) URL, then re-run."
  fi
else
  base=$(grep -oE 'PUBLIC_BASE_URL = "[^"]*"' wrangler.toml | sed 's/.*"\(.*\)"/\1/')
  say "PUBLIC_BASE_URL already set to $base (respecting it; a custom domain?)"
  url="$base"
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
