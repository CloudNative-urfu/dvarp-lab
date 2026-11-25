"""Cost accounting (issue #11): economics pin, post-hoc C_ep/C_guard from saved events.

- Frozen pin `frozen/economics.json`: declared market-average tariffs (agent 0.50/1.50,
  guard 0.15/0.15 per 1M), C_human=2, C_churn=20, p_att scenarios;
- defender-borne costs come from `raw.events` of the raw DB (NFR-2.9): agent `llm_call`
  → C_ep; `guard:*` signals/errors → C_guard (CPU of non-LLM guards — time, never money);
- attacker-side `llm_call` events are self-limited and excluded from both.
"""

from __future__ import annotations

import pytest

from services.metrics import economics, extract, formulas
from tests.test_metrics_golden import REF


# --------------------------------------------------------------------------- economics pin
def test_pin_values_match_issue_11():
    pin = economics.load_economics()
    assert pin["agent_tariff"] == (0.5, 1.5)
    assert pin["guard_tariff"] == (0.15, 0.15)
    assert pin["C_human"] == 2.0
    assert pin["C_churn"] == 20.0
    assert pin["p_att_scenarios"] == [0.01, 0.03, 0.1]
    assert pin["price_sensitivity_factors"] == [0.5, 2.0]


def test_pin_rejects_broken_values(tmp_path):
    bad = tmp_path / "economics.json"
    bad.write_text('{"schema": "darp-economics-1", "agent_tariff": {"input_per_million": -1}}')
    with pytest.raises(ValueError):
        economics.load_economics(bad)


def test_money_conversion():
    assert economics.money({"tokens_in": 1_000_000, "tokens_out": 1_000_000}, (0.5, 1.5)) == 2.0
    assert economics.money({}, (0.15, 0.15)) == 0.0


# ---------------------------------------------------------------------------- episode costs
def _ev(component, kind, cost):
    return {"component": component, "kind": kind, "cost": cost}


def test_episode_costs_defender_only():
    events = [
        _ev("agent", "llm_call", {"tokens_in": 1_000_000, "tokens_out": 2_000_000}),
        _ev("attacker", "llm_call", {"tokens_in": 10_000_000, "tokens_out": 10_000_000}),
        _ev("guard:input-filter", "guard_signal", {"tokens_in": 1_000_000, "cpu_ms": 5.0}),
        _ev("guard:deberta", "guard_error", {"tokens_in": 1_000_000, "cpu_ms": 7.0}),
        _ev("policy", "decision", {"tokens_in": 9_999_999}),
    ]
    costs = extract._episode_costs(events)
    # agent: 1M in × 0.5 + 2M out × 1.5 = 3.5; attacker excluded (NFR-2.9)
    assert costs["c_ep"] == pytest.approx(3.5)
    # guard: 2M tokens × 0.15/1M = 0.3; cpu stays as time
    assert costs["c_guard"] == pytest.approx(0.3)
    assert costs["guard_cpu_ms"] == pytest.approx(12.0)


def test_episode_costs_empty_and_no_events():
    assert extract._episode_costs([]) == {"c_ep": 0.0, "c_guard": 0.0, "guard_cpu_ms": 0.0}


# ------------------------------------------------- end-to-end: costs enter L* through /compute
@pytest.mark.asyncio
async def test_costs_flow_into_break_even(filter_client, metrics_client):
    await _seed_cost_grid(filter_client, config="g0", tokens=0, guard=0)
    await _seed_cost_grid(filter_client, config="g_cost", tokens=1_000_000, guard=1_000_000)
    r = await metrics_client.post("/compute", json={})
    r.raise_for_status()
    # per attack episode: 1M in × 0.5/1M = 0.5 (C_ep), 1M × 0.15/1M = 0.15 (C_guard);
    # mean over 8 episodes (4 attacks + 4 legal, legal costs zero) → 0.25 / 0.075.
    assert await _lookup_c(metrics_client, "g_cost", "C_ep") == pytest.approx(0.25)
    assert await _lookup_c(metrics_client, "g_cost", "C_guard") == pytest.approx(0.075)
    assert await _lookup_c(metrics_client, "g0", "C_ep") == pytest.approx(0.0)

    # numerator = attack_service (0.5·0.25) + guard (0.075) = 0.2; dV = 0.5
    # → L* = 0.2 / (0.5·0.5) = 0.8.
    assert await _lookup_c(metrics_client, "g_cost", "L_star") == pytest.approx(0.8)


async def _seed_cost_grid(client, *, config, tokens, guard):
    cost_agent = (
        {"tokens_in": tokens, "tokens_out": 0, "requests": 1, "latency_ms": 1.0} if tokens else None
    )
    cost_guard = (
        {"tokens_in": guard, "tokens_out": 0, "requests": 1, "cpu_ms": 3.0} if guard else None
    )
    events = []
    if cost_agent:
        events.append(_ev("agent", "llm_call", cost_agent))
        events.append(_ev("attacker", "llm_call", {"tokens_in": 999_999, "tokens_out": 0}))
    if cost_guard:
        events.append(_ev("guard:input-filter", "guard_signal", cost_guard))
    from .conftest import make_raw, record_turn

    legal = make_raw(
        config_name=config,
        extra={
            "verdict": {
                "violation": False,
                "outcome": "refused",
                "task_status": "completed",
                "escalated": False,
            }
        },
    )
    for i in range(4):
        atk = make_raw(
            config_name=config,
            extra={
                "events": events,
                "verdict": {
                    "violation": config == "g0" and i < 2,  # g0: V=0.5 reference; g_cost: V=0.0
                    "outcome": "executed" if config == "g0" and i < 2 else "refused",
                    "task_status": "refund_granted",
                    "escalated": False,
                },
            },
        )
        await record_turn(
            client,
            episode_id=f"{config}-a{i}",
            turn=i,
            channel="attack",
            text=f"attack {i}",
            config_name=config,
            raw=atk,
        )
        await record_turn(
            client,
            episode_id=f"{config}-l{i}",
            turn=i,
            channel="legal",
            text=f"legal {i}",
            config_name=config,
            raw=legal,
        )


async def _lookup_c(client, config, metric):
    r = await client.get(f"/metrics/{config}")
    r.raise_for_status()
    vals = [row["value"] for row in r.json()["results"] if row["metric"] == metric]
    assert len(vals) == 1
    return vals[0]


# ------------------------------------------------------------------- formulas with non-zero costs
def _inputs_c(config, V, R=0.0, E=0.0, c_ep=0.0, c_guard=0.0):
    return formulas.Inputs(
        config=config,
        w_A=0.5,
        w_L=0.5,
        V=V,
        V_k=round(V * 20),
        V_n=20,
        R=R,
        E=E,
        C_ep=c_ep,
        C_guard=c_guard,
    )


def test_terms_with_costs():
    t = formulas.terms(
        _inputs_c("g_cost", 0.2, c_ep=1.0, c_guard=0.15), REF, formulas.base_prices()
    )
    assert t["dC_ep"] == pytest.approx(1.0)
    assert t["dC_guard"] == pytest.approx(0.15)
    assert t["attack_service"] == pytest.approx(0.5)
    assert t["guard"] == pytest.approx(0.15)


def test_l_star_with_costs_golden():
    g = _inputs_c("g_cost", 0.0, E=0.1, c_ep=1.0, c_guard=0.15)
    res = formulas.l_star(g, REF, formulas.base_prices())
    # numerator = 0 (refuse) + 0.5·1.0 (attack_service) + 0.15 (guard) + 0.1·2 (manual) = 0.85
    assert res["numerator"] == pytest.approx(0.85)
    assert res["L_star"] == pytest.approx(0.85 / (0.5 * 0.4))
