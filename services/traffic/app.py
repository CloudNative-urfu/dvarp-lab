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
            shop=Svc(SHOP_URL),
            db_url=resolve_db_url(),
            filter_svc=Svc(FILTER_URL),
            customer_base_url=os.environ.get("LAB_CUSTOMER_LLM_BASE_URL"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


def resolve_db_url() -> str:
    """Строка подключения к БД магазина: env LAB_SHOP_DB_URL или shop_svc GET /db/readonly."""
    url = os.environ.get("LAB_SHOP_DB_URL")
    if url:
        return url
    return Svc(SHOP_URL).get("/db/readonly")["url"]
