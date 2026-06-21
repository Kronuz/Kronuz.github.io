"""Configuration for the comments backend, read from the environment.

`.env` (sourced by run.sh) is the single source of truth; site.config.json carries
only the non-secret subset the website build reads.
"""
import os
import secrets

REPO = os.environ.get("REPO", "owner/repo")
OWNER, NAME = REPO.split("/", 1)
# The blog's own URLs, used to seed the default tenant (below). SITE_URL is the site
# origin; REPO_URL is the "view on GitHub" link. Both are per-blog (per-tenant) values.
SITE_URL = os.environ.get("SITE_URL", "")
REPO_URL = os.environ.get("REPO_URL", "")
# Per-tenant widget config served by GET /api/config. The config-tenant path (github
# form) reads these from env; the db-tenant path reads them from the tenant row.
# DISCUSSIONS_STRIP_SUFFIX drops a login suffix when displaying handles (cosmetic);
# DISCUSSIONS_GIPHY_KEY enables the composer's client-side GIF picker.
DISCUSSIONS_STRIP_SUFFIX = os.environ.get("DISCUSSIONS_STRIP_SUFFIX", "")
DISCUSSIONS_GIPHY_KEY = os.environ.get("DISCUSSIONS_GIPHY_KEY", "")

# Discussion category new threads are created under (giscus-style auto-create on
# first comment). Matched case-insensitively by name or slug; falls back to the
# repo's first category if the configured one isn't found. "Announcements"-type
# categories only let maintainers open threads, so a general category is best.
DISCUSSION_CATEGORY = os.environ.get("DISCUSSION_CATEGORY", "General")

ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "*").split(",")
# Always allow the local Astro dev server (npm run dev) so the widget can read
# comments while developing against this backend, without weakening prod. These map to
# the default tenant (dev works against this instance's own blog).
DEV_ORIGINS = ["http://localhost:4321", "http://127.0.0.1:4321"]
if ALLOWED_ORIGINS != ["*"]:
    ALLOWED_ORIGINS += [o for o in DEV_ORIGINS if o not in ALLOWED_ORIGINS]

# --- Architecture: store, database, sessions, tenants ------------------------
# STORE: where comments live. "selfhosted" (a Database holds the system of record) or
# "github" (real GitHub Discussions via GraphQL). Back-compat: the old
# DISCUSSIONS_BACKEND=sqlite|github maps to selfhosted|github.
_legacy_backend = os.environ.get("DISCUSSIONS_BACKEND", "sqlite")
STORE = os.environ.get("STORE") or ("github" if _legacy_backend == "github" else "selfhosted")
# DATABASE: the self-hosted store's backing driver (also backs db sessions/tenants).
# "sqlite" today; "mysql"/"postgres" would be added drivers (see db/__init__.py).
DATABASE = os.environ.get("DATABASE", "sqlite")
# SESSION_STORE: where OAuth sessions live. "db" (in the Database; the default for the
# self-hosted form, which already has one) or "lru" (in-memory; the default for the
# github form, so it needs no database at all). "cookie" (stateless) is also available.
SESSION_STORE = os.environ.get("SESSION_STORE") or ("lru" if STORE == "github" else "db")
# TENANTS: the tenant registry. "db" (multi-tenant, in the Database) or "config" (a
# single tenant from this instance's env; the default for the github form).
TENANTS = os.environ.get("TENANTS") or ("config" if STORE == "github" else "db")
# Compat alias still read by GET /api/me and the widget: "github" or "sqlite".
DISCUSSIONS_BACKEND = "github" if STORE == "github" else "sqlite"

# Server-side token the *github* store uses to READ discussions for signed-out
# visitors: GitHub's GraphQL API needs auth even for public data, so an anonymous
# reader can't query it directly. WRITES always use the reader's own OAuth token
# (authentic authorship); this token is only the read fallback (a signed-in reader's
# own token is used for reads instead, so viewerHasReacted is accurate). A
# fine-grained PAT with Discussions:read (or classic public_repo read) on REPO is
# enough; giscus uses its app's installation token for the same job. Unused otherwise.
GITHUB_READ_TOKEN = os.environ.get("GITHUB_READ_TOKEN", "")

# --- OAuth / identity --------------------------------------------------------
# Extra GitHub logins allowed to moderate (hide/delete any comment), comma-separated.
# The server token's own account is always treated as an admin (resolved at startup).
ADMIN_LOGINS = [s.strip() for s in os.environ.get("ADMIN_LOGINS", "").split(",") if s.strip()]
OAUTH_CLIENT_ID = os.environ.get("OAUTH_CLIENT_ID", "")
OAUTH_CLIENT_SECRET = os.environ.get("OAUTH_CLIENT_SECRET", "")
# The github store needs the reader's token to write Discussions (repo scope); the
# sqlite store only needs identity (read:user).
OAUTH_SCOPE = os.environ.get(
    "OAUTH_SCOPE", "repo" if DISCUSSIONS_BACKEND == "github" else "read:user"
)
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://127.0.0.1:8099")
SESSION_SECRET = os.environ.get("SESSION_SECRET", secrets.token_hex(16))
COOKIE_CROSS_SITE = os.environ.get("COOKIE_CROSS_SITE", "0") == "1"
OAUTH_ENABLED = bool(OAUTH_CLIENT_ID and OAUTH_CLIENT_SECRET)

# --- Multi-tenant ------------------------------------------------------------
# Every comment/discussion/reaction is scoped to a *tenant* (a hosted blog). Phase 1:
# the backend serves one blog, so all rows belong to a single default tenant, seeded at
# startup from this instance's env (SITE_URL / REPO / REPO_URL / ADMIN_LOGINS). The
# schema is ready for more tenants; per-request tenant resolution (from the request
# Origin) and per-tenant moderation come in later phases. See discussions/ROADMAP.md.
DEFAULT_TENANT_ID = os.environ.get("DEFAULT_TENANT_ID", "default")

# --- SQLite store ------------------------------------------------------------
# Anchor paths at the backend dir (this package's parent) so the SQLite file and the
# widget resolve the same way regardless of the package's depth.
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SESSION_TTL = int(os.environ.get("SESSION_TTL", str(7 * 24 * 3600)))  # 7 days
# One SQLite file holds the whole system: OAuth sessions, comments, and reactions.
DB_PATH = os.environ.get("DB_PATH", os.path.join(_BACKEND_DIR, "discussions.db"))

# --- Limits / abuse protection -----------------------------------------------
# Max characters in a comment (and the preview body). GitHub caps comment bodies at
# 65536; oversized input is rejected (413) before we render or store it.
MAX_BODY = int(os.environ.get("MAX_BODY", 65536))
# Coarse early backstop: reject a request whose Content-Length exceeds this, before the
# body is read/parsed (so a giant payload can't be buffered into memory). Generous vs
# MAX_BODY (which is chars; bytes can be larger for multibyte + JSON overhead) — its job
# is only to stop multi-MB junk, not to enforce the exact comment length.
REQUEST_MAX_BYTES = int(os.environ.get("REQUEST_MAX_BYTES", 1_048_576))  # 1 MB

# --- Logging -----------------------------------------------------------------
# The app logs to stdout; run.sh redirects the server's stdout/stderr to a single
# file (LOG_FILE, default discussions.log) under systemd, since the journal isn't
# readable on the host. LOG_LEVEL tunes the app's verbosity.
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

# Widget static dir (served at /demo for the same-origin demo page).
WIDGET_DIR = os.path.join(_BACKEND_DIR, "..", "widget")
