/**
 * Configuration + bindings for the comments Worker, read from the environment.
 *
 * A port of discussions/backend/discussions/config.py, trimmed to the self-hosted,
 * multi-tenant form: the store is always the D1 `Database`, sessions are always the
 * stateless signed cookie, and the tenant registry is always D1-backed. The knobs that
 * selected between forms in the Python config (STORE / SESSION_STORE / TENANTS) are
 * therefore gone.
 */
import type { D1Database } from "@cloudflare/workers-types";

/** Worker bindings + vars (wrangler.toml [vars] and `wrangler secret put`). */
export interface Env {
  DB: D1Database;
  REPO: string;
  SITE_URL: string;
  REPO_URL: string;
  ALLOWED_ORIGINS: string;
  ADMIN_LOGINS: string;
  DEFAULT_TENANT_ID: string;
  OAUTH_CLIENT_ID: string;
  OAUTH_CLIENT_SECRET?: string; // secret
  SESSION_SECRET?: string; // secret
  PUBLIC_BASE_URL: string;
  OAUTH_SCOPE: string;
  COOKIE_CROSS_SITE: string;
  DISCUSSIONS_STRIP_SUFFIX?: string;
  DISCUSSIONS_GIPHY_KEY?: string;
  MAX_BODY?: string;
  REQUEST_MAX_BYTES?: string;
  SESSION_TTL?: string;
  // New-comment notifications (all optional; unset = disabled).
  NOTIFY_KIND?: string; // slack | discord | telegram — picks the webhook payload shape
  NOTIFY_WEBHOOK?: string; // secret: webhook URL (or a Telegram bot sendMessage URL)
  NOTIFY_TELEGRAM_CHAT?: string; // telegram chat id (telegram only)
  NOTIFY_FEED_TOKEN?: string; // secret: gates GET /api/comments/feed
}

/** Always allow the local Astro dev server (npm run dev) so the widget can read/post
 * while developing against this backend, without weakening prod. These map to the
 * default tenant. */
export const DEV_ORIGINS = ["http://localhost:4321", "http://127.0.0.1:4321"];

export interface Cfg {
  repo: string;
  siteUrl: string;
  repoUrl: string;
  allowedOrigins: string[];
  adminLogins: string[];
  defaultTenantId: string;
  oauthClientId: string;
  oauthClientSecret: string;
  sessionSecret: string;
  publicBaseUrl: string;
  oauthScope: string;
  cookieCrossSite: boolean;
  stripSuffix: string;
  giphyKey: string;
  maxBody: number;
  requestMaxBytes: number;
  sessionTtl: number;
  oauthEnabled: boolean;
  wildcard: boolean;
}

function intOr(v: string | undefined, dflt: number): number {
  const n = v ? parseInt(v, 10) : NaN;
  return Number.isFinite(n) ? n : dflt;
}

let _warnedSecret = false;

/** Build the effective config from the request's env bindings. Cheap; done per request. */
export function loadCfg(env: Env): Cfg {
  const allowed = (env.ALLOWED_ORIGINS || "*").split(",").map((s) => s.trim()).filter(Boolean);
  const wildcard = allowed.length === 1 && allowed[0] === "*";
  if (!wildcard) {
    for (const o of DEV_ORIGINS) if (!allowed.includes(o)) allowed.push(o);
  }
  // SESSION_SECRET must be a real, stable secret in prod (it signs session cookies). If
  // it's missing we fall back to a fixed dev value and warn once, rather than minting a
  // random per-isolate secret that would invalidate everyone's cookie on each cold start.
  let sessionSecret = env.SESSION_SECRET || "";
  if (!sessionSecret) {
    sessionSecret = "dev-insecure-session-secret-change-me";
    if (!_warnedSecret) {
      _warnedSecret = true;
      console.warn("SESSION_SECRET is not set; using an insecure dev default. Set it with `wrangler secret put SESSION_SECRET`.");
    }
  }
  const clientId = env.OAUTH_CLIENT_ID || "";
  const clientSecret = env.OAUTH_CLIENT_SECRET || "";
  return {
    repo: env.REPO || "owner/repo",
    siteUrl: env.SITE_URL || "",
    repoUrl: env.REPO_URL || "",
    allowedOrigins: allowed,
    adminLogins: (env.ADMIN_LOGINS || "").split(",").map((s) => s.trim()).filter(Boolean),
    defaultTenantId: env.DEFAULT_TENANT_ID || "default",
    oauthClientId: clientId,
    oauthClientSecret: clientSecret,
    sessionSecret,
    publicBaseUrl: env.PUBLIC_BASE_URL || "http://127.0.0.1:8787",
    oauthScope: env.OAUTH_SCOPE || "read:user",
    cookieCrossSite: (env.COOKIE_CROSS_SITE || "0") === "1",
    stripSuffix: env.DISCUSSIONS_STRIP_SUFFIX || "",
    giphyKey: env.DISCUSSIONS_GIPHY_KEY || "",
    maxBody: intOr(env.MAX_BODY, 65536),
    requestMaxBytes: intOr(env.REQUEST_MAX_BYTES, 1_048_576),
    sessionTtl: intOr(env.SESSION_TTL, 7 * 24 * 3600),
    oauthEnabled: Boolean(clientId && clientSecret),
    wildcard,
  };
}

/** A structured HTTP error carrying a status code, mapped to a JSON body by the app.
 * Mirrors FastAPI's HTTPException so ports of the store/routes read the same. */
export class HttpError extends Error {
  status: number;
  headers?: Record<string, string>;
  constructor(status: number, detail: string, headers?: Record<string, string>) {
    super(detail);
    this.status = status;
    this.headers = headers;
  }
}
