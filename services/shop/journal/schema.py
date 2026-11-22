"""Journal schema: component registry, sides and closed event vocabularies.

The recording side is derived from the component via the registry and is never passed by
calling code: an attacker-side component physically cannot charge defender costs (and vice
versa). Sides:
- `defender` — defended side: agent, guardrails, policy, executor, tools, manual queue,
  process rules g_proc. Its costs are defender-borne and enter break-even economics.
- `attacker` — attacking side; its costs are self-limited and reported separately.
- `harness` — polygon service parts (orchestrator, channel as transport, evaluator).
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from typing import Any

SCHEMA = "lab.event_log/1"

SIDES = ("defender", "attacker", "harness")
TRAFFIC_CLASSES = ("legal", "attack", "control")

# Base components and their side. Guardrails are registered by the `guard:<plugin_id>` pattern.
COMPONENT_SIDES: dict[str, str] = {
    "agent": "defender",
    "tools": "defender",
    "executor": "defender",
    "policy": "defender",
    "manual_queue": "defender",
    "process": "defender",  # process rules g_proc (configs component)
    "attacker": "attacker",
    "runner": "harness",
    "channel": "harness",
    "evaluator": "harness",
}
GUARD_PREFIX = "guard:"
_GUARD_RE = re.compile(r"^guard:[a-z0-9][a-z0-9_.-]{0,63}$")

# Closed event-kind vocabularies per component class. An unknown kind is a recording error:
# metrics are built from the journal, and a typo in a kind would silently distort the bill.
KINDS: dict[str, frozenset[str]] = {
    "agent": frozenset({"llm_call", "tool_proposed", "reply", "note"}),
    "tools": frozenset({"tool_call", "tool_result"}),
    "executor": frozenset({"exec_request", "exec_result"}),
    "policy": frozenset({"decision"}),
    "manual_queue": frozenset({"enqueue", "service_start", "service_end"}),
    "process": frozenset({"admission", "decision"}),
    "guard": frozenset({"guard_signal", "guard_error"}),
    "attacker": frozenset({"llm_call", "attempt", "message_composed", "protocol_violation"}),
    "runner": frozenset(
        {
            "run_start",
            "run_end",
            "episode_start",
            "episode_end",
            "snapshot",
            "restore",
            "reproducibility_defect",
            "legal_user",
            "svc_retry",
        }
    ),
    "channel": frozenset(
        {"session_open", "message", "research_feedback", "protocol_violation", "session_close"}
    ),
    "evaluator": frozenset({"outcome", "legal_outcome"}),
}

# Event kinds that are "taken decisions" and must carry a basis.
DECISION_KINDS = frozenset({"decision", "exec_result", "outcome", "legal_outcome"})

GUARD_SIGNALS = ("allow", "flag", "block", "score")
POLICY_ACTIONS = ("continue", "isolate", "clarify", "escalate", "terminate")
ATTACK_OUTCOMES = ("executed", "refused", "ignored")
CHANNEL_DIRECTIONS = ("to_defender", "to_attacker")
# Extended channel feedback is only allowed in a research-mode journal.
RESEARCH_ONLY_KINDS = frozenset({"research_feedback"})

# Cost record fields. Tokens and requests are deterministic and enter the trajectory; time
# fields are volatile measurements and are excluded from the trajectory.
COST_INT_FIELDS = ("tokens_in", "tokens_out", "requests")
COST_FLOAT_FIELDS = ("cpu_ms", "gpu_ms", "latency_ms", "manual_minutes")
COST_FIELDS = COST_INT_FIELDS + COST_FLOAT_FIELDS


class EventLogError(ValueError):
    """Recording violates the journal schema or the side separation."""


def component_class(component: str) -> str:
    if component in COMPONENT_SIDES:
        return component
    if _GUARD_RE.match(component or ""):
        return "guard"
    raise EventLogError(f"unknown component {component!r}")


def side_of(component: str) -> str:
    cls = component_class(component)
    return "defender" if cls == "guard" else COMPONENT_SIDES[cls]


def _finite_nonneg(value: Any, name: str, *, integer: bool) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EventLogError(f"cost.{name}: expected a number, got {value!r}")
    if integer and not isinstance(value, int):
        raise EventLogError(f"cost.{name}: expected an int, got {value!r}")
    if not math.isfinite(value) or value < 0:
        raise EventLogError(f"cost.{name}: expected a finite non-negative, got {value!r}")


def validate_cost(cost: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if cost is None:
        return None
    if not isinstance(cost, Mapping):
        raise EventLogError("cost must be a dict")
    unknown = set(cost) - set(COST_FIELDS)
    if unknown:
        raise EventLogError(f"unknown cost fields: {sorted(unknown)}")
    for k, v in cost.items():
        _finite_nonneg(v, k, integer=k in COST_INT_FIELDS)
    return {k: cost[k] for k in COST_FIELDS if k in cost}


def validate_payload(cls: str, kind: str, data: Mapping[str, Any]) -> None:
    """Content checks of key event kinds."""
    if kind in DECISION_KINDS:
        basis = data.get("basis")
        if not isinstance(basis, str) or not basis.strip():
            raise EventLogError(f"{cls}.{kind}: decision without a basis (data.basis)")
    if cls == "guard" and kind == "guard_signal":
        sig = data.get("signal")
        if sig not in GUARD_SIGNALS:
            raise EventLogError(f"guard_signal: signal {sig!r} not in {GUARD_SIGNALS}")
        if sig == "score" and "score" not in data:
            raise EventLogError("guard_signal: score signal without a score value")
        if "score" in data:
            s = data["score"]
            if (
                isinstance(s, bool)
                or not isinstance(s, (int, float))
                or not math.isfinite(s)
                or not 0.0 <= s <= 1.0
            ):
                raise EventLogError(f"guard_signal: score out of [0, 1]: {s!r}")
    if cls == "policy" and kind == "decision" and data.get("action") not in POLICY_ACTIONS:
        raise EventLogError(
            f"policy.decision: action {data.get('action')!r} not in {POLICY_ACTIONS}"
        )
    if cls == "evaluator" and kind == "outcome" and data.get("outcome") not in ATTACK_OUTCOMES:
        raise EventLogError(
            f"evaluator.outcome: outcome {data.get('outcome')!r} not in {ATTACK_OUTCOMES}"
        )
    if cls == "channel" and kind == "message":
        if data.get("direction") not in CHANNEL_DIRECTIONS:
            raise EventLogError(f"channel.message: direction {data.get('direction')!r}")
        if not isinstance(data.get("text"), str):
            raise EventLogError("channel.message: message text is required")
    if cls == "executor" and kind == "exec_result" and data.get("status") not in ("ok", "refused"):
        raise EventLogError(f"executor.exec_result: status {data.get('status')!r}")
