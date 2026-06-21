"""Active comment store, selected by DISCUSSIONS_BACKEND.

Two server backends:
- sqlite — the self-hosted system of record (comments/replies/edits/hides/reactions
  in our SQLite; OAuth used only to learn who the reader is). The fallback when an
  organization's OAuth-App access restrictions block a reader token from writing to
  Discussions.
- github — real GitHub Discussions via GraphQL: the reader's own token writes (so
  authorship is authentic, like giscus), a server token reads for signed-out
  visitors. For a repo you own (no OAuth-App restriction). See github.py.

The `Store` interface (base.py) keeps them swappable. The app holds one Store
instance (init/closed by the lifespan); routes call get_store().
"""
from ..config import DISCUSSIONS_BACKEND
from .base import Store

_store = None


def build_store() -> Store:
    if DISCUSSIONS_BACKEND == "sqlite":
        from .sqlite import SqliteStore
        return SqliteStore()
    if DISCUSSIONS_BACKEND == "github":
        from .github import GitHubStore
        return GitHubStore()
    raise RuntimeError(
        f"unknown DISCUSSIONS_BACKEND={DISCUSSIONS_BACKEND!r}; expected 'sqlite' or 'github'"
    )


def get_store() -> Store:
    global _store
    if _store is None:
        _store = build_store()
    return _store
