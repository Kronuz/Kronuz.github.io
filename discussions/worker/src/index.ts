/**
 * discussions Worker — self-hosted, multi-tenant blog comments on Hono + Cloudflare D1.
 *
 * A port of discussions/backend/discussions/app.py (+ auth.py, comments.py, reactions.py),
 * trimmed to the self-hosted store. Wiring the Python app did at startup (runtime.py) is
 * done per request here from `c.env` bindings, because a Worker has no lifespan: each
 * request builds the D1 Database, loads the tenant registry, and constructs the cookie
 * session store + self-hosted store. The two background tasks (session sweeper, tenant
 * refresher) are gone: sessions are stateless cookies, and the registry is read per
 * request. CORS + origin enforcement are driven by the live tenant set, so a newly
 * onboarded blog works without a redeploy.
 */
import { type Context, Hono } from "hono";
import { getCookie, setCookie, deleteCookie } from "hono/cookie";
import { cors } from "hono/cors";
import { type Cfg, type Env, DEV_ORIGINS, HttpError, loadCfg } from "./config.js";
import { Database } from "./db.js";
import * as gh from "./gh.js";
import { RateLimit } from "./ratelimit.js";
import { CookieSessionStore } from "./sessions.js";
import { SelfHostedStore, type Viewer } from "./store.js";
import { loadTenants, type TenantRegistry } from "./tenants.js";

type Vars = {
  cfg: Cfg;
  db: Database;
  tenants: TenantRegistry;
  sessions: CookieSessionStore;
  store: SelfHostedStore;
};

type App = Hono<{ Bindings: Env; Variables: Vars }>;
const app: App = new Hono<{ Bindings: Env; Variables: Vars }>();

const enc = new TextEncoder();

// --- rate limits (per-isolate best-effort; see ratelimit.ts) -----------------
const rl = {
  read: new RateLimit(120, 60),
  post: new RateLimit(6, 60),
  edit: new RateLimit(30, 60),
  del: new RateLimit(30, 60),
  hide: new RateLimit(60, 60),
  preview: new RateLimit(30, 60),
  react: new RateLimit(60, 60),
};

type Ctx = Context<{ Bindings: Env; Variables: Vars }>;

function clientKey(c: Ctx, viewer: Viewer | null): string {
  if (viewer?.login) return "u:" + viewer.login;
  return "ip:" + (c.req.header("cf-connecting-ip") || "unknown");
}

function limit(c: Ctx, limiter: RateLimit, viewer: Viewer | null): void {
  const retry = limiter.check(clientKey(c, viewer));
  if (retry !== null) {
    throw new HttpError(429, "Too many requests; slow down.", { "Retry-After": String(retry) });
  }
}

// --- context helpers ---------------------------------------------------------
function requestTenant(c: Ctx): string {
  const origin = c.req.header("origin");
  return c.get("tenants").idForOrigin(origin) || c.get("cfg").defaultTenantId;
}

async function currentSession(c: Ctx) {
  // Prefer the Authorization: Bearer token (the cross-platform path; the widget keeps it in
  // localStorage), falling back to the cookie for same-site/desktop callers.
  const auth = c.req.header("authorization");
  let sid = auth && auth.startsWith("Bearer ") ? auth.slice(7).trim() : "";
  if (!sid) sid = getCookie(c, "gc_session") || "";
  if (!sid) return null;
  return c.get("sessions").get(sid);
}

async function currentViewer(c: Ctx): Promise<Viewer | null> {
  const sess = await currentSession(c);
  if (!sess) return null;
  const tenantId = requestTenant(c);
  return {
    login: sess.login,
    name: sess.name,
    avatarUrl: sess.avatarUrl,
    url: sess.url ?? null,
    tenant_id: tenantId,
    is_admin: c.get("tenants").isAdmin(tenantId, sess.login),
  };
}

// --- OAuth `state` signing (CSRF) -------------------------------------------
async function hmacSign(secret: string, msg: string): Promise<Uint8Array> {
  const key = await crypto.subtle.importKey("raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, [
    "sign",
  ]);
  return new Uint8Array(await crypto.subtle.sign("HMAC", key, enc.encode(msg)));
}

function toHex(b: Uint8Array): string {
  return [...b].map((x) => x.toString(16).padStart(2, "0")).join("");
}

async function makeState(secret: string, returnUrl: string): Promise<string> {
  const raw = btoa(JSON.stringify({ r: returnUrl, n: toHex(crypto.getRandomValues(new Uint8Array(8))), t: Math.floor(Date.now() / 1000) }))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
  return raw + "." + toHex(await hmacSign(secret, raw));
}

async function readState(secret: string, signed: string): Promise<{ r?: string; t?: number } | null> {
  const i = signed.lastIndexOf(".");
  if (i < 0) return null;
  const raw = signed.slice(0, i);
  const mac = signed.slice(i + 1);
  if (mac !== toHex(await hmacSign(secret, raw))) return null;
  let data: { r?: string; t?: number };
  try {
    let s = raw.replace(/-/g, "+").replace(/_/g, "/");
    while (s.length % 4) s += "=";
    data = JSON.parse(atob(s));
  } catch {
    return null;
  }
  if (Math.floor(Date.now() / 1000) - Number(data.t || 0) > 600) return null;
  return data;
}

// --- middleware --------------------------------------------------------------

// Reject an oversized body by its declared Content-Length before it's read into memory.
app.use("*", async (c, next) => {
  const cl = c.req.header("content-length");
  const max = parseInt(c.env.REQUEST_MAX_BYTES || "1048576", 10);
  if (cl && /^\d+$/.test(cl) && parseInt(cl, 10) > max) {
    return c.json({ detail: "request too large" }, 413);
  }
  await next();
});

// Build the per-request pieces from env bindings (what runtime.py did at startup).
app.use("*", async (c, next) => {
  const cfg = loadCfg(c.env);
  const db = new Database(c.env.DB);
  const tenants = await loadTenants(db, cfg);
  c.set("cfg", cfg);
  c.set("db", db);
  c.set("tenants", tenants);
  c.set("sessions", new CookieSessionStore(cfg.sessionSecret, cfg.sessionTtl));
  c.set("store", new SelfHostedStore(db, tenants, cfg));
  await next();
});

// CORS driven by the live tenant set: an Origin is allowed iff it's a registered tenant's
// origin or a local dev origin (or anything, in open wildcard mode). We echo the origin
// rather than "*", so credentials (the session cookie) stay enabled.
app.use("*", (c, next) =>
  cors({
    origin: (origin) => {
      if (!origin) return null;
      const cfg = c.get("cfg");
      const tenants = c.get("tenants");
      if (cfg.wildcard) return origin;
      if (DEV_ORIGINS.includes(origin) || tenants.origins().has(origin)) return origin;
      return null;
    },
    credentials: true,
    allowMethods: ["GET", "POST", "OPTIONS"],
    allowHeaders: ["Content-Type", "Authorization"],
  })(c, next),
);

// Origin enforcement (the multi-tenant security crux): a cross-origin API request whose
// Origin is not a registered tenant is rejected, so a random site can't post into (or read)
// another blog's threads. Skip wildcard mode, OPTIONS (CORS handled it), and /api/health.
app.use("*", async (c, next) => {
  const cfg = c.get("cfg");
  if (!cfg.wildcard && c.req.method !== "OPTIONS") {
    const origin = c.req.header("origin");
    const path = new URL(c.req.url).pathname;
    if (origin && path.startsWith("/api/") && path !== "/api/health") {
      const registered = DEV_ORIGINS.includes(origin) || c.get("tenants").idForOrigin(origin) !== null;
      if (!registered) return c.json({ detail: "origin not registered" }, 403);
    }
  }
  await next();
});

// --- health ------------------------------------------------------------------
app.get("/api/health", (c) => c.json({ ok: true, repo: c.get("cfg").repo }));

// --- auth + identity ---------------------------------------------------------
app.get("/api/me", async (c) => {
  const cfg = c.get("cfg");
  const sess = await currentSession(c);
  const base = { oauth: cfg.oauthEnabled, backend: "sqlite" };
  if (!sess) return c.json({ ...base, authenticated: false });
  const tenantId = requestTenant(c);
  return c.json({
    ...base,
    authenticated: true,
    login: sess.login,
    avatarUrl: sess.avatarUrl,
    name: sess.name,
    isAdmin: c.get("tenants").isAdmin(tenantId, sess.login),
  });
});

app.get("/api/config", (c) => {
  const t = c.get("tenants").get(requestTenant(c));
  if (!t) return c.json({});
  return c.json({
    repo: t.repo || "",
    repoUrl: t.repo_url || "",
    siteUrl: t.origin || "",
    stripSuffix: t.strip_suffix || "",
    giphyKey: t.giphy_key || "",
  });
});

app.get("/auth/login", async (c) => {
  const cfg = c.get("cfg");
  if (!cfg.oauthEnabled) throw new HttpError(503, "OAuth not configured");
  const returnUrl = c.req.query("return") || "/";
  const params = new URLSearchParams({
    client_id: cfg.oauthClientId,
    redirect_uri: cfg.publicBaseUrl + "/auth/callback",
    scope: cfg.oauthScope,
    state: await makeState(cfg.sessionSecret, returnUrl),
    allow_signup: "false",
  });
  return c.redirect("https://github.com/login/oauth/authorize?" + params.toString());
});

app.get("/auth/callback", async (c) => {
  const cfg = c.get("cfg");
  const code = c.req.query("code") || "";
  const state = c.req.query("state") || "";
  const st = await readState(cfg.sessionSecret, state);
  if (!st) throw new HttpError(400, "bad state");
  const { token } = await gh.exchangeCode(cfg, code);
  const u = await gh.user(token);
  const value = await c.get("sessions").create({
    login: u.login,
    avatarUrl: u.avatar_url,
    name: u.name || u.login,
    url: u.html_url ?? null,
  });
  // Cookie still set for same-site/desktop callers; the token in the redirect fragment below
  // is the cross-platform delivery, since mobile browsers block the cross-site cookie.
  setCookie(c, "gc_session", value, {
    httpOnly: true,
    sameSite: cfg.cookieCrossSite ? "None" : "Lax",
    secure: cfg.cookieCrossSite,
    maxAge: cfg.sessionTtl,
    path: "/",
  });
  // Redirect back to the blog page, handing the widget the session token in the URL fragment.
  // The return URL's origin is validated against the allow-list so the callback can't be used
  // as an open redirect to an arbitrary site.
  let ret = st.r || "";
  try {
    const o = new URL(ret).origin;
    const ok =
      cfg.wildcard || DEV_ORIGINS.includes(o) || c.get("tenants").origins().has(o) || cfg.allowedOrigins.includes(o);
    if (!ok) ret = "";
  } catch {
    ret = "";
  }
  if (!ret) ret = cfg.siteUrl || "/";
  return c.redirect(ret.split("#")[0] + "#gc_token=" + encodeURIComponent(value));
});

app.post("/auth/logout", (c) => {
  const cfg = c.get("cfg");
  // Clear with the SAME attributes the cookie was set with. A SameSite=None; Secure cookie
  // (cross-site) is only cleared by a deletion cookie that also carries them; a plain
  // delete is treated as SameSite=Lax and ignored cross-site, so sign-out would do nothing.
  deleteCookie(c, "gc_session", {
    path: "/",
    sameSite: cfg.cookieCrossSite ? "None" : "Lax",
    secure: cfg.cookieCrossSite,
  });
  return c.json({ ok: true });
});

// --- comments ----------------------------------------------------------------
app.get("/api/discussions", async (c) => {
  const first = Math.max(1, Math.min(parseInt(c.req.query("first") || "20", 10) || 20, 100));
  const viewer = await currentViewer(c);
  limit(c, rl.read, viewer);
  return c.json(
    (await c.get("store").getDiscussion({
      tenantId: requestTenant(c),
      term: c.req.query("term") ?? null,
      after: c.req.query("after") ?? null,
      first,
      viewer,
    })) as object,
  );
});

app.post("/api/comments", async (c) => {
  const body = await c.req.json<{
    body: string;
    term?: string;
    title?: string;
    subtitle?: string;
    url?: string;
    reply_to_id?: string;
  }>();
  const viewer = await currentViewer(c);
  limit(c, rl.post, viewer);
  return c.json(
    (await c.get("store").addComment({
      tenantId: requestTenant(c),
      term: body.term ?? null,
      title: body.title ?? null,
      subtitle: body.subtitle ?? null,
      url: body.url ?? null,
      body: body.body,
      replyToId: body.reply_to_id ?? null,
      viewer,
    })) as object,
  );
});

app.post("/api/comments/edit", async (c) => {
  const body = await c.req.json<{ comment_id: string; body: string }>();
  const viewer = await currentViewer(c);
  limit(c, rl.edit, viewer);
  return c.json((await c.get("store").editComment({ commentId: body.comment_id, body: body.body, viewer })) as object);
});

app.post("/api/comments/delete", async (c) => {
  const body = await c.req.json<{ comment_id: string }>();
  const viewer = await currentViewer(c);
  limit(c, rl.del, viewer);
  return c.json((await c.get("store").deleteComment({ commentId: body.comment_id, viewer })) as object);
});

app.post("/api/comments/hide", async (c) => {
  const body = await c.req.json<{ comment_id: string; hide?: boolean; reason?: string }>();
  const viewer = await currentViewer(c);
  limit(c, rl.hide, viewer);
  return c.json(
    (await c.get("store").setHidden({
      commentId: body.comment_id,
      hide: body.hide ?? true,
      reason: body.reason ?? null,
      viewer,
    })) as object,
  );
});

app.post("/api/preview", async (c) => {
  const body = await c.req.json<{ text?: string }>();
  const viewer = await currentViewer(c);
  if (!viewer) throw new HttpError(401, "sign in required");
  limit(c, rl.preview, viewer);
  const html = await c.get("store").preview({ text: body.text || "", viewer });
  return c.json({ html });
});

// --- reactions ---------------------------------------------------------------
app.post("/api/react", async (c) => {
  const body = await c.req.json<{ comment_id: string; content: string; on?: boolean }>();
  const viewer = await currentViewer(c);
  limit(c, rl.react, viewer);
  return c.json(
    (await c.get("store").react({
      commentId: body.comment_id,
      content: body.content,
      on: body.on ?? true,
      viewer,
    })) as object,
  );
});

// --- error mapping (FastAPI's HTTPException shape: {"detail": ...}) ----------
app.onError((err, c) => {
  if (err instanceof HttpError) {
    const res = c.json({ detail: err.message }, err.status as 400);
    if (err.headers) for (const [k, v] of Object.entries(err.headers)) res.headers.set(k, v);
    return res;
  }
  console.error("unhandled error:", err);
  return c.json({ detail: "internal error" }, 500);
});

export default app;
