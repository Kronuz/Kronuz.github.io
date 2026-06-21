"""GitHubStore — the comment store that uses real GitHub Discussions.

The ideal the SelfHostedStore stands in for: the reader's own OAuth token writes to
GitHub Discussions, so comments and reactions are *authentically* authored by them
(their avatar, their name, editable/deletable by them on GitHub, native reaction
counts) — no local store, no "via the blog" stamp. Markdown is rendered by GitHub
(`bodyHTML`), so bodies match GitHub exactly.

Auth model (the same split giscus uses):
- WRITE (post/edit/delete/hide/react): the reader's own token (`viewer["token"]`),
  so authorship is genuine. Requires `repo`/`public_repo` scope, granted at sign-in
  when DISCUSSIONS_BACKEND=github (see config.OAUTH_SCOPE).
- READ: a signed-in reader's own token (accurate `viewerHasReacted`), falling back to
  a server-side GITHUB_READ_TOKEN for signed-out visitors (GitHub's GraphQL API needs
  auth even for public data).

Why this fits a repo you own: some organizations enable OAuth-App access
restrictions that reject a reader token's `addDiscussionComment` (FORBIDDEN); where
that applies, the SelfHostedStore is the fallback. A repo you control has no such
restriction, so reader-token writes go through and authorship is genuine.

Term mapping (giscus-style): a post's `term` (slug) maps to a Discussion whose title
*is* the term, in the configured REPO + DISCUSSION_CATEGORY. The thread is created
lazily on the first comment. `tenant_id` is accepted for interface parity but unused:
the github store serves the one repo in its config (single-tenant).
"""
from typing import Optional

from fastapi import HTTPException

from .. import gh
from ..config import (DISCUSSION_CATEGORY, GITHUB_READ_TOKEN, MAX_BODY, NAME, OWNER,
                      REPO)
from .base import HIDE_REASONS, Store, check_reaction, require_viewer

# The DiscussionComment fields the widget needs, shared by every query/mutation.
_COMMENT_FIELDS = """
  id
  url
  createdAt
  lastEditedAt
  bodyHTML
  body
  isMinimized
  minimizedReason
  author { login url avatarUrl ... on User { name } }
  reactionGroups { content viewerHasReacted reactors { totalCount } }
"""

_REPO_Q = """
query($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    id
    discussionCategories(first: 50) { nodes { id name slug } }
  }
}
"""

_FIND_Q = """
query($q: String!) {
  search(query: $q, type: DISCUSSION, first: 10) {
    nodes { ... on Discussion { id number title url } }
  }
}
"""

_THREAD_Q = """
query($id: ID!, $first: Int!, $after: String, $replies: Int!) {
  node(id: $id) {
    ... on Discussion {
      title
      url
      comments(first: $first, after: $after) {
        totalCount
        pageInfo { hasNextPage endCursor }
        nodes {
          %(c)s
          replies(first: $replies) {
            totalCount
            pageInfo { hasNextPage }
            nodes { %(c)s }
          }
        }
      }
    }
  }
}
""" % {"c": _COMMENT_FIELDS}

_CREATE_DISCUSSION_M = """
mutation($repoId: ID!, $catId: ID!, $title: String!, $body: String!) {
  createDiscussion(input: {repositoryId: $repoId, categoryId: $catId, title: $title, body: $body}) {
    discussion { id number url }
  }
}
"""

_ADD_M = """
mutation($discId: ID!, $body: String!, $replyToId: ID) {
  addDiscussionComment(input: {discussionId: $discId, body: $body, replyToId: $replyToId}) {
    comment { %(c)s }
  }
}
""" % {"c": _COMMENT_FIELDS}

_EDIT_M = """
mutation($id: ID!, $body: String!) {
  updateDiscussionComment(input: {commentId: $id, body: $body}) {
    comment { %(c)s }
  }
}
""" % {"c": _COMMENT_FIELDS}

_DELETE_M = """
mutation($id: ID!) {
  deleteDiscussionComment(input: {id: $id}) { clientMutationId }
}
"""

_MINIMIZE_M = """
mutation($id: ID!, $classifier: ReportedContentClassifiers!) {
  minimizeComment(input: {subjectId: $id, classifier: $classifier}) {
    minimizedComment { ... on DiscussionComment { %(c)s } }
  }
}
""" % {"c": _COMMENT_FIELDS}

_UNMINIMIZE_M = """
mutation($id: ID!) {
  unminimizeComment(input: {subjectId: $id}) {
    unminimizedComment { ... on DiscussionComment { %(c)s } }
  }
}
""" % {"c": _COMMENT_FIELDS}

_REACT_M = """
mutation($id: ID!, $content: ReactionContent!) {
  %(op)s(input: {subjectId: $id, content: $content}) {
    subject { ... on DiscussionComment {
      reactionGroups { content viewerHasReacted reactors { totalCount } }
    } }
  }
}
"""


def _norm_reason(reason: Optional[str]) -> Optional[str]:
    """GitHub's minimizedReason display string -> our uppercase classifier enum."""
    if not reason:
        return None
    norm = reason.strip().upper().replace("-", "_").replace(" ", "_")
    return norm if norm in HIDE_REASONS else norm


def _map_reactions(groups: list) -> list:
    """ReactionGroup[] -> the widget's [{content, count, viewerHasReacted}] (non-empty
    groups only, so the UI shows existing reactions and the picker adds new ones)."""
    out = []
    for g in groups or []:
        count = ((g.get("reactors") or {}).get("totalCount")) or 0
        if count > 0:
            out.append({
                "content": g["content"],
                "count": count,
                "viewerHasReacted": bool(g.get("viewerHasReacted")),
            })
    return out


def _map_comment(node: dict, replies=None, reply_total=None, replies_more=False) -> dict:
    """A GitHub DiscussionComment node -> the store's comment shape (see base.py).
    GitHub's timestamps are already ISO-8601 and its bodyHTML is already rendered."""
    author = node.get("author") or {}
    d = {
        "id": node["id"],
        "url": node.get("url"),
        "createdAt": node.get("createdAt"),
        "updatedAt": node.get("lastEditedAt"),
        "bodyHTML": node.get("bodyHTML") or "",
        "bodyMarkdown": node.get("body") or "",
        "authorLogin": author.get("login"),
        "author": {
            "login": author.get("login"),
            "name": author.get("name") or author.get("login"),
            "url": author.get("url") or "",
            "avatarUrl": author.get("avatarUrl") or "",
        },
        "isMinimized": bool(node.get("isMinimized")),
        "minimizedReason": _norm_reason(node.get("minimizedReason")),
        # GitHub doesn't expose when a comment was minimized; the widget keys off
        # isMinimized/minimizedReason, so a precise timestamp isn't needed.
        "hiddenAt": None,
        "reactions": _map_reactions(node.get("reactionGroups")),
    }
    if replies is not None:
        d["replies"] = replies
        d["replyCount"] = reply_total if reply_total is not None else len(replies)
        d["repliesHaveMore"] = replies_more
    return d


class GitHubStore(Store):
    name = "github"

    def __init__(self) -> None:
        self._repo: Optional[dict] = None          # {id, categoryId}
        self._terms: dict = {}                      # term -> {id, number, url}

    def _read_token(self, viewer: Optional[dict]) -> str:
        """Token for a READ: the signed-in reader's own (accurate viewerHasReacted),
        else the server read token. Without either, a signed-out read can't proceed."""
        if viewer and viewer.get("token"):
            return viewer["token"]
        if GITHUB_READ_TOKEN:
            return GITHUB_READ_TOKEN
        raise HTTPException(
            status_code=503,
            detail="comments need a GITHUB_READ_TOKEN for signed-out readers",
        )

    async def _repo_ctx(self, token: str) -> dict:
        """The repo id + the target discussion category id, fetched once and cached."""
        if self._repo:
            return self._repo
        data = await gh.graphql(token, _REPO_Q, {"owner": OWNER, "name": NAME})
        repo = data.get("repository")
        if not repo:
            raise HTTPException(status_code=502, detail=f"repository {REPO} not found")
        cats = (repo.get("discussionCategories") or {}).get("nodes") or []
        if not cats:
            raise HTTPException(status_code=502, detail=f"{REPO} has no discussion categories")
        want = (DISCUSSION_CATEGORY or "").strip().lower()
        match = next((c for c in cats
                      if c["name"].lower() == want or (c.get("slug") or "").lower() == want), None)
        self._repo = {"id": repo["id"], "categoryId": (match or cats[0])["id"]}
        return self._repo

    async def _find_thread(self, token: str, term: str) -> Optional[dict]:
        """The Discussion whose title == term (cached), or None if not created yet."""
        if term in self._terms:
            return self._terms[term]
        q = f'repo:{OWNER}/{NAME} in:title "{term}"'
        data = await gh.graphql(token, _FIND_Q, {"q": q})
        for node in (data.get("search") or {}).get("nodes") or []:
            if node.get("title") == term:
                self._terms[term] = {"id": node["id"], "number": node["number"], "url": node["url"]}
                return self._terms[term]
        return None

    async def get_discussion(self, *, tenant_id, term, after, first, viewer):
        if not term:
            raise HTTPException(status_code=400, detail="term required")
        token = self._read_token(viewer)
        thread = await self._find_thread(token, term)
        if not thread:
            # No thread yet (no comments). Mirror the empty shape the widget expects.
            return {"discussion": {"totalCount": 0, "title": None, "url": None},
                    "pageInfo": {"hasNextPage": False, "endCursor": None}, "comments": []}
        data = await gh.graphql(token, _THREAD_Q, {
            "id": thread["id"], "first": first, "after": after, "replies": 100})
        disc = data.get("node") or {}
        conn = disc.get("comments") or {}
        comments = []
        for n in conn.get("nodes") or []:
            rconn = n.get("replies") or {}
            reps = [_map_comment(r) for r in rconn.get("nodes") or []]
            comments.append(_map_comment(
                n, replies=reps,
                reply_total=rconn.get("totalCount", len(reps)),
                replies_more=bool((rconn.get("pageInfo") or {}).get("hasNextPage")),
            ))
        page = conn.get("pageInfo") or {}
        return {
            "discussion": {"totalCount": conn.get("totalCount", len(comments)),
                           "title": disc.get("title"), "url": disc.get("url")},
            "pageInfo": {"hasNextPage": bool(page.get("hasNextPage")),
                         "endCursor": page.get("endCursor")},
            "comments": comments,
        }

    async def _ensure_thread(self, token: str, term: str, title, url) -> dict:
        """Find the term's Discussion or create it (giscus-style, on first comment)."""
        thread = await self._find_thread(token, term)
        if thread:
            return thread
        ctx = await self._repo_ctx(token)
        body = (f"Comments for **{title}**\n\n{url}".strip() if (title or url)
                else f"Comments for `{term}`.")
        data = await gh.graphql(token, _CREATE_DISCUSSION_M, {
            "repoId": ctx["id"], "catId": ctx["categoryId"], "title": term, "body": body})
        disc = (data.get("createDiscussion") or {}).get("discussion") or {}
        if not disc.get("id"):
            raise HTTPException(status_code=502, detail="could not create the discussion thread")
        self._terms[term] = {"id": disc["id"], "number": disc.get("number"), "url": disc.get("url")}
        return self._terms[term]

    async def add_comment(self, *, tenant_id, term, title, subtitle, url, body,
                          reply_to_id, viewer):
        viewer = require_viewer(viewer)
        if not term:
            raise HTTPException(status_code=400, detail="term required")
        if not (body or "").strip():
            raise HTTPException(status_code=400, detail="empty comment")
        if len(body) > MAX_BODY:
            raise HTTPException(status_code=413, detail="comment too long")
        token = viewer["token"]
        thread = await self._ensure_thread(token, term, title, url)
        data = await gh.graphql(token, _ADD_M, {
            "discId": thread["id"], "body": body, "replyToId": reply_to_id or None})
        node = (data.get("addDiscussionComment") or {}).get("comment")
        if not node:
            raise HTTPException(status_code=502, detail="comment was not created")
        # Top-level comments carry an (empty) replies list; a reply does not (matches sqlite).
        return _map_comment(node, replies=([] if not reply_to_id else None))

    async def edit_comment(self, *, comment_id, body, viewer):
        viewer = require_viewer(viewer)
        if not (body or "").strip():
            raise HTTPException(status_code=400, detail="empty comment")
        if len(body) > MAX_BODY:
            raise HTTPException(status_code=413, detail="comment too long")
        data = await gh.graphql(viewer["token"], _EDIT_M, {"id": comment_id, "body": body})
        node = (data.get("updateDiscussionComment") or {}).get("comment")
        if not node:
            raise HTTPException(status_code=404, detail="comment not found")
        return _map_comment(node)

    async def delete_comment(self, *, comment_id, viewer):
        viewer = require_viewer(viewer)
        await gh.graphql(viewer["token"], _DELETE_M, {"id": comment_id})
        return {"ok": True, "id": comment_id}

    async def set_hidden(self, *, comment_id, hide, reason, viewer):
        viewer = require_viewer(viewer)
        if hide:
            classifier = (reason or "OUTDATED").upper()
            if classifier not in HIDE_REASONS:
                raise HTTPException(status_code=400, detail="invalid hide reason")
            data = await gh.graphql(viewer["token"], _MINIMIZE_M,
                                    {"id": comment_id, "classifier": classifier})
            node = (data.get("minimizeComment") or {}).get("minimizedComment")
        else:
            data = await gh.graphql(viewer["token"], _UNMINIMIZE_M, {"id": comment_id})
            node = (data.get("unminimizeComment") or {}).get("unminimizedComment")
        if not node:
            raise HTTPException(status_code=404, detail="comment not found")
        return _map_comment(node)

    async def react(self, *, comment_id, content, on, viewer):
        viewer = require_viewer(viewer)
        content = check_reaction(content)
        op = "addReaction" if on else "removeReaction"
        data = await gh.graphql(viewer["token"], _REACT_M % {"op": op},
                                {"id": comment_id, "content": content})
        subject = (data.get(op) or {}).get("subject") or {}
        return {"comment_id": comment_id, "reactions": _map_reactions(subject.get("reactionGroups"))}

    async def preview(self, *, text, viewer):
        require_viewer(viewer)
        if len(text or "") > MAX_BODY:
            raise HTTPException(status_code=413, detail="comment too long")
        if not (text or "").strip():
            return ""
        # GitHub's own renderer, so the preview matches the posted comment exactly. Use
        # the reader's token when signed in, falling back to the server read token.
        token = (viewer or {}).get("token") or GITHUB_READ_TOKEN
        return await gh.markdown(token, text, context=REPO)
