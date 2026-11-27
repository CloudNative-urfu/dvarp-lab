"""run_campaign по фейковым сервисам: configure, сид-цикл, манифест, guard, probe."""

import json

import pytest

from launcher import probe as launcher_probe
from launcher import run_campaign


class FakeSvc:
    def __init__(self, script=None):
        self.calls = []
        self.script = list(script or [])

    def post(self, path, json=None):
        self.calls.append(("POST", path, json))
        if self.script:
            return self.script.pop(0)
        if path == "/run-episode":
            return {"outcome": "budget_exhausted", "turns": 1, "attempts": 1}
        if path == "/snapshot":
            return {"snapshot_id": "snap-1", "state_hash": "snap-1", "label": json["label"]}
        if path == "/reset":
            return {"ok": True, "world": "world_a", "dataset_hash": "hash-a"}
        if path in ("/configure", "/snapshot/restore", "/compute"):
            return {"ok": True}
        return {}

    def get(self, path, **params):
        self.calls.append(("GET", path, params))
        if path == "/metrics/g0":
            return {"config_name": "g0", "results": []}
        if path == "/text/e1":
            return {"turns": []}
        if path == "/chain/verify":
            return {"defects": []}
        if path == "/health":
            return {"status": "ok"}
        return {}


SPEC = {
    "configs": {"mode": "point", "point": "g0"},
    "goals": {"mode": "point", "point": "refund_expired"},
    "styles": {"mode": "point", "point": "patient"},
    "tactics": {"mode": "point", "point": "direct_task"},
    "agent_models": {"mode": "point", "point": "PLACEHOLDER-agent-1"},
    "episodes": {"mode": "point", "point": 1},
    "seeds": {"mode": "range", "range": [0, 1]},
    "budget": 3,
}


def test_campaign_configure_seed_loop_manifest(tmp_path, monkeypatch):
    monkeypatch.setenv("LAB_RUNS_DIR", str(tmp_path / "runs"))
    shop, traffic, attack, metrics = FakeSvc(), FakeSvc(), FakeSvc(), FakeSvc()
    svcs = {"shop": shop, "traffic": traffic, "attack": attack, "metrics": metrics}
    manifest = run_campaign(SPEC, services=svcs)
    # порядок ячейки: reset (инициализирует журнал) → configure (пин модели)
    pair_calls = [(c[1], c[2]) for c in shop.calls if c[1] in ("/reset", "/configure")]
    assert pair_calls[0][0] == "/reset" and pair_calls[1][0] == "/configure"
    assert pair_calls[1][1]["config_name"] == "g0"
    assert pair_calls[1][1]["agent_model"]["name"] == "PLACEHOLDER-agent-1"
    # сид-цикл: 2 ячейки с сидами 0 и 1
    seeds = [c["seed"] for c in manifest["cells"]]
    assert seeds == [0, 1]
    # манифест пиннит оси, сид и мир каждой пары
    assert manifest["axes"]["seeds"] == [0, 1]
    assert manifest["axes"]["goals"] == ["refund_expired"]
    assert manifest["cells"][0]["episodes"][0]["episode"] == 1
    # эпизоды: legal + attack на каждую пару
    assert len(attack.calls) == 2
    body = attack.calls[0][2]
    assert body["goal"] == "refund_expired"
    assert body["style"] == "patient" and body["run_id"] == manifest["run_id"]
    assert [c[2]["group_seed"] for c in traffic.calls] == [0, 1]
    assert [c[2]["group_seed"] for c in attack.calls] == [0, 1]
    mf = json.loads(
        (tmp_path / "runs" / manifest["run_id"] / "manifest.json").read_text(encoding="utf-8")
    )
    assert mf["run_id"] == manifest["run_id"]
    # пин версии замороженного мира: из ответа /reset каждой ячейки
    assert manifest["world"] == {"name": "world_a", "dataset_hash": "hash-a"}
    assert mf["world"] == manifest["world"]


def test_campaign_guard_needs_confirm(tmp_path, monkeypatch):
    monkeypatch.setenv("LAB_RUNS_DIR", str(tmp_path / "runs"))
    big = dict(SPEC)
    big["seeds"] = {"mode": "range", "range": [0, 999]}
    big["episodes"] = {"mode": "range", "range": [1, 3]}
    shop, traffic, attack = FakeSvc(), FakeSvc(), FakeSvc()
    result = run_campaign(
        big, services={"shop": shop, "traffic": traffic, "attack": attack, "metrics": FakeSvc()}
    )
    assert result.get("needs_confirm") is True
    assert result["episodes"] > 1000
    assert attack.calls == []  # ничего не запустилось без подтверждения
    ok = run_campaign(
        {**big, "confirm": True},
        services={"shop": shop, "traffic": traffic, "attack": attack, "metrics": FakeSvc()},
    )
    assert ok["cells"]


def test_probe_marks_raw_and_skips_manifest(tmp_path, monkeypatch):
    monkeypatch.setenv("LAB_RUNS_DIR", str(tmp_path / "runs"))
    shop, attack = FakeSvc(), FakeSvc()
    result = launcher_probe(
        {
            "config": "g0",
            "goal": "refund_expired",
            "tactic": "direct_task",
            "budget": 2,
            "agent_model": "PLACEHOLDER-agent-1",
        },
        services={"shop": shop, "attack": attack},
    )
    assert result["outcome"] == "budget_exhausted"
    assert shop.calls[0][1] == "/reset"
    assert shop.calls[1][1] == "/configure"
    assert attack.calls[0][2]["goal"] == "refund_expired"
    assert not list((tmp_path / "runs").glob("*/manifest.json"))  # манифест не пишется


def test_probe_requires_goal():
    shop, attack = FakeSvc(), FakeSvc()
    with pytest.raises(SystemExit, match="цель"):
        launcher_probe(
            {
                "config": "g0",
                "tactic": "direct_task",
                "budget": 2,
                "agent_model": "PLACEHOLDER-agent-1",
            },
            services={"shop": shop, "attack": attack},
        )


def test_attack_ids_unique_on_full_grid(tmp_path, monkeypatch):
    """#20/#50: id обеих ног пары — от полной сценарной сигнатуры ячейки."""
    monkeypatch.setenv("LAB_RUNS_DIR", str(tmp_path / "runs"))
    spec = {
        **SPEC,
        "styles": {"mode": "all"},
        "tactics": {"mode": "all"},
        "episodes": {"mode": "point", "point": 2},
        "seeds": {"mode": "point", "point": 0},
        "confirm": True,
    }
    svcs = {k: FakeSvc() for k in ("shop", "traffic", "attack", "metrics")}
    manifest = run_campaign(spec, services=svcs)
    styles, tactics = manifest["axes"]["styles"], manifest["axes"]["tactics"]
    assert len(styles) > 1 and len(tactics) > 1
    eps = [e for c in manifest["cells"] for e in c["episodes"]]
    attack_ids = [e["attack_episode_id"] for e in eps]
    n_cells = len(styles) * len(tactics) * 2  # × 1 цель SPEC
    assert len(attack_ids) == n_cells == len(set(attack_ids))
    # legal id несёт ту же сигнатуру, что и attack id пары (dvarp-lab#50)
    legal_ids = [e["legal_episode_id"] for e in eps]
    assert len(legal_ids) == n_cells == len(set(legal_ids))
    assert {
        lid.replace(f"-L{i}-", f"-A{i}-", 1)
        for lid, i in zip(legal_ids, [e["episode"] for e in eps])
    } == set(attack_ids)
    attack_calls = [c[2] for c in svcs["attack"].calls if c[1] == "/run-episode"]
    assert [c["episode_id"] for c in attack_calls] == attack_ids
    assert len({c["seed"] for c in attack_calls}) == len(attack_calls)
    # у каждой пары живы обе ноги
    legal_calls = [c for c in svcs["traffic"].calls if c[1] == "/run-episode"]
    assert len(legal_calls) == len(attack_calls)


def test_attack_id_picks_up_new_axes():
    from launcher.campaign import attack_episode_id

    cell = {"config": "g0", "style": "patient", "tactic": "t", "goal": "refund", "seed": 3}
    cell |= {"agent_model": "m", "attacker_model": None}
    assert attack_episode_id("r", 1, cell) == "r-A1-patient-t-refund-s3"
