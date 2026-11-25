"""Raw DB schema of filter_svc: one row per turn (public text + private raw payload)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


class Turn(Base):
    """One turn of one episode: text is public, raw/snapshot stay behind the barrier."""

    __tablename__ = "turns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    record_id: Mapped[str] = mapped_column(String(64), unique=True)
    episode_id: Mapped[str] = mapped_column(String(128), index=True)
    config_name: Mapped[str] = mapped_column(String(128), index=True)
    channel: Mapped[str] = mapped_column(String(16))
    turn: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    model_spec: Mapped[dict] = mapped_column(JSON)
    raw: Mapped[dict] = mapped_column(JSON)
    snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class EpisodeFinal(Base):
    """Final row of one episode (#10): verdict and guard-signal counters, apart from the trace.

    Written by shop_svc on episode end via POST /finalize; snapshot restores never touch it.
    Metrics read it any time; formulas change without rerunning episodes.
    """

    __tablename__ = "episode_finals"
    # one row per (episode_id, config, model): legal ids repeat across configs by design
    __table_args__ = (UniqueConstraint("episode_id", "config_name", "model_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    episode_id: Mapped[str] = mapped_column(String(128), index=True)
    config_name: Mapped[str] = mapped_column(String(128), index=True)
    model_key: Mapped[str] = mapped_column(Text)
    channel: Mapped[str] = mapped_column(String(16))
    model_spec: Mapped[dict] = mapped_column(JSON)
    verdict: Mapped[dict] = mapped_column(JSON)
    guard_signals: Mapped[dict] = mapped_column(JSON)
    leak: Mapped[bool] = mapped_column(Boolean, default=False)
    leak_turns: Mapped[list] = mapped_column(JSON, default=list)
    run_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    remote_llm: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
