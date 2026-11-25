"""Economics pin loader (issue #11): frozen tariffs and scenario prices.

The values are **declared market averages**, not measurements; validity of any
money conclusion is protected by the price-sensitivity requirement (#11, §2.2 of
docs/validity.md). The pin lives in `frozen/economics.json` (freezing = explicit
commit); the loader validates the schema so a typo cannot silently zero a tariff.

Non-LLM guardrails are charged strictly $0: CPU seconds of local detectors stay
in the journal as time (cpu_ms/latency_ms) and are never converted to dollars —
money differentiates only the LLM class (#11).
"""

from __future__ import annotations

import json
import math
from typing import Any

from lab.modelspec import FROZEN_DIR

ECONOMICS_PATH = FROZEN_DIR / "economics.json"


def _positive(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"economics.{name}: expected a number, got {value!r}")
    v = float(value)
    if not math.isfinite(v) or v < 0:
        raise ValueError(f"economics.{name}: expected a finite non-negative, got {value!r}")
    return v


def _tariff(raw: Any, name: str) -> tuple[float, float]:
    if not isinstance(raw, dict):
        raise TypeError(f"economics.{name}: expected an object")
    return _positive(raw.get("input_per_million"), f"{name}.input_per_million"), _positive(
        raw.get("output_per_million"), f"{name}.output_per_million"
    )


def load_economics(path=None) -> dict[str, Any]:
    """Validated economics pin (frozen/economics.json)."""
    path = path or ECONOMICS_PATH
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema") != "darp-economics-1":
        raise ValueError("economics pin: schema must be darp-economics-1")
    out = {
        "agent_tariff": _tariff(data.get("agent_tariff"), "agent_tariff"),
        "guard_tariff": _tariff(data.get("guard_tariff"), "guard_tariff"),
        "C_human": _positive(data.get("C_human"), "C_human"),
        "C_churn": _positive(data.get("C_churn"), "C_churn"),
    }
    p_att = data.get("p_att_scenarios")
    if not isinstance(p_att, list) or not p_att:
        raise ValueError("economics.p_att_scenarios: expected a non-empty list")
    out["p_att_scenarios"] = sorted(float(_positive(x, "p_att_scenarios[]")) for x in p_att)
    factors = data.get("price_sensitivity_factors")
    if not isinstance(factors, list) or not factors:
        raise ValueError("economics.price_sensitivity_factors: expected a non-empty list")
    out["price_sensitivity_factors"] = sorted(
        float(_positive(x, "price_sensitivity_factors[]")) for x in factors
    )
    out["queue"] = _queue(data.get("queue"))
    return out


def _queue(raw: Any) -> dict[str, Any]:
    """Queue scale anchor of the pin (issue #12): straight-to-queue share, ρ₀ base load,
    operators/service/patience."""
    if not isinstance(raw, dict):
        raise TypeError("economics.queue: expected an object")
    base_rho = raw.get("base_rho")
    if isinstance(base_rho, bool) or not isinstance(base_rho, (int, float)):
        raise TypeError("economics.queue.base_rho: expected a number")
    if not math.isfinite(float(base_rho)) or not 0 <= float(base_rho) < 1:
        raise ValueError("economics.queue.base_rho: expected a share in [0, 1)")
    stq = raw.get("straight_to_queue")
    if isinstance(stq, bool) or not isinstance(stq, (int, float)):
        raise TypeError("economics.queue.straight_to_queue: expected a number")
    if not math.isfinite(float(stq)) or not 0 < float(stq) < 1:
        raise ValueError("economics.queue.straight_to_queue: expected a share in (0, 1)")
    operators = raw.get("operators")
    if isinstance(operators, bool) or not isinstance(operators, int) or operators < 1:
        raise ValueError("economics.queue.operators: expected an integer ≥ 1")
    rho0 = raw.get("rho0_scenarios")
    if not isinstance(rho0, list) or not rho0:
        raise ValueError("economics.queue.rho0_scenarios: expected a non-empty list")
    for x in rho0:
        if (
            isinstance(x, bool)
            or not isinstance(x, (int, float))
            or not math.isfinite(float(x))
            or not 0 <= float(x) < 1
        ):
            raise ValueError(f"economics.queue.rho0_scenarios[]: share in [0, 1), got {x!r}")
    if float(base_rho) not in {float(x) for x in rho0}:
        raise ValueError("economics.queue: base_rho must be one of rho0_scenarios")
    return {
        "straight_to_queue": float(stq),
        "base_rho": float(base_rho),
        "rho0_scenarios": sorted(float(x) for x in rho0),
        "operators": int(operators),
        "service_minutes": _positive(raw.get("service_minutes"), "queue.service_minutes"),
        "patience_minutes": _positive(raw.get("patience_minutes"), "queue.patience_minutes"),
    }


def queue_defaults(pin: dict[str, Any]) -> dict[str, Any]:
    """Base-case queue parameters: the middle p_att scenario anchors the base computation."""
    return {
        "p_att": pin["p_att_scenarios"][len(pin["p_att_scenarios"]) // 2],
        **pin["queue"],
    }


def money(cost: dict[str, Any], tariff: tuple[float, float]) -> float:
    """USD cost of one cost-dict {tokens_in, tokens_out} at per-million tariffs."""
    tokens_in = float(cost.get("tokens_in") or 0.0)
    tokens_out = float(cost.get("tokens_out") or 0.0)
    return (tokens_in * tariff[0] + tokens_out * tariff[1]) / 1_000_000.0


__all__ = ["ECONOMICS_PATH", "load_economics", "money", "queue_defaults"]
