"""ui_svc: консоль полигона — читатель/вызыватель, ноль расчётов и ноль оркестрации.

Статическая страница (Vue, vendored, без билда) + тонкие /api/*: описание формы
данными (`services/ui/describe.py`), запуск run_campaign/probe (те же функции, что у
CLI), прогресс, прокси на metrics/filter. Инвариант: никакой математики и никакого
управления сервисами здесь нет — только вызов launcher/metrics/filter.
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
from services.ui.describe import describe

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
    return {**describe(), "health": health}


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


class MetricsFilter(BaseModel):
    config_name: str | None = None
    model_spec: dict[str, Any] | None = None
    include_probe: bool = False
    include_remote: bool = False


@app.post("/api/compute")
def compute(body: MetricsFilter) -> dict:
    """Расчёт с сохранением в metric_results (metrics /compute)."""
    return _svc(METRICS_URL).post("/compute", body.model_dump())


@app.post("/api/preview")
def preview(body: MetricsFilter) -> dict:
    """Одноразовый расчёт по фильтрам (metrics /preview): ничего не пишет."""
    return _svc(METRICS_URL).post("/preview", body.model_dump())


@app.get("/api/metric-models")
def metric_models() -> dict:
    return _svc(METRICS_URL).get("/models")


@app.get("/api/metrics/{config_name}")
def metrics(config_name: str) -> dict:
    """Сохранённые строки metrics, разложенные по model_spec (форма для отрисовки)."""
    m = _svc(METRICS_URL).get(f"/metrics/{config_name}")
    groups: dict[str, dict[str, Any]] = {}
    for r in m.get("results", []):
        key = json.dumps(r["model_spec"], sort_keys=True) + ":" + r.get("mode", "local")
        g = groups.setdefault(
            key,
            {
                "config_name": config_name,
                "model_spec": r["model_spec"],
                "mode": r.get("mode", "local"),
                "computed_at": r["computed_at"],
                "final": {},
            },
        )
        g["final"][r["metric"]] = r["value"]
    return {**m, "groups": list(groups.values())}


@app.get("/api/text/{episode_id}")
def text(episode_id: str) -> dict:
    return _svc(FILTER_URL).get(f"/text/{episode_id}")


@app.get("/api/dialog/{episode_id}")
def dialog(episode_id: str) -> dict:
    return _svc(FILTER_URL).get(f"/dialog/{episode_id}")


@app.get("/api/episodes")
def episodes_list() -> dict:
    return _svc(FILTER_URL).get("/episodes")


@app.get("/api/metric-configs")
def metric_configs() -> dict:
    return _svc(METRICS_URL).get("/configs")


@app.get("/api/chain")
def chain() -> dict:
    return _svc(FILTER_URL).get("/chain/verify")


def _manifests() -> list[dict[str, Any]]:
    items = []
    runs_dir = _runs_dir()
    if runs_dir.exists():
        for mf in sorted(runs_dir.glob("*/manifest.json"), reverse=True):
            try:
                items.append(json.loads(mf.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                continue
    return items


@app.get("/api/runs")
def runs() -> dict:
    """Сводка манифестов (без ячеек): run_id, remote-пин, объём."""
    return {
        "runs": [
            {
                "run_id": m.get("run_id"),
                "remote_llm": bool(m.get("remote_llm")),
                "cells": len(m.get("cells", [])),
                "episodes": sum(len(c.get("episodes", [])) for c in m.get("cells", [])),
                "axes": m.get("axes", {}),
            }
            for m in _manifests()
        ]
    }


@app.get("/api/runs/{run_id}")
def run_detail(run_id: str) -> dict:
    """Манифест прогона целиком: оси, ячейки, ссылки на эпизоды и их исходы."""
    for m in _manifests():
        if m.get("run_id") == run_id:
            return m
    raise HTTPException(404, f"прогон {run_id} не найден")


@app.get("/api/summary")
def summary() -> dict:
    """Таблица «Результаты»: сохранённые группы метрик всех конфигураций, роль agent.

    Перебор по юниверсу конфигураций, а не по metrics /configs: тот список скрывает
    remote-прогоны, а сохранённые метрики remote-кампании показывать нужно. Группа
    attacker не выводится: у неё нет легальной ноги (артефакт группировки по model_spec).
    """
    rows = []
    for name in axis_universe("configs"):
        rows += [g for g in metrics(name)["groups"] if g["model_spec"].get("role") == "agent"]
    return {"rows": rows}


@app.get("/api/pairs")
def pairs(
    config: str | None = None,
    attack: str | None = None,
    run_id: str | None = None,
    limit: int = 100,
) -> dict:
    """Вкладка «Диалоги»: пары эпизодов из манифестов плоским списком с фильтрами."""
    found, configs, run_ids = [], set(), []
    for m in _manifests():
        run_ids.append(m.get("run_id"))
        for cell in m.get("cells", []):
            configs.add(cell.get("config"))
            if (run_id and m.get("run_id") != run_id) or (config and cell.get("config") != config):
                continue
            for e in cell.get("episodes", []):
                if attack and (e.get("attack") or {}).get("outcome") != attack:
                    continue
                found.append(
                    {
                        "run_id": m.get("run_id"),
                        "remote_llm": bool(m.get("remote_llm")),
                        "config": cell.get("config"),
                        **(cell.get("scenario") or {}),
                        **e,
                    }
                )
    return {
        "total": len(found),
        "pairs": found[:limit],
        "configs": sorted(c for c in configs if c),
        "runs": run_ids,
    }


class ProbeIn(BaseModel):
    config: str
    tactic: str
    budget: int = 8
    seed: int | None = None
    style: str | None = None
    agent_model: str | None = None
    attacker_model: str | None = None
    allow_remote_llm: bool = False


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
                "allow_remote_llm": body.allow_remote_llm,
            }
        )
    except SystemExit as exc:
        raise HTTPException(400, str(exc)) from None


app.mount("/static", StaticFiles(directory=STATIC), name="static")
