"""Reaction toggle route — thin wrapper over the active store (see store/)."""
from fastapi import APIRouter, Request
from pydantic import BaseModel

from . import runtime
from .auth import current_viewer
from .ratelimit import RateLimit, client_key

router = APIRouter()

_rl_react = RateLimit(60, 60)  # per signed-in login (else IP), 60s window


class ReactionReq(BaseModel):
    comment_id: str       # the comment the reaction is on
    content: str          # one of GitHub's ReactionContent values
    on: bool = True        # True = add the reaction, False = remove it


@router.post("/api/react")
async def react(req: ReactionReq, request: Request) -> dict:
    viewer = await current_viewer(request)
    _rl_react.check(client_key(request, viewer))
    return await runtime.store().react(comment_id=req.comment_id, content=req.content,
                                       on=req.on, viewer=viewer)
