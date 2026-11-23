"""filter_svc (port 9414): response/raw separation; only text leaves the service.

Raw payloads, state snapshots and model-call cassettes are stored here behind the barrier
(raw DB + JSONL hash chain). Metrics read the raw DB read-only, never the text endpoints.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from lab.chain import GENESIS

from . import store
from .models import Turn


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Сырая БД существует с момента старта сервиса (append-only, не пересоздаётся)."""
    store.init_db()
    yield


app = FastAPI(title="filter_svc", version="0.1.0", lifespan=lifespan)

CHANNELS = ("legal", "attack")


class RecordRequest(BaseModel):
    episode_id: str
    channel: str
    turn: int
    text: str
    model_spec: dict[str, Any]
    raw: dict[str, Any]
    snapshot: dict[str, Any] | None = None
    # Not in docs/api.md; shop_svc pins the config per episode, metrics aggregate by it.
    config_name: str | None = None


@app.get("/health")
def health() -> dict:
    return {"service": "filter_svc", "status": "ok"}


@app.post("/record")
def record(body: RecordRequest) -> dict:
    if body.channel not in CHANNELS:
        raise HTTPException(400, f"channel must be one of {CHANNELS}")
    config_name = body.config_name or body.raw.get("config_name")
    if not config_name:
        raise HTTPException(400, "config_name missing (top-level or raw.config_name)")
    store.init_db()
    with Session(store.engine()) as session:
        record_id = store.record_turn(
            session,
            episode_id=body.episode_id,
            config_name=config_name,
            channel=body.channel,
            turn=body.turn,
            text=body.text,
            model_spec=body.model_spec,
            raw=body.raw,
            snapshot=body.snapshot,
        )
        session.commit()
    return {"record_id": record_id}


@app.get("/text/{episode_id}")
def text(episode_id: str) -> dict:
    """Barrier: public part only — turn number, channel and text, nothing of the raw."""
    store.init_db()
    with Session(store.engine()) as session:
        rows = store.episode_turns(session, episode_id)
    return {
        "episode_id": episode_id,
        "turns": [{"turn": r.turn, "channel": r.channel, "text": r.text} for r in rows],
    }


@app.get("/episodes")
def episodes() -> dict:
    """Список эпизодов сырой БД: id, конфиг, каналы, число ходов (без текстов)."""
    store.init_db()
    with Session(store.engine()) as session:
        rows = (
            session.query(Turn.episode_id, Turn.config_name, Turn.channel).order_by(Turn.id).all()
        )
    seen: dict[str, dict] = {}
    for episode_id, config_name, channel in rows:
        item = seen.setdefault(
            episode_id, {"episode_id": episode_id, "config_name": config_name, "channels": []}
        )
        if channel not in item["channels"]:
            item["channels"].append(channel)
        item["n_turns"] = item.get("n_turns", 0) + 1
    return {"episodes": list(seen.values())}


@app.get("/chain/verify")
def chain_verify() -> dict:
    defects = store.chain().verify() if store.settings.chain_path.exists() else []
    return {"defects": defects, "genesis": GENESIS}
