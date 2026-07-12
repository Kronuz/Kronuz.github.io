/**
 * D1Database driver — the Cloudflare D1 backing store for the self-hosted comments.
 *
 * A port of discussions/backend/discussions/db/{base,sqlite}.py. D1 *is* SQLite, so the
 * schema (migrations/0001_init.sql) and queries carry over almost verbatim; the aiosqlite
 * connection + cursor calls become D1's prepared-statement API
 * (`.prepare(sql).bind(...).all()/.first()/.run()`, `.batch([...])` for atomic groups).
 *
 * Differences from the Python driver, all because this is a fresh deployment:
 *   - no runtime PRAGMA/ALTER migrations (the schema ships final in migrations/),
 *   - no `sessions` methods (sessions are stateless cookies; see sessions.ts).
 *
 * Time columns are epoch seconds (matching the Python backend's time.time()).
 */
import type { D1Database } from "@cloudflare/workers-types";

const now = (): number => Date.now() / 1000;

const COMMENT_COLS =
  "id, term, parent_id, author_login, author_name, author_avatar, author_url, " +
  "body_md, body_html, created_at, updated_at, is_minimized, min_reason, hidden_at, tenant_id";

export interface CommentRow {
  id: string;
  term: string;
  parent_id: string | null;
  author_login: string;
  author_name: string | null;
  author_avatar: string | null;
  author_url: string | null;
  body_md: string;
  body_html: string;
  created_at: number;
  updated_at: number | null;
  is_minimized: boolean;
  min_reason: string | null;
  hidden_at: number | null;
  tenant_id: string;
}

export interface TenantRow {
  id: string;
  origin: string | null;
  repo: string | null;
  repo_url: string | null;
  strip_suffix: string;
  giphy_key: string;
  created_at?: number;
  admins?: string[];
}

export interface DiscussionRow {
  term: string;
  title: string | null;
  subtitle: string | null;
  url: string | null;
  createdAt: number;
}

export interface ReactionGroup {
  content: string;
  count: number;
  viewerHasReacted: boolean;
}

function toCommentRow(r: Record<string, unknown>): CommentRow {
  return {
    id: r.id as string,
    term: r.term as string,
    parent_id: (r.parent_id as string | null) ?? null,
    author_login: r.author_login as string,
    author_name: (r.author_name as string | null) ?? null,
    author_avatar: (r.author_avatar as string | null) ?? null,
    author_url: (r.author_url as string | null) ?? null,
    body_md: r.body_md as string,
    body_html: r.body_html as string,
    created_at: r.created_at as number,
    updated_at: (r.updated_at as number | null) ?? null,
    is_minimized: Boolean(r.is_minimized),
    min_reason: (r.min_reason as string | null) ?? null,
    hidden_at: (r.hidden_at as number | null) ?? null,
    tenant_id: (r.tenant_id as string) ?? "",
  };
}

export class Database {
  constructor(private db: D1Database) {}

  // --- tenants ---------------------------------------------------------------
  async tenantSeedDefault(
    tenantId: string,
    origin: string,
    repo: string,
    repoUrl: string,
    admins: string[],
  ): Promise<void> {
    const stmts = [
      this.db
        .prepare("INSERT OR IGNORE INTO tenants(id, origin, repo, repo_url, created_at) VALUES(?,?,?,?,?)")
        .bind(tenantId, origin, repo, repoUrl, now()),
      ...admins.map((login) =>
        this.db.prepare("INSERT OR IGNORE INTO tenant_admins(tenant_id, login) VALUES(?,?)").bind(tenantId, login),
      ),
    ];
    await this.db.batch(stmts);
  }

  async tenantLoadAll(): Promise<{ tenants: TenantRow[]; admins: Record<string, Set<string>> }> {
    const t = await this.db
      .prepare("SELECT id, origin, repo, repo_url, strip_suffix, giphy_key FROM tenants")
      .all<Record<string, unknown>>();
    const tenants: TenantRow[] = (t.results || []).map((r) => ({
      id: r.id as string,
      origin: (r.origin as string | null) ?? null,
      repo: (r.repo as string | null) ?? null,
      repo_url: (r.repo_url as string | null) ?? null,
      strip_suffix: (r.strip_suffix as string) ?? "",
      giphy_key: (r.giphy_key as string) ?? "",
    }));
    const a = await this.db.prepare("SELECT tenant_id, login FROM tenant_admins").all<Record<string, unknown>>();
    const admins: Record<string, Set<string>> = {};
    for (const r of a.results || []) {
      const tid = r.tenant_id as string;
      (admins[tid] ??= new Set()).add(r.login as string);
    }
    return { tenants, admins };
  }

  async tenantGet(tenantId: string): Promise<TenantRow | null> {
    const r = await this.db
      .prepare(
        "SELECT id, origin, repo, repo_url, created_at, strip_suffix, giphy_key FROM tenants WHERE id=?",
      )
      .bind(tenantId)
      .first<Record<string, unknown>>();
    if (!r) return null;
    return {
      id: r.id as string,
      origin: (r.origin as string | null) ?? null,
      repo: (r.repo as string | null) ?? null,
      repo_url: (r.repo_url as string | null) ?? null,
      created_at: r.created_at as number,
      strip_suffix: (r.strip_suffix as string) ?? "",
      giphy_key: (r.giphy_key as string) ?? "",
    };
  }

  async tenantAdmins(tenantId: string): Promise<string[]> {
    const a = await this.db
      .prepare("SELECT login FROM tenant_admins WHERE tenant_id=?")
      .bind(tenantId)
      .all<Record<string, unknown>>();
    return (a.results || []).map((r) => r.login as string);
  }

  async tenantCreate(
    tenantId: string,
    origin: string,
    repo = "",
    repoUrl = "",
    admins: string[] = [],
    stripSuffix = "",
    giphyKey = "",
  ): Promise<void> {
    const stmts = [
      this.db
        .prepare(
          "INSERT INTO tenants(id, origin, repo, repo_url, created_at, strip_suffix, giphy_key) " +
            "VALUES(?,?,?,?,?,?,?) " +
            "ON CONFLICT(id) DO UPDATE SET origin=excluded.origin, repo=excluded.repo, " +
            "repo_url=excluded.repo_url, strip_suffix=excluded.strip_suffix, giphy_key=excluded.giphy_key",
        )
        .bind(tenantId, origin, repo, repoUrl, now(), stripSuffix, giphyKey),
      ...admins.map((login) =>
        this.db.prepare("INSERT OR IGNORE INTO tenant_admins(tenant_id, login) VALUES(?,?)").bind(tenantId, login),
      ),
    ];
    await this.db.batch(stmts);
  }

  async tenantDelete(tenantId: string, purge = false): Promise<void> {
    const stmts = [
      this.db.prepare("DELETE FROM tenant_admins WHERE tenant_id=?").bind(tenantId),
      this.db.prepare("DELETE FROM tenants WHERE id=?").bind(tenantId),
    ];
    if (purge) {
      stmts.push(
        this.db.prepare("DELETE FROM reactions WHERE tenant_id=?").bind(tenantId),
        this.db.prepare("DELETE FROM comments WHERE tenant_id=?").bind(tenantId),
        this.db.prepare("DELETE FROM discussions WHERE tenant_id=?").bind(tenantId),
      );
    }
    await this.db.batch(stmts);
  }

  async tenantAdminAdd(tenantId: string, login: string): Promise<void> {
    await this.db
      .prepare("INSERT OR IGNORE INTO tenant_admins(tenant_id, login) VALUES(?,?)")
      .bind(tenantId, login)
      .run();
  }

  async tenantAdminRemove(tenantId: string, login: string): Promise<void> {
    await this.db
      .prepare("DELETE FROM tenant_admins WHERE tenant_id=? AND login=?")
      .bind(tenantId, login)
      .run();
  }

  async tenantList(): Promise<TenantRow[]> {
    const t = await this.db
      .prepare(
        "SELECT id, origin, repo, repo_url, created_at, strip_suffix, giphy_key FROM tenants ORDER BY created_at",
      )
      .all<Record<string, unknown>>();
    const tenants: TenantRow[] = (t.results || []).map((r) => ({
      id: r.id as string,
      origin: (r.origin as string | null) ?? null,
      repo: (r.repo as string | null) ?? null,
      repo_url: (r.repo_url as string | null) ?? null,
      created_at: r.created_at as number,
      strip_suffix: (r.strip_suffix as string) ?? "",
      giphy_key: (r.giphy_key as string) ?? "",
      admins: [],
    }));
    const a = await this.db.prepare("SELECT tenant_id, login FROM tenant_admins").all<Record<string, unknown>>();
    const byT: Record<string, string[]> = {};
    for (const r of a.results || []) (byT[r.tenant_id as string] ??= []).push(r.login as string);
    for (const t2 of tenants) t2.admins = (byT[t2.id] || []).sort();
    return tenants;
  }

  // --- discussions -----------------------------------------------------------
  async discussionGet(tenantId: string, term: string): Promise<DiscussionRow | null> {
    const r = await this.db
      .prepare("SELECT term, title, subtitle, url, created_at FROM discussions WHERE tenant_id=? AND term=?")
      .bind(tenantId, term)
      .first<Record<string, unknown>>();
    if (!r) return null;
    return {
      term: r.term as string,
      title: (r.title as string | null) ?? null,
      subtitle: (r.subtitle as string | null) ?? null,
      url: (r.url as string | null) ?? null,
      createdAt: r.created_at as number,
    };
  }

  async discussionUpsert(
    tenantId: string,
    term: string,
    title: string | null,
    subtitle: string | null,
    url: string | null,
  ): Promise<void> {
    await this.db
      .prepare(
        "INSERT OR IGNORE INTO discussions(tenant_id, term, title, subtitle, url, created_at) VALUES(?,?,?,?,?,?)",
      )
      .bind(tenantId, term, title, subtitle, url, now())
      .run();
  }

  // --- comments --------------------------------------------------------------
  async commentInsert(c: CommentRow): Promise<void> {
    await this.db
      .prepare(`INSERT INTO comments(${COMMENT_COLS}) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)`)
      .bind(
        c.id,
        c.term,
        c.parent_id,
        c.author_login,
        c.author_name,
        c.author_avatar,
        c.author_url,
        c.body_md,
        c.body_html,
        c.created_at,
        c.updated_at,
        c.is_minimized ? 1 : 0,
        c.min_reason,
        c.hidden_at,
        c.tenant_id,
      )
      .run();
  }

  async commentGet(commentId: string): Promise<CommentRow | null> {
    const r = await this.db
      .prepare(`SELECT ${COMMENT_COLS} FROM comments WHERE id=?`)
      .bind(commentId)
      .first<Record<string, unknown>>();
    return r ? toCommentRow(r) : null;
  }

  async commentUpdateBody(commentId: string, bodyMd: string, bodyHtml: string, updatedAt: number): Promise<void> {
    await this.db
      .prepare("UPDATE comments SET body_md=?, body_html=?, updated_at=? WHERE id=?")
      .bind(bodyMd, bodyHtml, updatedAt, commentId)
      .run();
  }

  async commentSetHidden(
    commentId: string,
    hide: boolean,
    reason: string | null,
    hiddenAt: number | null,
  ): Promise<void> {
    await this.db
      .prepare("UPDATE comments SET is_minimized=?, min_reason=?, hidden_at=? WHERE id=?")
      .bind(hide ? 1 : 0, hide ? reason : null, hide ? hiddenAt : null, commentId)
      .run();
  }

  async commentDelete(commentId: string): Promise<string[]> {
    const kids = await this.db
      .prepare("SELECT id FROM comments WHERE parent_id=?")
      .bind(commentId)
      .all<Record<string, unknown>>();
    const ids = [commentId, ...(kids.results || []).map((r) => r.id as string)];
    const qs = ids.map(() => "?").join(",");
    await this.db.prepare(`DELETE FROM comments WHERE id IN (${qs})`).bind(...ids).run();
    return ids;
  }

  async commentsTop(tenantId: string, term: string, limit: number, offset: number): Promise<CommentRow[]> {
    const r = await this.db
      .prepare(
        `SELECT ${COMMENT_COLS} FROM comments ` +
          "WHERE tenant_id=? AND term=? AND parent_id IS NULL " +
          "ORDER BY created_at ASC, id ASC LIMIT ? OFFSET ?",
      )
      .bind(tenantId, term, limit, offset)
      .all<Record<string, unknown>>();
    return (r.results || []).map(toCommentRow);
  }

  async commentsTopCount(tenantId: string, term: string): Promise<number> {
    const r = await this.db
      .prepare("SELECT COUNT(*) AS n FROM comments WHERE tenant_id=? AND term=? AND parent_id IS NULL")
      .bind(tenantId, term)
      .first<Record<string, unknown>>();
    return (r?.n as number) ?? 0;
  }

  async commentsReplies(parentIds: string[]): Promise<Record<string, CommentRow[]>> {
    const ids = parentIds.filter(Boolean);
    if (!ids.length) return {};
    const qs = ids.map(() => "?").join(",");
    const r = await this.db
      .prepare(
        `SELECT ${COMMENT_COLS} FROM comments WHERE parent_id IN (${qs}) ORDER BY created_at ASC, id ASC`,
      )
      .bind(...ids)
      .all<Record<string, unknown>>();
    const out: Record<string, CommentRow[]> = {};
    for (const raw of r.results || []) {
      const row = toCommentRow(raw);
      (out[row.parent_id as string] ??= []).push(row);
    }
    return out;
  }

  // --- reactions -------------------------------------------------------------
  async reactionsFor(commentIds: string[], viewer: string | null): Promise<Record<string, ReactionGroup[]>> {
    const ids = [...new Set(commentIds.filter(Boolean))];
    if (!ids.length) return {};
    const qs = ids.map(() => "?").join(",");
    const r = await this.db
      .prepare(
        "SELECT comment_id, content, COUNT(*) AS c, " +
          "SUM(CASE WHEN login=? THEN 1 ELSE 0 END) AS mine " +
          `FROM reactions WHERE comment_id IN (${qs}) GROUP BY comment_id, content`,
      )
      .bind(viewer || "", ...ids)
      .all<Record<string, unknown>>();
    const out: Record<string, ReactionGroup[]> = {};
    for (const row of r.results || []) {
      const cid = row.comment_id as string;
      (out[cid] ??= []).push({
        content: row.content as string,
        count: row.c as number,
        viewerHasReacted: Boolean(row.mine),
      });
    }
    return out;
  }

  async reactToggle(commentId: string, login: string, content: string, on: boolean, tenantId: string): Promise<void> {
    if (on) {
      await this.db
        .prepare(
          "INSERT OR IGNORE INTO reactions(comment_id, login, content, created_at, tenant_id) VALUES(?,?,?,?,?)",
        )
        .bind(commentId, login, content, now(), tenantId)
        .run();
    } else {
      await this.db
        .prepare("DELETE FROM reactions WHERE comment_id=? AND login=? AND content=?")
        .bind(commentId, login, content)
        .run();
    }
  }

  async reactionsPurge(commentId: string): Promise<void> {
    await this.db.prepare("DELETE FROM reactions WHERE comment_id=?").bind(commentId).run();
  }
}
