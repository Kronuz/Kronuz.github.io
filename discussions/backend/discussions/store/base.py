"""The comment store interface + shared helpers.

A *store* is the backend that holds the commenting system. Two implement this:

- SqliteStore  — what we run. The full system (comments, replies, edits, hides,
  reactions) lives in our SQLite; OAuth is used only to learn who the reader is.
- GitHubStore  — the ideal: if the org ever approves the OAuth App (repo /
  public_repo), the reader's own token writes to GitHub Discussions, so comments
  are truly authored by them and reactions are native — no local store, no stamp.

Both return the same comment shape (below) so the routes and the widget don't care
which one is active. Stores raise fastapi.HTTPException for auth/validation errors,
matching the rest of the backend.

Comment shape:
    {
      "id": str, "url": str|None, "createdAt": iso, "updatedAt": iso|None,
      "bodyHTML": str, "bodyMarkdown": str, "authorLogin": str|None,
      "author": {"login", "name", "url", "avatarUrl"},
      "isMinimized": bool, "minimizedReason": str|None, "hiddenAt": str|None,
      "reactions": [{"content", "count", "viewerHasReacted"}],
      "replies": [ ...comment... ],   # top-level only
      "replyCount": int, "repliesHaveMore": bool,   # top-level only
    }

get_discussion returns:
    {"discussion": {"totalCount": int, "title": str|None, "url": str|None},
     "pageInfo": {"hasNextPage": bool, "endCursor": str|None},
     "comments": [ ...top-level comments... ]}
"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException

# GitHub's eight reaction emoji (the ReactionContent enum); we whitelist these.
REACTION_CONTENT = {
    "THUMBS_UP", "THUMBS_DOWN", "LAUGH", "HOORAY", "CONFUSED", "HEART", "ROCKET", "EYES",
}

# GitHub's ReportedContentClassifiers — the valid reasons for hiding a comment.
HIDE_REASONS = {"OUTDATED", "OFF_TOPIC", "RESOLVED", "DUPLICATE", "SPAM", "ABUSE"}


def iso(epoch: Optional[float]) -> Optional[str]:
    """Epoch seconds -> ISO-8601 UTC (what the widget's `new Date(...)` expects)."""
    if epoch is None:
        return None
    return datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def require_viewer(viewer: Optional[dict]) -> dict:
    if not viewer:
        raise HTTPException(status_code=401, detail="sign in required")
    return viewer


def check_reaction(content: str) -> str:
    content = (content or "").upper()
    if content not in REACTION_CONTENT:
        raise HTTPException(status_code=400, detail="invalid reaction")
    return content


class Store:
    """Interface every comment backend implements. `viewer` is None (signed out) or
    {login, name, avatarUrl, url, token, tenant_id, is_admin} for the current reader,
    where `tenant_id`/`is_admin` describe the tenant whose blog the request came from.
    Term-keyed methods take the resolved `tenant_id` explicitly (a term is unique only
    within a tenant); id-keyed methods derive the tenant from the comment row and
    authorize moderation against *that* tenant, so `viewer.is_admin` (request-tenant
    scoped) is not used for authorization."""

    name = "base"

    async def init(self) -> None:
        pass

    async def close(self) -> None:
        pass

    async def get_discussion(self, *, tenant_id: str, term: Optional[str],
                            after: Optional[str], first: int, viewer: Optional[dict]) -> dict:
        raise NotImplementedError

    async def add_comment(self, *, tenant_id: str, term: Optional[str],
                          title: Optional[str], subtitle: Optional[str], url: Optional[str],
                          body: str, reply_to_id: Optional[str], viewer: Optional[dict]) -> dict:
        raise NotImplementedError

    async def edit_comment(self, *, comment_id: str, body: str, viewer: Optional[dict]) -> dict:
        raise NotImplementedError

    async def delete_comment(self, *, comment_id: str, viewer: Optional[dict]) -> dict:
        raise NotImplementedError

    async def set_hidden(self, *, comment_id: str, hide: bool, reason: Optional[str],
                         viewer: Optional[dict]) -> dict:
        raise NotImplementedError

    async def react(self, *, comment_id: str, content: str, on: bool,
                    viewer: Optional[dict]) -> dict:
        raise NotImplementedError
