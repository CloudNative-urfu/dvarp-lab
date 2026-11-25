"""filter_svc (port 9414): response/raw separation; only text leaves the service.

Raw payloads, state snapshots and model-call cassettes are stored here behind the barrier
(raw DB + JSONL hash chain). Metrics read the raw DB read-only, never the text endpoints.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from lab.chain import GENESIS

from . import store
from .models import EpisodeFinal, Turn


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
    # Idempotency key: a retried delivery with a known record_id is not appended twice.
    record_id: str | None = None


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
        if body.record_id and store.has_record(session, body.record_id):
            return {"record_id": body.record_id, "duplicate": True}
        record_id = store.record_turn(
            session,
            record_id=body.record_id,
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


class FinalizeRequest(BaseModel):
    episode_id: str
    config_name: str
    channel: str
    model_spec: dict[str, Any]
    verdict: dict[str, Any]
    guard_signals: dict[str, int] = {}
    leak: bool = False  # system prompt canary in an agent reply (separate from outcomes)
    leak_turns: list[int] = []
    run_id: str | None = None
    seed: int | None = None
    remote_llm: bool = False


@app.post("/finalize")
def finalize(body: FinalizeRequest) -> dict:
    """One final row per episode; a repeat (delivery retry) replaces it with the same data."""
    if body.channel not in CHANNELS:
        raise HTTPException(400, f"channel must be one of {CHANNELS}")
    store.init_db()
    key = {
        "episode_id": body.episode_id,
        "config_name": body.config_name,
        "model_key": json.dumps(body.model_spec, sort_keys=True, ensure_ascii=False),
    }
    with Session(store.engine()) as session:
        row = session.query(EpisodeFinal).filter_by(**key).one_or_none()
        if row is None:
            row = EpisodeFinal(**key)
            session.add(row)
        for k, v in body.model_dump().items():
            setattr(row, k, v)
        session.commit()
    return {"ok": True}


@app.get("/finals/{episode_id}")
def final(episode_id: str) -> dict:
    """Structural outcome of a finished episode for the launcher manifest (no trace, no raw)."""
    store.init_db()
    with Session(store.engine()) as session:
        row = (
            session.query(EpisodeFinal)
            .filter_by(episode_id=episode_id)
            .order_by(EpisodeFinal.id.desc())
            .first()
        )
    if row is None:
        raise HTTPException(404, f"no final row for {episode_id}")
    v = row.verdict or {}
    return {
        "episode_id": episode_id,
        "outcome": v.get("outcome") or v.get("task_status"),
        "violation": bool(v.get("violation")),
        "task_status": v.get("task_status"),
        "escalated": bool(v.get("escalated")),
        "leak": bool(row.leak),
    }


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


@app.get("/dialog/{episode_id}")
def dialog(episode_id: str) -> dict:
    """Barrier: the episode as a dialog of channel texts only (customer → agent per turn).

    Built from the shop channel messages (what the customer sent and what the agent
    answered); one line per (turn, author, text), so duplicate deliveries collapse.
    Nothing else of the raw (guard decisions, tools, llm calls) leaves.
    """
    store.init_db()
    with Session(store.engine()) as session:
        rows = store.episode_turns(session, episode_id)
    authors = {"to_defender": "customer", "to_attacker": "agent"}
    lines: list[dict] = []
    seen: set[tuple] = set()
    for r in rows:
        for e in (r.raw or {}).get("events") or []:
            data = e.get("data") or {}
            if e.get("kind") != "message" or data.get("direction") not in authors:
                continue
            line = {
                "turn": data.get("turn", r.turn),
                "channel": r.channel,
                "author": authors[data["direction"]],
                "text": data.get("text", ""),
            }
            key = (line["turn"], line["author"], line["text"])
            if key not in seen:
                seen.add(key)
                lines.append(line)
    if not lines:  # нет записей shop: только ответы агента из записей симуляций
        for r in rows:
            key = (r.turn, "agent", r.text)
            if key not in seen:
                seen.add(key)
                lines.append(
                    {"turn": r.turn, "channel": r.channel, "author": "agent", "text": r.text}
                )
    return {"episode_id": episode_id, "lines": lines}


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
