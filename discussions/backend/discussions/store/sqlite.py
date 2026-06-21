"""SqliteStore — the comment backend we run.

The whole commenting system (comments, replies, edits, hides, reactions) lives in
our SQLite (see db.py). OAuth is used only to learn who the reader is (login, name,
avatar, profile URL); Markdown is rendered locally (md.render) so there is no GitHub
dependency at all for the comment path.

Threads are keyed by `term` (the post slug). Authorization is ours: a comment's
author may edit/delete it, an admin (blog owner) may delete/hide any.
"""
import secrets
import time
from typing import Optional

from fastapi import HTTPException

from .. import db, md
from ..config import MAX_BODY
from .base import Store, check_reaction, iso, require_viewer, HIDE_REASONS


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


class SqliteStore(Store):
    name = "sqlite"

    def _can_moderate(self, row: dict, viewer: dict) -> bool:
        """A moderator of the comment's own tenant may hide/delete it. Authorization is
        per-tenant (db.tenant_is_admin against row["tenant_id"]), not the viewer's
        self-reported request-tenant flag — so an admin of one blog can't moderate
        another's comments."""
        return db.tenant_is_admin(row["tenant_id"], viewer.get("login"))

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
        # Fetch one extra to know whether another page follows.
        top = await db.comments_top(tenant_id, term, first + 1, offset)
        has_next = len(top) > first
        top = top[:first]
        reply_map = await db.comments_replies([t["id"] for t in top])

        ids = []
        for t in top:
            ids.append(t["id"])
            ids.extend(r["id"] for r in reply_map.get(t["id"], []))
        rmap = await db.reactions_for(ids, viewer_login)

        comments = []
        for t in top:
            reps = [_to_dict(r, rmap) for r in reply_map.get(t["id"], [])]
            comments.append(_to_dict(t, rmap, replies=reps, reply_total=len(reps)))

        total = await db.comments_top_count(tenant_id, term)
        disc = await db.discussion_get(tenant_id, term)
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
            parent = await db.comment_get(reply_to_id)
            if not parent or parent["term"] != term or parent["tenant_id"] != tenant_id:
                raise HTTPException(status_code=404, detail="parent comment not found")
            if parent["parent_id"]:
                # A thread is one level deep: a reply to a reply attaches to the
                # top-level comment, matching GitHub.
                reply_to_id = parent["parent_id"]
        # Create the discussion (the per-page container) on its first comment, fixing
        # the page metadata; later comments leave it untouched.
        await db.discussion_upsert(tenant_id, term, title, subtitle, url)
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
        await db.comment_insert(row)
        return _to_dict(row, {}, replies=([] if not reply_to_id else None))

    async def edit_comment(self, *, comment_id, body, viewer):
        viewer = require_viewer(viewer)
        if not (body or "").strip():
            raise HTTPException(status_code=400, detail="empty comment")
        if len(body) > MAX_BODY:
            raise HTTPException(status_code=413, detail="comment too long")
        row = await db.comment_get(comment_id)
        if not row:
            raise HTTPException(status_code=404, detail="comment not found")
        if not (row["author_login"] == viewer["login"] or self._can_moderate(row, viewer)):
            raise HTTPException(status_code=403, detail="not allowed to edit this comment")
        html = md.render(body)
        now = time.time()
        await db.comment_update_body(comment_id, body, html, now)
        row.update(body_md=body, body_html=html, updated_at=now)
        return _to_dict(row, {})

    async def delete_comment(self, *, comment_id, viewer):
        viewer = require_viewer(viewer)
        row = await db.comment_get(comment_id)
        if not row:
            raise HTTPException(status_code=404, detail="comment not found")
        if not (row["author_login"] == viewer["login"] or self._can_moderate(row, viewer)):
            raise HTTPException(status_code=403, detail="not allowed to delete this comment")
        deleted_ids = await db.comment_delete(comment_id)
        for cid in deleted_ids:
            await db.reactions_purge(cid)
        return {"ok": True, "id": comment_id}

    async def set_hidden(self, *, comment_id, hide, reason, viewer):
        viewer = require_viewer(viewer)
        row = await db.comment_get(comment_id)
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
        await db.comment_set_hidden(comment_id, hide, norm, hidden_at)
        row.update(is_minimized=hide, min_reason=norm, hidden_at=hidden_at)
        return _to_dict(row, {})

    async def react(self, *, comment_id, content, on, viewer):
        viewer = require_viewer(viewer)
        content = check_reaction(content)
        row = await db.comment_get(comment_id)
        if not row:
            raise HTTPException(status_code=404, detail="comment not found")
        if row["is_minimized"]:
            # Hidden comments are read-only (the UI hides the picker; enforce it here too).
            raise HTTPException(status_code=403, detail="cannot react to a hidden comment")
        await db.react_toggle(comment_id, viewer["login"], content, on, row["tenant_id"])
        groups = (await db.reactions_for([comment_id], viewer["login"])).get(comment_id, [])
        return {"comment_id": comment_id, "reactions": groups}
