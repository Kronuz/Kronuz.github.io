"""SelfHostedStore — the comment store whose system of record is a Database.

The full commenting system (comments, replies, edits, hides, reactions) lives in the
active Database driver (SQLite today; MySQL/Postgres are added drivers, see db/). OAuth
is used only to learn who the reader is; Markdown is rendered locally (md.render, the
cmark-gfm renderer GitHub uses) so bodies match GitHub with no GitHub dependency.

Threads are keyed by `term` (the post slug) within a tenant. Authorization is ours: a
comment's author may edit/delete it; a moderator of the comment's tenant may delete/hide
any (checked against the injected tenant registry).
"""
import secrets
import time

from fastapi import HTTPException

from .. import md
from ..config import MAX_BODY
from .base import HIDE_REASONS, Store, check_reaction, iso, require_viewer


def _to_dict(row: dict, reactions: dict, replies=None, reply_total=None) -> dict:
    d = {
        "id": row["id"],
        # No GitHub URL in this store; link to the comment's anchor on the page.
        "url": "#" + row["id"],
        "createdAt": iso(row["created_at"]),
        "updatedAt": iso(row["updated_at"]),
        "bodyHTML": row["body_html"],
        "bodyMarkdown": row["body_md"],
        "authorLogin": row["author_login"],
        "author": {
            "login": row["author_login"],
            "name": row["author_name"] or row["author_login"],
            "url": row["author_url"] or "",
            "avatarUrl": row["author_avatar"] or "",
        },
        "isMinimized": row["is_minimized"],
        "minimizedReason": row["min_reason"],
        "hiddenAt": iso(row.get("hidden_at")),
        "reactions": reactions.get(row["id"], []),
    }
    if replies is not None:
        d["replies"] = replies
        d["replyCount"] = reply_total if reply_total is not None else len(replies)
        d["repliesHaveMore"] = False  # we return every reply, so never "more on GitHub"
    return d


class SelfHostedStore(Store):
    name = "selfhosted"

    def __init__(self, db, tenants) -> None:
        self.db = db
        self.tenants = tenants

    def _can_moderate(self, row: dict, viewer: dict) -> bool:
        """A moderator of the comment's OWN tenant may hide/delete it (per-tenant, so an
        admin of one blog can't moderate another's comments)."""
        return self.tenants.is_admin(row["tenant_id"], viewer.get("login"))

    async def get_discussion(self, *, tenant_id, term, after, first, viewer):
        if not term:
            raise HTTPException(status_code=400, detail="term required")
        viewer_login = viewer["login"] if viewer else None
        offset = 0
        if after:
            try:
                offset = max(0, int(after))
            except ValueError:
                offset = 0
        top = await self.db.comments_top(tenant_id, term, first + 1, offset)
        has_next = len(top) > first
        top = top[:first]
        reply_map = await self.db.comments_replies([t["id"] for t in top])

        ids = []
        for t in top:
            ids.append(t["id"])
            ids.extend(r["id"] for r in reply_map.get(t["id"], []))
        rmap = await self.db.reactions_for(ids, viewer_login)

        comments = []
        for t in top:
            reps = [_to_dict(r, rmap) for r in reply_map.get(t["id"], [])]
            comments.append(_to_dict(t, rmap, replies=reps, reply_total=len(reps)))

        total = await self.db.comments_top_count(tenant_id, term)
        disc = await self.db.discussion_get(tenant_id, term)
        return {
            "discussion": {
                "totalCount": total,
                "title": disc["title"] if disc else None,
                "url": disc["url"] if disc else None,
            },
            "pageInfo": {"hasNextPage": has_next,
                         "endCursor": str(offset + first) if has_next else None},
            "comments": comments,
        }

    async def add_comment(self, *, tenant_id, term, title, subtitle, url, body,
                          reply_to_id, viewer):
        viewer = require_viewer(viewer)
        if not term:
            raise HTTPException(status_code=400, detail="term required")
        if not (body or "").strip():
            raise HTTPException(status_code=400, detail="empty comment")
        if len(body) > MAX_BODY:
            raise HTTPException(status_code=413, detail="comment too long")
        if reply_to_id:
            parent = await self.db.comment_get(reply_to_id)
            if not parent or parent["term"] != term or parent["tenant_id"] != tenant_id:
                raise HTTPException(status_code=404, detail="parent comment not found")
            if parent["parent_id"]:
                # A thread is one level deep: a reply to a reply attaches to the
                # top-level comment, matching GitHub.
                reply_to_id = parent["parent_id"]
        await self.db.discussion_upsert(tenant_id, term, title, subtitle, url)
        html = md.render(body)
        now = time.time()
        row = {
            "id": "c_" + secrets.token_hex(8),
            "term": term,
            "parent_id": reply_to_id,
            "author_login": viewer["login"],
            "author_name": viewer.get("name"),
            "author_avatar": viewer.get("avatarUrl"),
            "author_url": viewer.get("url"),
            "body_md": body,
            "body_html": html,
            "created_at": now,
            "updated_at": None,
            "is_minimized": False,
            "min_reason": None,
            "tenant_id": tenant_id,
        }
        await self.db.comment_insert(row)
        return _to_dict(row, {}, replies=([] if not reply_to_id else None))

    async def edit_comment(self, *, comment_id, body, viewer):
        viewer = require_viewer(viewer)
        if not (body or "").strip():
            raise HTTPException(status_code=400, detail="empty comment")
        if len(body) > MAX_BODY:
            raise HTTPException(status_code=413, detail="comment too long")
        row = await self.db.comment_get(comment_id)
        if not row:
            raise HTTPException(status_code=404, detail="comment not found")
        if not (row["author_login"] == viewer["login"] or self._can_moderate(row, viewer)):
            raise HTTPException(status_code=403, detail="not allowed to edit this comment")
        html = md.render(body)
        now = time.time()
        await self.db.comment_update_body(comment_id, body, html, now)
        row.update(body_md=body, body_html=html, updated_at=now)
        return _to_dict(row, {})

    async def delete_comment(self, *, comment_id, viewer):
        viewer = require_viewer(viewer)
        row = await self.db.comment_get(comment_id)
        if not row:
            raise HTTPException(status_code=404, detail="comment not found")
        if not (row["author_login"] == viewer["login"] or self._can_moderate(row, viewer)):
            raise HTTPException(status_code=403, detail="not allowed to delete this comment")
        deleted_ids = await self.db.comment_delete(comment_id)
        for cid in deleted_ids:
            await self.db.reactions_purge(cid)
        return {"ok": True, "id": comment_id}

    async def set_hidden(self, *, comment_id, hide, reason, viewer):
        viewer = require_viewer(viewer)
        row = await self.db.comment_get(comment_id)
        if not row:
            raise HTTPException(status_code=404, detail="comment not found")
        if not self._can_moderate(row, viewer):
            raise HTTPException(status_code=403, detail="moderators only")
        norm = None
        if hide:
            norm = (reason or "OUTDATED").upper()
            if norm not in HIDE_REASONS:
                raise HTTPException(status_code=400, detail="invalid hide reason")
        hidden_at = time.time() if hide else None
        await self.db.comment_set_hidden(comment_id, hide, norm, hidden_at)
        row.update(is_minimized=hide, min_reason=norm, hidden_at=hidden_at)
        return _to_dict(row, {})

    async def react(self, *, comment_id, content, on, viewer):
        viewer = require_viewer(viewer)
        content = check_reaction(content)
        row = await self.db.comment_get(comment_id)
        if not row:
            raise HTTPException(status_code=404, detail="comment not found")
        if row["is_minimized"]:
            raise HTTPException(status_code=403, detail="cannot react to a hidden comment")
        await self.db.react_toggle(comment_id, viewer["login"], content, on, row["tenant_id"])
        groups = (await self.db.reactions_for([comment_id], viewer["login"])).get(comment_id, [])
        return {"comment_id": comment_id, "reactions": groups}

    async def preview(self, *, text, viewer):
        require_viewer(viewer)
        if len(text or "") > MAX_BODY:
            raise HTTPException(status_code=413, detail="comment too long")
        if not (text or "").strip():
            return ""
        return md.render(text)
