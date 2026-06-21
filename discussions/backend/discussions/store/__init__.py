"""Active comment store, selected by the STORE knob (config.STORE).

Two stores:
- selfhosted — the self-hosted system of record: comments/replies/edits/hides/reactions
  live in the active Database driver (SQLite today; MySQL/Postgres are added drivers,
  see db/). OAuth is used only to learn who the reader is; Markdown is rendered locally.
- github — real GitHub Discussions via GraphQL: the reader's own token writes (so
  authorship is authentic, like giscus), a server read token reads for signed-out
  visitors. Single-tenant (serves the one repo in its config). See github.py.

The `Store` interface (base.py) keeps them swappable; adding a new store is one new
`store/<name>.py` plus a branch in build_store(). The chosen store is owned by the
runtime module (runtime.py), which builds and holds it; routes call runtime.store().
"""
from ..config import STORE
from .base import Store


def build_store(db, tenants) -> Store:
    """Construct the active store. selfhosted needs the Database (its system of record)
    and the tenant registry (per-tenant moderation); github needs neither (GitHub owns
    both storage and authorization)."""
    if STORE == "github":
        from .github import GitHubStore
        return GitHubStore()
    if STORE == "selfhosted":
        from .selfhosted import SelfHostedStore
        return SelfHostedStore(db, tenants)
    raise RuntimeError(
        f"unknown STORE={STORE!r}; expected 'selfhosted' or 'github'"
    )
