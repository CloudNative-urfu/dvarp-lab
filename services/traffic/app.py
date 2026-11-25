"""traffic_svc: симуляция безопасного трафика (стили общения, правдивые возвраты из БД)."""

from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from lab.svc_client import Svc

from .episode import run_episode

SHOP_URL = os.environ.get("LAB_SHOP_URL", "http://127.0.0.1:9411")
FILTER_URL = os.environ.get("LAB_FILTER_URL", "http://127.0.0.1:9414")

app = FastAPI(title="traffic_svc", version="0.1.0")


class RunEpisode(BaseModel):
    episode_id: str
    config_name: str
    agent_model: dict[str, Any]
    style: str
    seed: int
    run_id: str | None = None
    remote_llm: bool = False


@app.get("/health")
def health() -> dict:
    return {"service": "traffic_svc", "status": "ok"}


@app.post("/run-episode")
def run(body: RunEpisode) -> dict:
    try:
        return run_episode(
            body.episode_id,
            body.config_name,
            body.agent_model,
            body.style,
            body.seed,
            run_id=body.run_id,
            remote_llm=body.remote_llm,
            shop=Svc(SHOP_URL),
            db_url=resolve_db_url(),
            filter_svc=Svc(FILTER_URL),
            customer_base_url=os.environ.get("LAB_CUSTOMER_LLM_BASE_URL"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


def resolve_db_url() -> str:
    """Строка подключения к БД магазина — только из env LAB_SHOP_DB_URL (секрет конфигурации,
    по HTTP не ходит; issue #17)."""
    url = os.environ.get("LAB_SHOP_DB_URL")
    if not url:
        raise RuntimeError(
            "LAB_SHOP_DB_URL не задан: traffic_svc читает БД магазина только по строке из env"
        )
    return url
