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
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from lab.db import is_postgres

from . import economics, extract, formulas
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
    engine = metrics_engine()
    Base.metadata.create_all(engine)
    if "mode" not in {c["name"] for c in inspect(engine).get_columns("metric_results")}:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "ALTER TABLE metric_results ADD COLUMN mode VARCHAR(16) NOT NULL DEFAULT 'all'"
                )
            )


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


def _break_even(agg: extract.Aggregate, ref: extract.Aggregate | None) -> dict[str, Any]:
    """L* of the config against the reference (g0) of the same model; §9.2 statuses.
    Рядом — L* реального фрейма (фрейм A, #34) по сценариям p_att пина."""
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
        out = none("reference")
        out["L_star_real"] = None
        return out
    if ref is None:
        out = none("no_reference")
        out["L_star_real"] = None
        return out
    out = formulas.bounds(
        {k: agg.as_inputs() for k in ("low", "base", "high")},
        {k: ref.as_inputs() for k in ("low", "base", "high")},
    )
    bp = formulas.base_prices()
    out["L_star_real"] = {
        f"{p_att:g}": formulas.l_star_real(agg.as_inputs(), ref.as_inputs(), bp, p_att)["L_star"]
        for p_att in economics.load_economics()["p_att_scenarios"]
    }
    return out


def _metric_rows(
    agg: extract.Aggregate, be: dict[str, Any], spread: dict[str, Any], mode: str
) -> list[dict[str, Any]]:
    spec = json.loads(agg.model_spec)

    def row(metric: str, value: Any) -> dict[str, Any]:
        return {
            "config_name": agg.config,
            "model_spec": spec,
            "mode": mode,
            "metric": metric,
            "value": value,
        }

    d = agg.detection
    q = agg.queue
    return [
        row("n_attack", agg.n_attack),
        row("n_legal", agg.n_legal),
        row("n_remote", agg.n_remote),
        row("w_A", agg.w_A),
        row("V", agg.V),
        row("R", agg.R),
        row("E", agg.E),
        row("C_ep", agg.c_ep),
        row("C_guard", agg.c_guard),
        row("C_guard_cpu_ms", agg.guard_cpu_ms),
        row("E_attack", agg.e_attack),
        row("E_legal", agg.e_legal),
        row("queue_p_wait", q.get("P_wait")),
        row("queue_w_q_min", q.get("W_q_min")),
        row("queue_p_abandon", q.get("P_abandon")),
        row("queue_q_l_min", q.get("Q_L_min")),
        row("queue_stable", q.get("stable")),
        row("queue_grid", agg.queue_grid),
        row("G_tau_k", agg.g_tau_k),
        row("G_tau_rate", agg.g_tau_rate),
        row("G_tau_wilson_low", agg.g_tau_wilson[0] if agg.g_tau_wilson else None),
        row("G_tau_wilson_high", agg.g_tau_wilson[1] if agg.g_tau_wilson else None),
        row("G_tau_gate", agg.g_tau_gate),
        row("detection_tpr", d["TPR"]),
        row("detection_fpr", d["FPR"]),
        row("detection_precision", d["precision"]),
        row("break_even_status", be["status"]),
        row("L_star", be["L_star"]),
        row("L_star_min", be["L_star_min"]),
        row("L_star_max", be["L_star_max"]),
        row("prices_robust", be["prices_robust"]),
        row("break_even", be),
        row("L_star_real", be.get("L_star_real")),
        row("detection", d),
        row("seed_spread", spread),
    ]


def _seed_spread(eps: list[extract.Episode], reference: list[extract.Episode]) -> dict[str, Any]:
    """Compare seed groups only with g0 of the same run, seed and mode."""
    by_seed: dict[tuple[str, int], list[extract.Episode]] = {}
    refs: dict[tuple[str, int], list[extract.Episode]] = {}
    for e in eps:
        if e.run_id is not None and e.seed is not None:
            by_seed.setdefault((e.run_id, e.seed), []).append(e)
    for e in reference:
        if e.run_id is not None and e.seed is not None:
            refs.setdefault((e.run_id, e.seed), []).append(e)
    rows = []
    for (run_id, seed), group in sorted(by_seed.items()):
        agg = extract.aggregate(group)
        ref = extract.aggregate(refs[run_id, seed]) if (run_id, seed) in refs else None
        be = _break_even(agg, ref)
        rows.append(
            {
                "run_id": run_id,
                "seed": seed,
                "V": agg.V,
                "R": agg.R,
                "L_star": be["L_star"],
                "status": be["status"],
            }
        )
    return formulas.seed_spread(rows)


def _mode_groups(
    eps: list[extract.Episode], include_remote: bool
) -> dict[tuple[str, str, str], list[extract.Episode]]:
    groups = {}
    for (cfg, model), episodes in extract.group(eps).items():
        local = [e for e in episodes if not e.remote]
        remote = [e for e in episodes if e.remote]
        if local:
            groups[cfg, model, "local"] = local
        if include_remote and remote:
            groups[cfg, model, "remote"] = remote
            if local:
                groups[cfg, model, "all"] = episodes
    return groups


def _computed(
    config_name: str | None = None,
    model_spec: dict | None = None,
    include_probe: bool = False,
    include_remote: bool = False,
) -> list[tuple[extract.Aggregate, list[dict[str, Any]]]]:
    """Aggregates and metric rows per config × model_spec over the raw DB (no writes).

    The filter selects which configs are computed; the reference config is still looked
    up in the full raw data, so L* survives a config-filtered computation.
    """
    all_eps = _read_episodes(include_probe=include_probe, include_remote=include_remote)
    groups_all = _mode_groups(all_eps, include_remote)
    eps = all_eps
    if model_spec is not None:
        eps = [e for e in eps if e.model_spec == json.dumps(model_spec, sort_keys=True)]
    if config_name is not None:
        eps = [e for e in eps if e.config == config_name]
    out = []
    for (cfg, mkey, mode), group_eps in sorted(_mode_groups(eps, include_remote).items()):
        agg = extract.aggregate(group_eps)
        reference = groups_all.get((REFERENCE_CONFIG, mkey, mode), [])
        ref = extract.aggregate(reference) if reference else None
        be = _break_even(agg, ref)
        out.append((agg, _metric_rows(agg, be, _seed_spread(group_eps, reference), mode)))
    return out


def compute(
    config_name: str | None = None,
    model_spec: dict | None = None,
    include_probe: bool = False,
    include_remote: bool = False,
) -> int:
    """Recalculate metrics from the raw DB into the metrics DB; returns stored row count."""
    if _raw_missing():
        init_metrics_db()
        return 0
    rows = [
        r
        for _, group_rows in _computed(config_name, model_spec, include_probe, include_remote)
        for r in group_rows
    ]
    with Session(metrics_engine()) as session:
        for cfg, spec, mode in {
            (r["config_name"], json.dumps(r["model_spec"], sort_keys=True), r["mode"]) for r in rows
        }:
            session.query(MetricRow).filter(
                MetricRow.config_name == cfg, MetricRow.model_spec == spec, MetricRow.mode == mode
            ).delete()
            session.flush()
        for r in rows:
            session.add(
                MetricRow(
                    config_name=r["config_name"],
                    model_spec=json.dumps(r["model_spec"], sort_keys=True),
                    mode=r["mode"],
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


@app.post("/preview")
def preview_endpoint(body: ComputeIn) -> dict:
    """One-off computation by filters: computed and returned, never written to metric_results.

    Next to the final metrics each group carries the collected aggregates (counts and
    rates the formulas consume), so a reader sees what the numbers are made of.
    """
    if _raw_missing():
        return {"groups": []}
    groups = _computed(body.config_name, body.model_spec, body.include_probe, body.include_remote)
    return {
        "groups": [
            {
                "config_name": agg.config,
                "model_spec": json.loads(agg.model_spec),
                "mode": rows[0]["mode"],
                "final": {r["metric"]: r["value"] for r in rows},
                "seed_spread": next(r["value"] for r in rows if r["metric"] == "seed_spread"),
                "raw": {
                    k: getattr(agg, k)
                    for k in (
                        "n_attack",
                        "n_legal",
                        "n_remote",
                        "V_k",
                        "V_n",
                        "w_A",
                        "w_L",
                        "V",
                        "R",
                        "E",
                    )
                },
            }
            for agg, rows in groups
        ]
    }


@app.get("/models")
def models_with_data() -> dict:
    """model_spec, по которым есть записи (включая probe/remote) — для фильтров консоли."""
    specs = {e.model_spec for e in _read_episodes(include_probe=True, include_remote=True)}
    return {"models": [json.loads(s) for s in sorted(specs)]}


@app.get("/configs")
def configs_with_data() -> dict:
    """Конфигурации, по которым реально есть прогоны (стабильный порядок)."""
    names = sorted({e.config for e in _read_episodes()})
    return {"configs": names}


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
            .order_by(MetricRow.model_spec, MetricRow.mode, MetricRow.metric, MetricRow.id)
            .all()
        )
    return {
        "config_name": config_name,
        "results": [
            {
                "model_spec": json.loads(r.model_spec),
                "mode": r.mode,
                "metric": r.metric,
                "value": json.loads(r.value),
                "computed_at": r.computed_at.isoformat(),
            }
            for r in rows
        ],
    }
