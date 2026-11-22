"""Raw DB schema of filter_svc: one row per turn (public text + private raw payload)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Integer, String, Text
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
