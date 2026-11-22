"""Оси кампании: 4 режима, объём, сид-цикл, guard."""

import pytest

from launcher.axes import GUARD_VOLUME, axis_universe, resolve_axis, resolve_campaign


def test_enum_axis_modes():
    u = axis_universe("configs")
    assert "g0" in u and "configs.lock" not in u
    assert resolve_axis("configs", {"mode": "point", "point": "g0"}) == ["g0"]
    got = resolve_axis("configs", {"mode": "range", "range": ["g0", "g_ctx"]})
    assert got == ["g0", "g0_seed2", "g_ctx"]
    assert resolve_axis("configs", {"mode": "all"}) == u
    limited = resolve_axis("configs", {"mode": "all_limited", "offset": 1, "limit": 2})
    assert limited == u[1:3]
    assert resolve_axis("configs", {"mode": "set", "values": ["g0", "g_out"]}) == ["g0", "g_out"]


def test_numeric_axis_modes():
    assert resolve_axis("seeds", None) == [0]
    assert resolve_axis("episodes", None) == [1]
    assert resolve_axis("seeds", {"mode": "range", "range": [0, 2]}) == [0, 1, 2]
    assert resolve_axis("episodes", {"mode": "all_limited", "offset": 3, "limit": 2}) == [3, 4]
    with pytest.raises(ValueError, match="неограничена"):
        resolve_axis("seeds", {"mode": "all"})


def test_axis_validation():
    with pytest.raises(ValueError, match="отсутствует в frozen"):
        resolve_axis("configs", {"mode": "point", "point": "no_such"})
    with pytest.raises(ValueError, match="границы range"):
        resolve_axis("configs", {"mode": "range", "range": ["g0", "no_such"]})
    with pytest.raises(ValueError):
        resolve_axis("configs", {"mode": "point", "point": 42})


def test_tactics_split_filter():
    all_t = resolve_axis("tactics", {"mode": "all"})
    dev_t = resolve_axis("tactics", {"mode": "all", "split": "dev"})
    assert set(dev_t) <= set(all_t)
    assert {"third_party_emergency", "authority_impersonation"} <= set(all_t)


def test_campaign_volume_and_guard():
    camp = resolve_campaign(
        {
            "configs": {"mode": "point", "point": "g0"},
            "styles": {"mode": "point", "point": "patient"},
            "tactics": {"mode": "point", "point": "direct_task"},
            "agent_models": {"mode": "point", "point": "PLACEHOLDER-agent-1"},
            "episodes": {"mode": "point", "point": 2},
            "seeds": {"mode": "range", "range": [0, 2]},
        }
    )
    cells, episodes = camp.volume()
    assert cells == 3  # 3 сида × 1 × 1 × 1
    assert episodes == 6  # × 2 эпизода
    assert len(camp.cells()) == 3
    assert camp.cells()[1]["seed"] == 1
    assert episodes > GUARD_VOLUME or GUARD_VOLUME == 1000
