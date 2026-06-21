"""A tiny in-process sliding-window rate limiter — no external deps, no extra infra.

The backend is a single uvicorn process, so an in-memory limiter is enough to stop an
"angry coworker" from flooding comments/reactions/edits. Each limiter keeps, per key, a
deque of recent hit timestamps and rejects (HTTP 429) once the window is full. Keys are
the signed-in login when available (so a flood follows the person, not their IP) and
fall back to the client IP for anonymous endpoints.
"""
import time
from collections import defaultdict, deque
from typing import Optional

from fastapi import HTTPException, Request


class RateLimit:
    def __init__(self, max_events: int, per_seconds: float):
        self.max = max_events
        self.per = per_seconds
        self._hits: dict = defaultdict(deque)
        self._since_sweep = 0

    def check(self, key: str) -> None:
        """Record a hit for `key`; raise 429 (with Retry-After) if over the limit."""
        now = time.monotonic()
        cutoff = now - self.per
        q = self._hits[key]
        while q and q[0] <= cutoff:
            q.popleft()
        if len(q) >= self.max:
            retry = max(1, int(q[0] + self.per - now) + 1)
            raise HTTPException(status_code=429, detail="Too many requests; slow down.",
                                headers={"Retry-After": str(retry)})
        q.append(now)
        self._maybe_sweep(now)

    def _maybe_sweep(self, now: float) -> None:
        # Opportunistic memory bound: every ~500 hits, drop buckets that fully aged out
        # so the key space can't grow without limit.
        self._since_sweep += 1
        if self._since_sweep < 500:
            return
        self._since_sweep = 0
        cutoff = now - self.per
        for k in list(self._hits):
            q = self._hits[k]
            while q and q[0] <= cutoff:
                q.popleft()
            if not q:
                del self._hits[k]


def client_key(request: Request, viewer: Optional[dict]) -> str:
    """Rate-limit key: the signed-in login if we have one, else the client IP."""
    if viewer and viewer.get("login"):
        return "u:" + viewer["login"]
    client = request.client
    return "ip:" + (client.host if client else "unknown")
