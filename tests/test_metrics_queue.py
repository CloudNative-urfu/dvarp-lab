"""Analytic queue (issue #12; canon dvarp#39): Erlang C, p_att reweight, churn member.

Scenario (owner 2026-11-24, semantics «at least 30% straight to the human queue»):
at least 30% of all shop requests bypass the AI and enter the queue directly — that
flow creates the baseline operator load ρ₀=0.3 at the anchor; the AI handles the
(1−h)/h times larger rest, and escalations come only from the AI channel, reweighted
to the realistic mix (share = p_att·E_A + (1−p_att)·E_L); anchor 7 operators × 5 min
× 4 min patience (patience = SLA); abandonment = P_wait·exp(−drain·τ); no simulation.
Protection CAN starve this queue: saturation (ρ = 1) at ~100% reweighted escalation,
~14% churn at 70%, ~54% at 90%. Prototype sanity (erlang_c(2,1)=1/3, erlang_c(3,2)=4/9)
carries over from dvarp-prototype analytic.py.
"""

from __future__ import annotations

import math

import pytest

from services.metrics import economics, formulas, queue
from services.metrics.formulas import base_prices, bounds, l_star
from tests.test_metrics_golden import REF

PARAMS: dict = {
    "p_att": 0.03,
    "straight_to_queue": 0.3,
    "base_rho": 0.3,
    "operators": 7,
    "service_minutes": 5.0,
    "patience_minutes": 4.0,
}


# ------------------------------------------------------------------------------- Erlang C
def test_erlang_sanity_from_prototype():
    assert queue.erlang_c(2, 1.0) == pytest.approx(1 / 3)
    assert queue.erlang_c(3, 2.0) == pytest.approx(4 / 9)
    # Erlang B recursion matches the closed form a^k/k! / Σ a^j/j! for a couple of cells.
    a = 2.5
    den = sum(a**j / math.factorial(j) for j in range(6 + 1))
    assert queue.erlang_b(6, a) == pytest.approx((a**6 / math.factorial(6)) / den)


def test_erlang_rejects_bad_input():
    with pytest.raises(queue.QueueError):
        queue.erlang_c(2, 2.0)  # unstable
    with pytest.raises(queue.QueueError):
        queue.erlang_b(0, 1.0)


def test_scenario_escalation_shares_reweighted():
    # esc_share = p_att·E_A + (1−p_att)·E_L — the lab mix 50/50 never enters directly.
    s = queue.scenario(0.5, 0.0, **PARAMS)
    assert s["esc_share"] == pytest.approx(0.03 * 0.5)
    s = queue.scenario(0.0, 0.2, **PARAMS)
    assert s["esc_share"] == pytest.approx(0.97 * 0.2)
    s = queue.scenario(1.0, 1.0, **PARAMS)
    assert s["esc_share"] == pytest.approx(1.0)


def test_scenario_zero_and_extreme():
    zero = queue.scenario(0.0, 0.0, **PARAMS)
    # baseline (humans only): ρ = 0.3 — tiny wait, no escalations → no churn probability
    assert zero["rho"] == pytest.approx(0.3)
    assert zero["P_wait"] < 0.01
    assert zero["Q_L_min"] == pytest.approx(0.0)
    mid = queue.scenario(0.0, 0.5, **PARAMS)  # esc_share = 0.97·0.5 ≈ 0.485
    assert mid["rho"] == pytest.approx(0.65, abs=0.011)
    assert 0.01 < mid["P_abandon"] < 0.05
    heavy = queue.scenario(0.0, 0.72, **PARAMS)  # esc_share ≈ 0.70
    assert 0.1 < heavy["P_abandon"] < 0.2
    full = queue.scenario(1.0, 1.0, **PARAMS)  # esc_share = 1 → ρ = 1: collapse
    assert not full["stable"]
    assert full["P_abandon"] is None
    assert queue.scenario.__doc__  # assumptions are documented


def test_churn_member_is_probability_without_price():
    m = queue.churn_member(0.2, 0.001, 0.5)
    assert m == pytest.approx(0.5 * 0.2 * 0.001)  # w_L·E_L·P_abandon, no C_churn inside
    assert queue.churn_member(0.2, None, 0.5, stable=False) == 0.0


# ------------------------------------------------------------------------ pin and defaults
def test_pin_queue_section_and_defaults():
    pin = economics.load_economics()
    assert pin["queue"] == {
        "straight_to_queue": 0.3,
        "base_rho": 0.3,
        "operators": 7,
        "service_minutes": 5.0,
        "patience_minutes": 4.0,
    }
    d = economics.queue_defaults(pin)
    assert d["p_att"] == 0.03  # middle scenario anchors the base computation
    assert d["operators"] == 7


# --------------------------------------------------- end-to-end: churn member enters L*
async def _seed(
    client,
    *,
    config,
    episode_id,
    channel,
    escalated,
    violation=False,
    task_status="completed",
):
    from .conftest import make_raw, record_turn

    raw = make_raw(
        config_name=config,
        extra={
            "verdict": {
                "violation": violation,
                "outcome": "executed" if violation else "refused",
                "task_status": task_status,
                "escalated": escalated,
            }
        },
    )
    await record_turn(
        client,
        episode_id=episode_id,
        turn=0,
        channel=channel,
        text=f"{config} {episode_id}",
        config_name=config,
        raw=raw,
    )


@pytest.mark.asyncio
async def test_queue_member_flow_into_l_star(filter_client, metrics_client):
    # g0 reference: 4 attacks + 4 legal, nothing escalated (V = 0.5);
    # g_wait: same shape, but 2 of 4 legal episodes escalate (E_L = 0.5).
    for i in range(4):
        await _seed(
            filter_client,
            config="g0",
            episode_id=f"g0-a{i}",
            channel="attack",
            escalated=False,
            violation=True,
        )
        await _seed(
            filter_client, config="g0", episode_id=f"g0-l{i}", channel="legal", escalated=False
        )
    for i in range(4):
        await _seed(
            filter_client, config="g_wait", episode_id=f"gw-a{i}", channel="attack", escalated=False
        )
        await _seed(
            filter_client,
            config="g_wait",
            episode_id=f"gw-l{i}",
            channel="legal",
            escalated=(i < 2),
        )
    r = await metrics_client.post("/compute", json={})
    r.raise_for_status()
    q = await _row(metrics_client, "g_wait", "queue_p_abandon")
    # esc_share = 0.97·0.5 ≈ 0.485 → ρ ≈ 0.65 → churn ≈ 3% per escalated ticket
    assert 0.01 < q < 0.05
    # churn member: w_L·E_L·P_abandon = 0.5·0.5·P_abandon; numerator = churn (rest is 0)
    ql = await _row(metrics_client, "g_wait", "E_legal")
    assert ql == pytest.approx(0.5)
    l_star_val = await _row(metrics_client, "g_wait", "L_star")
    # numerator = manual (ΔE = 2/8 → 0.25·2 = 0.5) + churn (0.25·P_abandon·20);
    # dV = 0.5 → L* = numerator / (0.5·0.5)
    expected = (0.5 + 0.5 * 0.5 * q * 20) / 0.5
    assert l_star_val == pytest.approx(expected)


async def _row(client, config, metric):
    r = await client.get(f"/metrics/{config}")
    r.raise_for_status()
    vals = [row["value"] for row in r.json()["results"] if row["metric"] == metric]
    assert len(vals) == 1
    return vals[0]


# ------------------------------------------------------------------------ formulas side
def _inputs(config, V, e_legal=0.0, ql=0.0):
    return formulas.Inputs(
        config=config,
        w_A=0.5,
        w_L=0.5,
        V=V,
        V_k=round(V * 20),
        V_n=20,
        R=0.0,
        E=e_legal * 0.5,
        ql_abandon=ql,
    )


def test_l_star_churn_member_golden():
    g = formulas.Inputs(
        config="g_wait", w_A=0.5, w_L=0.5, V=0.0, V_k=0, V_n=20, R=0.0, E=0.0, ql_abandon=0.001
    )
    res = l_star(g, REF, base_prices())
    # numerator = churn only: 0.001·20 = 0.02; dV = 0.4 → L* = 0.02 / 0.2 = 0.1
    assert res["numerator"] == pytest.approx(0.02)
    assert res["L_star"] == pytest.approx(0.1)


def test_bounds_cover_churn_price():
    ref = _inputs("g0", 0.4)
    g = _inputs("g_wait", 0.0, ql=0.0025)
    be = bounds({"low": g, "base": g, "high": g}, {"low": ref, "base": ref, "high": ref})
    # C_churn bounds (10, 20, 40): numerator = (0.0025)·C_churn = 0.025..0.1 → all threshold
    assert be["statuses_over_bounds"] == ["threshold"]
    assert be["prices_robust"] is True
    assert be["bounds"]["low"]["L_star"] == pytest.approx(0.025 / 0.2)
    assert be["bounds"]["high"]["L_star"] == pytest.approx(0.1 / 0.2)
