"""Own DB of metrics_svc: metric_results (config × model_spec × mode × metric)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class MetricRow(Base):
    """One stored metric: value is a JSON-encoded scalar (number, string or bool)."""

    __tablename__ = "metric_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    config_name: Mapped[str] = mapped_column(String(128), index=True)
    model_spec: Mapped[str] = mapped_column(Text)  # canonical JSON, pinned at /record time
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default="local")
    metric: Mapped[str] = mapped_column(String(128))
    value: Mapped[str] = mapped_column(Text)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
