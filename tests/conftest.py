"""Shared fixtures: per-test env pointing both services at temp files."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def lab_env(tmp_path, monkeypatch):
    raw_db = tmp_path / "raw.db"
    metrics_db = tmp_path / "metrics.db"
    raw_dir = tmp_path / "raw"
    monkeypatch.setenv("LAB_RAW_DB_URL", f"sqlite:///{raw_db}")
    monkeypatch.setenv("LAB_METRICS_DB_URL", f"sqlite:///{metrics_db}")
    monkeypatch.setenv("LAB_RAW_DIR", str(raw_dir))
    return SimpleNamespace(raw_db=raw_db, metrics_db=metrics_db, raw_dir=raw_dir)


@pytest.fixture
async def filter_client(lab_env):
    from services.filter.app import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://filter") as c:
        yield c


@pytest.fixture
async def metrics_client(lab_env):
    from services.metrics.app import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://metrics") as c:
        yield c


MODEL_SPEC = {"name": "qwen2.5-7b", "role": "support_agent", "params_b": 7.0, "revision": "r1"}


def make_raw(*, llm_calls=(), guard_signals=None, verdict=None, config_name="g0", extra=None):
    raw = {
        "config_name": config_name,
        "llm_calls": list(llm_calls),
        "guard_signals": guard_signals or {},
        "internal_notes": "shop-private",
    }
    if verdict:
        raw["verdict"] = verdict
    if extra:
        raw.update(extra)
    return raw


async def record_turn(
    client,
    *,
    episode_id,
    turn=0,
    channel="legal",
    text="t",
    config_name="g0",
    model_spec=None,
    raw=None,
    snapshot=None,
):
    body = {
        "episode_id": episode_id,
        "channel": channel,
        "turn": turn,
        "text": text,
        "model_spec": model_spec or MODEL_SPEC,
        "config_name": config_name,
        "raw": raw or make_raw(config_name=config_name),
        "snapshot": snapshot,
    }
    r = await client.post("/record", json=body)
    r.raise_for_status()
    return r.json()


async def seed_episode(
    client,
    *,
    config_name,
    episode_id,
    channel,
    violation=False,
    outcome="refused",
    task_status="completed",
    escalated=False,
    detected=False,
    model_spec=None,
    turns=1,
    events=(),
):
    verdict = {
        "violation": violation,
        "outcome": outcome,
        "task_status": task_status,
        "escalated": escalated,
    }
    signals = {"flag": 1} if detected else {}
    raw = make_raw(
        config_name=config_name,
        guard_signals=signals,
        verdict=verdict,
        extra={"events": list(events)} if events else None,
    )
    for t in range(turns):
        await record_turn(
            client,
            episode_id=episode_id,
            turn=t,
            channel=channel,
            text=f"{channel} turn {t}",
            config_name=config_name,
            model_spec=model_spec,
            raw=raw,
        )
