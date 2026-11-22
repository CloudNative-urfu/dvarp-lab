"""attack_svc: симуляция атаки (корпус заморожен, тактика из плана прогона, только текст)."""

from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from lab.svc_client import Svc

from .episode import run_attack

SHOP_URL = os.environ.get("LAB_SHOP_URL", "http://127.0.0.1:9411")
FILTER_URL = os.environ.get("LAB_FILTER_URL", "http://127.0.0.1:9414")

app = FastAPI(title="attack_svc", version="0.1.0")

# Флаги для launcher: сигналы начала/конца атаки.
_state: dict[str, Any] = {"started": False, "stopped": False}


class RunEpisode(BaseModel):
    episode_id: str
    config_name: str
    attacker_model: dict[str, Any]
    tactic: str
    budget: int
    seed: int
    style: str | None = None
    run_id: str | None = None


@app.get("/health")
def health() -> dict:
    return {"service": "attack_svc", "status": "ok"}


@app.get("/state")
def state() -> dict:
    return dict(_state)


@app.post("/start")
def start() -> dict:
    _state.update(started=True, stopped=False)
    return {"ok": True, "started": True}


@app.post("/stop")
def stop() -> dict:
    _state.update(stopped=True, started=False)
    return {"ok": True, "stopped": True}


@app.post("/run-episode")
def run(body: RunEpisode) -> dict:
    try:
        return run_attack(
            body.episode_id,
            body.config_name,
            body.attacker_model,
            body.tactic,
            body.budget,
            body.seed,
            style_name=body.style,
            run_id=body.run_id,
            shop=Svc(SHOP_URL),
            filter_svc=Svc(FILTER_URL),
            attacker_base_url=os.environ.get("LAB_ATTACKER_LLM_BASE_URL"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
