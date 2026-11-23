"""Cost summary by sides, components, traffic classes and episodes; conversion to money.

Side separation: `defender_borne` is everything recorded by defended-side components
(including agent and guardrail work on attack episodes — it is a cost of our capacity);
`self_limited` is everything the attacking side recorded (its own tokens), reported
separately and not included in ΔNet. `harness` events belong to neither side.

Rates — assumption of the "computation to money" decomposition: tokens [0.05, 0.50] USD per
1M (base 0.20), CPU [0.02, 0.10] USD per CPU-hour (base 0.05), GPU [0.20, 1.50] (base 0.50).
Manual review minutes are not converted to money here: that is the ΔE·C_manual member of
break-even.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from typing import Any

from .schema import COST_FIELDS, GUARD_PREFIX, SIDES, EventLogError

MS_PER_HOUR = 3_600_000.0


@dataclass(frozen=True)
class Rates:
    token_usd_per_m: float = 0.20
    cpu_usd_per_hour: float = 0.05
    gpu_usd_per_hour: float = 0.50

    def __post_init__(self):
        for k, v in asdict(self).items():
            if (
                isinstance(v, bool)
                or not isinstance(v, (int, float))
                or not math.isfinite(v)
                or v < 0
            ):
                raise EventLogError(f"rate {k} must be a finite non-negative: {v!r}")


RATE_PRESETS: dict[str, Rates] = {
    "low": Rates(0.05, 0.02, 0.20),
    "base": Rates(0.20, 0.05, 0.50),
    "high": Rates(0.50, 0.10, 1.50),
}


def compute_usd(cost: Mapping[str, Any], rates: Rates) -> float:
    """Money cost of computation of one record or a sum of records."""
    tokens = cost.get("tokens_in", 0) + cost.get("tokens_out", 0)
    return (
        tokens * rates.token_usd_per_m / 1_000_000.0
        + cost.get("cpu_ms", 0.0) * rates.cpu_usd_per_hour / MS_PER_HOUR
        + cost.get("gpu_ms", 0.0) * rates.gpu_usd_per_hour / MS_PER_HOUR
    )


def _zero() -> dict[str, Any]:
    t: dict[str, Any] = {k: 0 for k in COST_FIELDS}
    t.update(events=0, cost_events=0)
    return t


def _add(total: dict[str, Any], cost: Mapping[str, Any] | None) -> None:
    total["events"] += 1
    if cost:
        total["cost_events"] += 1
        for k, v in cost.items():
            total[k] += v


def _finish(total: dict[str, Any], rates: Rates) -> dict[str, Any]:
    out = dict(total)
    out["tokens"] = out["tokens_in"] + out["tokens_out"]
    out["usd_compute"] = compute_usd(out, rates)
    return out


def defender_bucket(component: str) -> str:
    """Defender cost bucket: all guardrails are folded into `guard` (C_guard)."""
    return "guard" if component.startswith(GUARD_PREFIX) else component


def summarize(events: Iterable[Mapping[str, Any]], rates: Rates | None = None) -> dict[str, Any]:
    rates = rates or RATE_PRESETS["base"]
    events = list(events)
    if not events:
        raise EventLogError("empty journal")
    modes = {
        bool(e["data"].get("research_mode"))
        for e in events
        if e["component"] == "runner" and e["kind"] == "run_start"
    }
    run_ids = sorted({e["run_id"] for e in events})
    if len(modes) > 1:
        raise EventLogError("research-mode and main runs must not be mixed")

    by_side = {s: _zero() for s in SIDES}
    by_component: dict[str, dict] = {}
    by_traffic: dict[str, dict[str, dict]] = {}
    episodes: dict[str, dict] = {}
    for e in events:
        side, comp, cost = e["side"], e["component"], e.get("cost")
        _add(by_side[side], cost)
        _add(by_component.setdefault(comp, dict(_zero(), side=side)), cost)
        eid = e.get("episode_id")
        if eid is None:
            continue
        key = f"{e['run_id']}/{eid}" if len(run_ids) > 1 else eid
        ep = episodes.setdefault(
            key,
            {
                "traffic": e["traffic"],
                "defender": _zero(),
                "attacker": _zero(),
                "defender_components": {},
            },
        )
        _add(by_traffic.setdefault(e["traffic"], {s: _zero() for s in SIDES})[side], cost)
        if side in ("defender", "attacker"):
            _add(ep[side], cost)
        if side == "defender":
            _add(ep["defender_components"].setdefault(defender_bucket(comp), _zero()), cost)

    fin = lambda t: _finish(t, rates)
    return {
        "run_ids": run_ids,
        "research_mode": modes.pop() if modes else None,
        "rates": asdict(rates),
        "defender_borne": fin(by_side["defender"]),
        "self_limited": fin(by_side["attacker"]),
        "harness": fin(by_side["harness"]),
        "by_component": {c: dict(fin(t), side=t["side"]) for c, t in sorted(by_component.items())},
        "by_traffic": {
            tr: {s: fin(t) for s, t in sides.items()} for tr, sides in sorted(by_traffic.items())
        },
        "episodes": {
            k: {
                "traffic": v["traffic"],
                "defender": fin(v["defender"]),
                "attacker": fin(v["attacker"]),
                "defender_components": {
                    c: fin(t) for c, t in sorted(v["defender_components"].items())
                },
            }
            for k, v in sorted(episodes.items())
        },
    }


def per_episode_means(summary: Mapping[str, Any], traffic: str | None = None) -> dict[str, float]:
    """Mean defender money cost per episode: `C_ep` (whole defended side) and `C_guard`
    (guardrails only), optionally by traffic class. The attacker's own mean spend
    (`self_limited_usd`) is reported separately."""
    eps = [v for v in summary["episodes"].values() if traffic is None or v["traffic"] == traffic]
    if not eps:
        return {"episodes": 0, "C_ep": 0.0, "C_guard": 0.0, "self_limited_usd": 0.0}
    n = len(eps)
    return {
        "episodes": n,
        "C_ep": math.fsum(v["defender"]["usd_compute"] for v in eps) / n,
        "C_guard": math.fsum(
            v["defender_components"].get("guard", {}).get("usd_compute", 0.0) for v in eps
        )
        / n,
        "self_limited_usd": math.fsum(v["attacker"]["usd_compute"] for v in eps) / n,
    }
