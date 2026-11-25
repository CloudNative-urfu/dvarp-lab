"""Golden tests of the metric formulas copied from dvarp-prototype @ d5828df.

Synthetic configs with known answers (base prices C_refuse=15, C_manual=2 — the pinned
C_human, issue #11; w_A=0.5):

- g0 (reference): V=0.4, R=0, E=0;
- g_proc: V=0, R=0, E=0.1  → L* = (0.1·2) / (0.5·0.4) = 1.0, threshold;
- g_in:   V=0, R=0.1, E=0.1 → L* = (0.5·0.1·15 + 0.1·2) / 0.2 = 4.75, threshold;
- g_free: V=0, R=0, E=0    → numerator = 0 → pays_at_any_price, L* = 0;
- g_same: V=0.4            → no_safety_gain (ΔV = 0);
- g_neg:  V=0.5            → more_violations (ΔV < 0).

Price bounds (g_proc): low (5, 1) → L* = 0.1/0.2 = 0.5; high (40, 15) → L* = 1.5/0.2 = 7.5.
"""

from __future__ import annotations

import pytest

from services.metrics import formulas


def inp(config, V, R=0.0, E=0.0, w_A=0.5, V_n=20):
    v_k = round(V * V_n)
    return formulas.Inputs(config=config, w_A=w_A, w_L=1 - w_A, V=V, V_k=v_k, V_n=V_n, R=R, E=E)


REF = inp("g0", 0.4)
GOLDEN = {
    "g_proc": inp("g_proc", 0.0, E=0.1),
    "g_in": inp("g_in", 0.0, R=0.1, E=0.1),
    "g_free": inp("g_free", 0.0),
    "g_same": inp("g_same", 0.4),
    "g_neg": inp("g_neg", 0.5),
}
L_STAR_GOLDEN = {"g_proc": 1.0, "g_in": 4.75, "g_free": 0.0}
STATUS_GOLDEN = {
    "g_proc": "threshold",
    "g_in": "threshold",
    "g_free": "pays_at_any_price",
    "g_same": "no_safety_gain",
    "g_neg": "more_violations",
}


@pytest.mark.parametrize("name", sorted(GOLDEN))
def test_l_star_status(name):
    res = formulas.l_star(GOLDEN[name], REF, formulas.base_prices())
    assert res["status"] == STATUS_GOLDEN[name]


@pytest.mark.parametrize("name", sorted(L_STAR_GOLDEN))
def test_l_star_value(name):
    res = formulas.l_star(GOLDEN[name], REF, formulas.base_prices())
    assert res["L_star"] == pytest.approx(L_STAR_GOLDEN[name])


def test_reference_is_itself():
    res = formulas.l_star(REF, REF, formulas.base_prices())
    assert res["status"] == "reference"
    assert res["L_star"] is None


def test_pays_at_threshold():
    res = formulas.l_star(GOLDEN["g_proc"], REF, formulas.base_prices())
    assert not formulas.pays_at(res, 1.0)
    assert formulas.pays_at(res, 1.0 + 1e-9)


def test_delta_net():
    # ΔNet(g_proc) = 0.5·0.4·L_viol − 0.2: zero exactly at the golden threshold.
    assert formulas.delta_net(GOLDEN["g_proc"], REF, formulas.base_prices(), 1.0) == pytest.approx(
        0.0
    )
    assert formulas.delta_net(GOLDEN["g_proc"], REF, formulas.base_prices(), 10.0) > 0


def test_bounds_robust_and_span():
    be = formulas.bounds(
        {k: GOLDEN["g_proc"] for k in ("low", "base", "high")},
        {k: REF for k in ("low", "base", "high")},
    )
    assert be["bounds"]["low"]["L_star"] == pytest.approx(0.5)
    assert be["bounds"]["base"]["L_star"] == pytest.approx(1.0)
    assert be["bounds"]["high"]["L_star"] == pytest.approx(7.5)
    assert be["statuses_over_bounds"] == ["threshold"]
    assert be["prices_robust"] is True
    assert be["decision_at_L_viol"] == {"50": True, "500": True, "5000": True}


def test_bounds_not_robust():
    # Status flips between pays_at_any_price and threshold over the price bounds:
    # refuse term grows with C_refuse, manual term (negative here) shrinks with C_manual.
    ref_busy = inp("g0", 0.4, R=0.4, E=0.4)
    cheap = inp("g_cheap", 0.2, R=0.0, E=1.0)
    be = formulas.bounds(
        {k: cheap for k in ("low", "base", "high")}, {k: ref_busy for k in ("low", "base", "high")}
    )
    assert be["bounds"]["low"]["status"] == "pays_at_any_price"
    assert be["bounds"]["high"]["status"] == "threshold"
    assert be["prices_robust"] is False


def test_detection_golden():
    d = formulas.detection(
        att_detected=[True, True, False, False], legal_detected=[False, False, True, False]
    )
    assert d["TP"] == 2 and d["FN"] == 2 and d["FP"] == 1 and d["TN"] == 3
    assert d["TPR"] == pytest.approx(0.5)
    assert d["FPR"] == pytest.approx(0.25)
    assert d["precision"] == pytest.approx(2 / 3)


def test_detection_empty():
    d = formulas.detection([], [])
    assert d["TPR"] is None and d["FPR"] is None and d["precision"] is None


def test_ppv_golden():
    assert formulas.ppv(0.5, 0.25, 0.5) == pytest.approx(0.5 * 0.5 / (0.25 + 0.125))


def test_seed_spread_golden():
    rows = [
        {"V": 0.4, "R": 0.0, "L_star": 3.0, "status": "threshold", "seed": 1},
        {"V": 0.5, "R": 0.1, "L_star": None, "status": "more_violations", "seed": 2},
    ]
    spread = formulas.seed_spread(rows)
    assert spread["V"]["spread"] == pytest.approx(0.1)
    assert spread["R"]["spread"] == pytest.approx(0.1)
    assert spread["L_star"]["spread"] == pytest.approx(0.0)
    assert spread["status_stable"] is False


def test_seed_spread_needs_two_runs():
    spread = formulas.seed_spread([{"V": 0.4, "R": 0.0, "L_star": 3.0, "status": "threshold"}])
    assert spread["runs"] == 1
