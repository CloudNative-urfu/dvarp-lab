"""Episodes and per-(config × model_spec) aggregates from the raw DB of filter_svc.

Adapted from dvarp-prototype @ d5828df (darp_range/metrics/extract.py). Text of the parties
is never read here — only structured fields inside raw:

- raw.verdict: {violation, outcome, task_status, escalated} — episode outcome by the shop
  estimator, taken from the highest-numbered turn that carries a verdict;
- raw.guard_signals: {signal: count} per turn, summed over the episode; "detected" = a
  flag/block signal fired at least once (DETECT_SIGNALS of the prototype);
- raw.run_id / raw.seed: optional run grouping for seed_spread.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from . import formulas


@dataclass(frozen=True)
class Episode:
    """One episode in the volume needed by metrics (no party text)."""

    config: str
    model_spec: str  # canonical JSON of the pinned model_spec
    episode_id: str
    channel: str
    violation: bool
    outcome: str | None
    task_status: str | None
    escalated: bool
    detected: bool
    run_id: str | None = None
    seed: int | None = None


def _model_key(model_spec: dict[str, Any]) -> str:
    return json.dumps(model_spec, sort_keys=True, ensure_ascii=False)


def episodes_of(session: Session) -> list[Episode]:
    """Collapse raw turns into episodes (one row per episode_id × config × model_spec)."""
    from services.filter.models import Turn

    by_key: dict[tuple[str, str, str], dict] = {}
    for row in session.query(Turn).order_by(Turn.turn, Turn.id).all():
        key = (row.config_name, _model_key(row.model_spec or {}), row.episode_id)
        ep = by_key.setdefault(
            key,
            {
                "config": row.config_name,
                "model": key[1],
                "episode_id": row.episode_id,
                "channel": row.channel,
                "signals": {},
            },
        )
        raw = row.raw or {}
        ep["signals"] = {
            k: ep["signals"].get(k, 0) + v for k, v in (raw.get("guard_signals") or {}).items()
        }
        verdict = raw.get("verdict")
        if verdict:
            ep["verdict"] = verdict
        for opt in ("run_id", "seed"):
            if opt in raw:
                ep[opt] = raw[opt]
    out = []
    for key, ep in sorted(by_key.items()):
        signals = ep["signals"]
        detected = any(signals.get(s, 0) > 0 for s in formulas.DETECT_SIGNALS)
        verdict = ep.get("verdict") or {}
        out.append(
            Episode(
                config=ep["config"],
                model_spec=ep["model"],
                episode_id=ep["episode_id"],
                channel=ep["channel"],
                violation=bool(verdict.get("violation")),
                outcome=verdict.get("outcome"),
                task_status=verdict.get("task_status"),
                escalated=bool(verdict.get("escalated")),
                detected=detected,
                run_id=ep.get("run_id"),
                seed=ep.get("seed"),
            )
        )
    return out


@dataclass
class Aggregate:
    """Aggregates of one config × model_spec (prototype extract.aggregate, simplified)."""

    config: str
    model_spec: str
    run_id: str | None
    seed: int | None
    n_attack: int
    n_legal: int
    w_A: float
    w_L: float
    V: float
    V_k: int
    V_n: int
    R: float
    E: float
    detection: dict[str, Any] = field(default_factory=dict)

    def as_inputs(self, config: str | None = None) -> formulas.Inputs:
        return formulas.Inputs(
            config=config or self.config,
            w_A=self.w_A,
            w_L=self.w_L,
            V=self.V,
            V_k=self.V_k,
            V_n=self.V_n,
            R=self.R,
            E=self.E,
        )


def aggregate(eps: list[Episode]) -> Aggregate:
    """FR-1.23-style aggregates of one config × model_spec from its episodes."""
    att = [e for e in eps if e.channel == "attack"]
    legal = [e for e in eps if e.channel == "legal"]
    n_a, n_l = len(att), len(legal)
    n = n_a + n_l
    w_a = n_a / n if n else 0.0
    v_k = sum(e.violation for e in att)
    r_k = sum(e.task_status == "unjustified_refusal" for e in legal)
    e_k = sum(e.escalated for e in eps)
    return Aggregate(
        config=eps[0].config,
        model_spec=eps[0].model_spec,
        run_id=eps[0].run_id,
        seed=eps[0].seed,
        n_attack=n_a,
        n_legal=n_l,
        w_A=w_a,
        w_L=1.0 - w_a,
        V=v_k / n_a if n_a else 0.0,
        V_k=v_k,
        V_n=n_a,
        R=r_k / n_l if n_l else 0.0,
        E=e_k / n if n else 0.0,
        detection=formulas.detection([e.detected for e in att], [e.detected for e in legal]),
    )


def group(eps: list[Episode]) -> dict[tuple[str, str], list[Episode]]:
    """Episodes grouped by (config_name, canonical model_spec)."""
    out: dict[tuple[str, str], list[Episode]] = {}
    for e in eps:
        out.setdefault((e.config, e.model_spec), []).append(e)
    return out
