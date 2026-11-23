"""metrics_svc (port 9415): L*/break-even/detection over the raw DB, at any time.

Collection ≠ computation: this service reads the raw DB of filter_svc (read-only
connection, LAB_RAW_DB_URL — the same DB, never written) and stores results in its own
DB (LAB_METRICS_DB_URL, default sqlite ./runs/metrics.db). Fixing a formula needs no
run rerun: POST /compute recalculates over the stored turns.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from lab.db import is_postgres

from . import extract, formulas
from .models import Base, MetricRow

app = FastAPI(title="metrics_svc", version="0.1.0")

REFERENCE_CONFIG = "g0"
METRICS_VERSION = "metrics-lab-1"


def raw_db_url() -> str:
    return os.environ.get("LAB_RAW_DB_URL", "sqlite:///./runs/raw.db")


def db_url() -> str:
    return os.environ.get("LAB_METRICS_DB_URL", "sqlite:///./runs/metrics.db")


_raw_engines: dict[str, Engine] = {}
_metrics_engines: dict[str, Engine] = {}


def _raw_engine() -> Engine:
    """Read-only connection to the raw DB of filter_svc (SQLite opens in mode=ro)."""
    url = raw_db_url()
    if url not in _raw_engines:
        if url.startswith("sqlite:///") and ":memory:" not in url:
            ro = "file:" + url.removeprefix("sqlite:///") + "?mode=ro&uri=true"
            eng: Engine = create_engine("sqlite:///" + ro, future=True)
        else:
            eng = create_engine(url, future=True, pool_pre_ping=True)
            if is_postgres(eng):

                def set_ro(dbapi_conn, _record):
                    dbapi_conn.exec_driver_sql("SET default_transaction_read_only = on")

                event.listens_for(eng, "connect")(set_ro)
        _raw_engines[url] = eng
    return _raw_engines[url]


def metrics_engine() -> Engine:
    url = db_url()
    if url not in _metrics_engines:
        if url.startswith("sqlite:///") and ":memory:" not in url:
            Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
        _metrics_engines[url] = create_engine(url, future=True)
    return _metrics_engines[url]


def init_metrics_db() -> None:
    Base.metadata.create_all(metrics_engine())


class ComputeIn(BaseModel):
    config_name: str | None = None
    model_spec: dict[str, Any] | None = None
    include_probe: bool = False
    include_remote: bool = False


def _raw_missing() -> bool:
    """True, если SQLite-файл сырой БД ещё не создан (деградация: «нет прогонов»)."""
    url = raw_db_url()
    if not url.startswith("sqlite:///") or ":memory:" in url:
        return False
    path = url.removeprefix("sqlite:///").split("?")[0]
    return not Path(path).exists()


def _read_episodes(
    include_probe: bool = False, include_remote: bool = False
) -> list[extract.Episode]:
    if _raw_missing():
        return []
    with Session(_raw_engine()) as session:
        return extract.episodes_of(
            session, include_probe=include_probe, include_remote=include_remote
        )


def _reference_rows(
    groups: dict[tuple[str, str], list[extract.Episode]], model_key: str
) -> extract.Aggregate | None:
    key = (REFERENCE_CONFIG, model_key)
    return extract.aggregate(groups[key]) if key in groups else None


def _break_even(agg: extract.Aggregate, ref: extract.Aggregate | None) -> dict[str, Any]:
    """L* of the config against the reference (g0) of the same model; §9.2 statuses."""
    none = lambda st: {
        "status": st,
        "L_star": None,
        "L_star_min": None,
        "L_star_max": None,
        "prices_robust": None,
        "bounds": {},
        "terms": {},
        "numerator": None,
        "decision_at_L_viol": {},
    }
    if agg.config == REFERENCE_CONFIG:
        return none("reference")
    if ref is None:
        return none("no_reference")
    return formulas.bounds(
        {k: agg.as_inputs() for k in ("low", "base", "high")},
        {k: ref.as_inputs() for k in ("low", "base", "high")},
    )


def _metric_rows(agg: extract.Aggregate, be: dict[str, Any]) -> list[dict[str, Any]]:
    spec = json.loads(agg.model_spec)

    def row(metric: str, value: Any) -> dict[str, Any]:
        return {"config_name": agg.config, "model_spec": spec, "metric": metric, "value": value}

    d = agg.detection
    return [
        row("n_attack", agg.n_attack),
        row("n_legal", agg.n_legal),
        row("w_A", agg.w_A),
        row("V", agg.V),
        row("R", agg.R),
        row("E", agg.E),
        row("detection_tpr", d["TPR"]),
        row("detection_fpr", d["FPR"]),
        row("detection_precision", d["precision"]),
        row("break_even_status", be["status"]),
        row("L_star", be["L_star"]),
        row("L_star_min", be["L_star_min"]),
        row("L_star_max", be["L_star_max"]),
        row("prices_robust", be["prices_robust"]),
        row("break_even", be),
        row("detection", d),
    ]


def compute(
    config_name: str | None = None,
    model_spec: dict | None = None,
    include_probe: bool = False,
    include_remote: bool = False,
) -> int:
    """Recalculate metrics from the raw DB into the metrics DB; returns stored row count.

    The filter selects which configs are computed; the reference config is still looked
    up in the full raw data, so L* survives a config-filtered /compute.
    """
    if _raw_missing():
        init_metrics_db()
        return 0
    all_eps = _read_episodes(include_probe=include_probe, include_remote=include_remote)
    groups_all = extract.group(all_eps)
    eps = all_eps
    if model_spec is not None:
        eps = [e for e in eps if e.model_spec == json.dumps(model_spec, sort_keys=True)]
    if config_name is not None:
        eps = [e for e in eps if e.config == config_name]
    rows: list[dict[str, Any]] = []
    for (cfg, mkey), group_eps in sorted(extract.group(eps).items()):
        agg = extract.aggregate(group_eps)
        # L* needs the reference config of the same pinned model in the same data.
        ref = _reference_rows(groups_all, mkey) if cfg != REFERENCE_CONFIG else None
        rows.extend(_metric_rows(agg, _break_even(agg, ref)))
    with Session(metrics_engine()) as session:
        for cfg, spec in {
            (r["config_name"], json.dumps(r["model_spec"], sort_keys=True)) for r in rows
        }:
            session.query(MetricRow).filter(
                MetricRow.config_name == cfg, MetricRow.model_spec == spec
            ).delete()
            session.flush()
        for r in rows:
            session.add(
                MetricRow(
                    config_name=r["config_name"],
                    model_spec=json.dumps(r["model_spec"], sort_keys=True),
                    metric=r["metric"],
                    value=json.dumps(r["value"]),
                )
            )
        session.commit()
    return len(rows)


@app.get("/health")
def health() -> dict:
    return {"service": "metrics_svc", "status": "ok", "version": METRICS_VERSION}


@app.post("/compute")
def compute_endpoint(body: ComputeIn) -> dict:
    init_metrics_db()
    return {
        "computed": compute(
            body.config_name, body.model_spec, body.include_probe, body.include_remote
        )
    }


@app.get("/metrics/{config_name}")
def metrics(config_name: str) -> dict:
    init_metrics_db()
    if _raw_missing():
        return {
            "config_name": config_name,
            "results": [],
            "note": "нет прогонов — сырая БД ещё не создана",
        }
    with Session(metrics_engine()) as session:
        rows = (
            session.query(MetricRow)
            .filter(MetricRow.config_name == config_name)
            .order_by(MetricRow.model_spec, MetricRow.metric, MetricRow.id)
            .all()
        )
    return {
        "config_name": config_name,
        "results": [
            {
                "model_spec": json.loads(r.model_spec),
                "metric": r.metric,
                "value": json.loads(r.value),
                "computed_at": r.computed_at.isoformat(),
            }
            for r in rows
        ],
    }
