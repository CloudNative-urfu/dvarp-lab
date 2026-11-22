"""Storage of filter_svc: raw DB, JSONL hash chain and per-episode cassettes."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from lab.cassette import Cassette
from lab.chain import Chain
from lab.db import make_engine

from .models import Base, Turn

LLM_CALLS_KEY = "llm_calls"
DETECT_SIGNALS = ("flag", "block")


class Settings:
    """Env-driven settings, read lazily so tests can point them at a temp dir."""

    @property
    def db_url(self) -> str:
        return os.environ.get("LAB_RAW_DB_URL", "sqlite:///./runs/raw.db")

    @property
    def raw_dir(self) -> Path:
        return Path(os.environ.get("LAB_RAW_DIR", "./runs/raw"))

    @property
    def chain_path(self) -> Path:
        return self.raw_dir / "chain.jsonl"

    def cassette_path(self, episode_id: str) -> Path:
        return self.raw_dir / f"cassette_{episode_id}.jsonl"


settings = Settings()
_engines: dict[str, Engine] = {}


def engine(url: str | None = None) -> Engine:
    url = url or settings.db_url
    if url not in _engines:
        if url.startswith("sqlite:///") and ":memory:" not in url:
            Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
        _engines[url] = make_engine(url)
    return _engines[url]


def init_db() -> None:
    Base.metadata.create_all(engine())


def chain() -> Chain:
    settings.raw_dir.mkdir(parents=True, exist_ok=True)
    return Chain(settings.chain_path)


def record_turn(
    session: Session,
    *,
    episode_id: str,
    config_name: str,
    channel: str,
    turn: int,
    text: str,
    model_spec: dict,
    raw: dict,
    snapshot: dict | None,
) -> str:
    """Persist a turn, append a chain line, write cassette lines for raw.llm_calls."""
    record_id = uuid.uuid4().hex
    row = Turn(
        record_id=record_id,
        episode_id=episode_id,
        config_name=config_name,
        channel=channel,
        turn=turn,
        text=text,
        model_spec=model_spec,
        raw=raw,
        snapshot=snapshot,
    )
    session.add(row)
    session.flush()
    chain().append(
        {
            "record_id": record_id,
            "episode_id": episode_id,
            "config_name": config_name,
            "channel": channel,
            "turn": turn,
            "text": text,
            "model_spec": model_spec,
            "raw": raw,
            "snapshot": snapshot,
        }
    )
    cassette = Cassette(settings.cassette_path(episode_id))
    for call in raw.get(LLM_CALLS_KEY) or []:
        cassette.record(
            call.get("role", "model"),
            call.get("model", model_spec),
            call.get("request"),
            call.get("response"),
        )
    return record_id


def episode_turns(session: Session, episode_id: str) -> list[Turn]:
    return (
        session.query(Turn).filter(Turn.episode_id == episode_id).order_by(Turn.turn, Turn.id).all()
    )


def all_turns(session: Session) -> list[Turn]:
    return session.query(Turn).order_by(Turn.id).all()
