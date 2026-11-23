"""ui_svc: консоль полигона — читатель/вызыватель, ноль расчётов и ноль оркестрации.

Статическая страница + тонкие /api/*: свод frozen, запуск run_campaign/probe
(единственные источники прогона — те же функции, что у CLI), прогресс, прокси
на metrics/filter. Инвариант: никакой математики и никакого управления
сервисами здесь нет — только вызов launcher/metrics/filter.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from lab.svc_client import Svc
from launcher import (
    ATTACK_URL,
    FILTER_URL,
    METRICS_URL,
    SHOP_URL,
    TRAFFIC_URL,
    run_campaign,
)
from launcher import probe as launcher_probe
from launcher.axes import GUARD_VOLUME, axis_universe, resolve_campaign
from launcher.campaign import _runs_dir

STATIC = Path(__file__).resolve().parent / "static"

app = FastAPI(title="ui_svc", version="0.1.0")

_STATE: dict[str, Any] = {"status": "idle"}
_STATE_LOCK = threading.Lock()


def _svc(url: str, timeout: float = 30.0) -> Svc:
    return Svc(url, timeout=timeout)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/health")
def health() -> dict:
    return {"service": "ui_svc", "status": "ok"}


@app.get("/api/meta")
def meta() -> dict:
    services = {
        "shop": SHOP_URL,
        "traffic": TRAFFIC_URL,
        "attack": ATTACK_URL,
        "filter": FILTER_URL,
        "metrics": METRICS_URL,
    }
    health = {}
    for name, url in services.items():
        try:
            _svc(url, timeout=2.0).get("/health")
            health[name] = "ok"
        except Exception:  # noqa: BLE001 — ping failure is a status, not a bug
            health[name] = "down"
    return {
        "configs": axis_universe("configs"),
        "styles": axis_universe("styles"),
        "tactics": axis_universe("tactics"),
        "agent_models": axis_universe("agent_models"),
        "attacker_models": axis_universe("attacker_models"),
        "guard": GUARD_VOLUME,
        "health": health,
    }


class VolumeIn(BaseModel):
    spec: dict[str, Any]


@app.post("/api/volume")
def volume(body: VolumeIn) -> dict:
    try:
        camp = resolve_campaign(body.spec)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    cells, episodes = camp.volume()
    return {"cells": cells, "episodes": episodes}


@app.post("/api/run")
def run(body: dict[str, Any]) -> dict:
    with _STATE_LOCK:
        if _STATE.get("status") == "running":
            raise HTTPException(409, "прогон уже выполняется")
        try:
            camp = resolve_campaign(body)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None
        _, episodes_total = camp.volume()
        if episodes_total > GUARD_VOLUME and not body.get("confirm"):
            return {"needs_confirm": True, "episodes": episodes_total, "guard": GUARD_VOLUME}
        _STATE.clear()
        _STATE.update({"status": "running", "started": time.time()})

        def progress(p: dict[str, Any]) -> None:
            with _STATE_LOCK:
                _STATE.update(p)

        def worker() -> None:
            try:
                manifest = run_campaign(body, progress=progress)
                with _STATE_LOCK:
                    _STATE.update({"status": "done", "manifest": manifest})
            except SystemExit as exc:
                with _STATE_LOCK:
                    _STATE.update({"status": "error", "error": str(exc)})
            except Exception as exc:  # noqa: BLE001 — any failure ends up in the UI
                with _STATE_LOCK:
                    _STATE.update({"status": "error", "error": repr(exc)})

        threading.Thread(target=worker, daemon=True).start()
        return {"started": True, "episodes": episodes_total}


@app.get("/api/run/status")
def run_status() -> dict:
    with _STATE_LOCK:
        return dict(_STATE)


@app.post("/api/compute")
def compute(body: dict[str, Any]) -> dict:
    return _svc(METRICS_URL).post(
        "/compute",
        {
            "config_name": body.get("config_name"),
            "include_probe": bool(body.get("include_probe")),
        },
    )


@app.get("/api/metrics/{config_name}")
def metrics(config_name: str) -> dict:
    return _svc(METRICS_URL).get(f"/metrics/{config_name}")


@app.get("/api/text/{episode_id}")
def text(episode_id: str) -> dict:
    return _svc(FILTER_URL).get(f"/text/{episode_id}")


@app.get("/api/episodes")
def episodes_list() -> dict:
    return _svc(FILTER_URL).get("/episodes")


@app.get("/api/metric-configs")
def metric_configs() -> dict:
    return _svc(METRICS_URL).get("/configs")


@app.get("/api/chain")
def chain() -> dict:
    return _svc(FILTER_URL).get("/chain/verify")


@app.get("/api/runs")
def runs() -> dict:
    items = []
    runs_dir = _runs_dir()
    if runs_dir.exists():
        for mf in sorted(runs_dir.glob("*/manifest.json"), reverse=True):
            try:
                items.append(json.loads(mf.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                continue
    return {"runs": items}


class ProbeIn(BaseModel):
    config: str
    tactic: str
    budget: int = 8
    seed: int | None = None
    style: str | None = None
    agent_model: str | None = None
    attacker_model: str | None = None


@app.post("/api/probe")
def probe_run(body: ProbeIn) -> dict:
    try:
        return launcher_probe(
            {
                "config": body.config,
                "tactic": body.tactic,
                "budget": body.budget,
                "seed": body.seed,
                "style": body.style,
                "agent_model": body.agent_model,
                "attacker_model": body.attacker_model,
            }
        )
    except SystemExit as exc:
        raise HTTPException(400, str(exc)) from None


app.mount("/static", StaticFiles(directory=STATIC), name="static")
