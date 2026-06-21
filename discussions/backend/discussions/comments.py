"""Comment routes — thin wrappers over the active store (see store/).

The store (SQLite today) owns all logic and authorization; these handlers just parse
the request, resolve the viewer, and delegate. Markdown preview renders locally
(md.render) so the composer's Preview matches a posted comment exactly.
"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from . import md
from .auth import current_viewer, request_tenant
from .config import MAX_BODY
from .ratelimit import RateLimit, client_key
from .store import get_store

router = APIRouter()

# Sliding-window limits, keyed by signed-in login (else client IP), 60s windows.
# Generous enough for normal use; tight enough to stop a flood.
_rl_read = RateLimit(120, 60)
_rl_post = RateLimit(6, 60)
_rl_edit = RateLimit(30, 60)
_rl_delete = RateLimit(30, 60)
_rl_hide = RateLimit(60, 60)
_rl_preview = RateLimit(30, 60)


@router.get("/api/discussions")
async def get_discussion(request: Request, term: Optional[str] = None,
                         after: Optional[str] = None, first: int = 20) -> dict:
    first = max(1, min(first, 100))
    viewer = await current_viewer(request)
    _rl_read.check(client_key(request, viewer))
    return await get_store().get_discussion(
        tenant_id=request_tenant(request), term=term, after=after, first=first, viewer=viewer)


class NewComment(BaseModel):
    body: str
    term: Optional[str] = None         # page slug (the discussion key)
    title: Optional[str] = None        # page metadata, stored with the discussion
    subtitle: Optional[str] = None     # page metadata, stored with the discussion
    url: Optional[str] = None          # page metadata, stored with the discussion
    reply_to_id: Optional[str] = None  # set to a top-level comment id to post a reply


@router.post("/api/comments")
async def post_comment(new: NewComment, request: Request) -> dict:
    viewer = await current_viewer(request)
    _rl_post.check(client_key(request, viewer))
    return await get_store().add_comment(
        tenant_id=request_tenant(request), term=new.term, title=new.title,
        subtitle=new.subtitle, url=new.url, body=new.body,
        reply_to_id=new.reply_to_id, viewer=viewer)


class EditReq(BaseModel):
    comment_id: str
    body: str


@router.post("/api/comments/edit")
async def edit_comment(req: EditReq, request: Request) -> dict:
    viewer = await current_viewer(request)
    _rl_edit.check(client_key(request, viewer))
    return await get_store().edit_comment(comment_id=req.comment_id, body=req.body, viewer=viewer)


class CommentRef(BaseModel):
    comment_id: str


@router.post("/api/comments/delete")
async def delete_comment(req: CommentRef, request: Request) -> dict:
    viewer = await current_viewer(request)
    _rl_delete.check(client_key(request, viewer))
    return await get_store().delete_comment(comment_id=req.comment_id, viewer=viewer)


class HideReq(BaseModel):
    comment_id: str
    hide: bool = True
    reason: Optional[str] = None  # a ReportedContentClassifiers value (when hiding)


@router.post("/api/comments/hide")
async def hide_comment(req: HideReq, request: Request) -> dict:
    viewer = await current_viewer(request)
    _rl_hide.check(client_key(request, viewer))
    return await get_store().set_hidden(comment_id=req.comment_id, hide=req.hide,
                                        reason=req.reason, viewer=viewer)


class PreviewReq(BaseModel):
    text: str = ""


@router.post("/api/preview")
async def preview(req: PreviewReq, request: Request) -> dict:
    # Preview is only useful while composing (which needs sign-in to post), so require a
    # viewer — that also keeps this render endpoint from being an open, unauthenticated
    # CPU sink. Rate-limited and length-capped like a real comment.
    viewer = await current_viewer(request)
    if not viewer:
        raise HTTPException(status_code=401, detail="sign in required")
    _rl_preview.check(client_key(request, viewer))
    text = req.text or ""
    if len(text) > MAX_BODY:
        raise HTTPException(status_code=413, detail="comment too long")
    if not text.strip():
        return {"html": ""}
    return {"html": md.render(text)}
