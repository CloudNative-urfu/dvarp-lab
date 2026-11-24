"""Remote-LLM: обход локальности, пины в сырых данных, пропуск в метриках, клиент прокси."""

import pytest
from fastapi.testclient import TestClient

from lab import nominal
from launcher.campaign import run_campaign
from services.filter import app as filter_app
from services.metrics import app as metrics_app


def test_nominal_remote_flag_bypasses_host_check(tmp_path):
    config = {"llm": {"base_url": "https://aitunnel.example/v1"}}
    strict = nominal.check_config("g0", config, [])
    assert any("не локальный контур" in p for p in strict)
    relaxed = nominal.check_config("g0", config, [], allow_remote=True)
    assert all("не локальный контур" not in p for p in relaxed)
    assert any("REMOTE LLM" in p for p in relaxed)  # пин предупреждением


def test_campaign_remote_pin_in_manifest_and_records(tmp_path, monkeypatch):
    monkeypatch.setenv("LAB_RUNS_DIR", str(tmp_path / "runs"))

    class FakeSvc:
        def __init__(self):
            self.calls = []

        def post(self, path, json=None):
            self.calls.append((path, json))
            if path == "/snapshot":
                return {"snapshot_id": "s1"}
            if path == "/run-episode":
                return {"outcome": "budget_exhausted", "turns": 1, "attempts": 1}
            return {"ok": True}

    svcs = {k: FakeSvc() for k in ("shop", "traffic", "attack", "metrics")}
    manifest = run_campaign(
        {
            "configs": {"mode": "point", "point": "g0"},
            "styles": {"mode": "point", "point": "patient"},
            "tactics": {"mode": "point", "point": "direct_task"},
            "agent_models": {"mode": "point", "point": "PLACEHOLDER-agent-1"},
            "episodes": {"mode": "point", "point": 1},
            "seeds": {"mode": "point", "point": 0},
            "budget": 2,
            "allow_remote_llm": True,
        },
        services=svcs,
    )
    assert manifest["remote_llm"] is True
    traffic_body = svcs["traffic"].calls[0][1]
    attack_body = svcs["attack"].calls[0][1]
    assert traffic_body["remote_llm"] is True and attack_body["remote_llm"] is True


def test_remote_model_outside_roster_gets_verification_spec(tmp_path, monkeypatch):
    monkeypatch.setenv("LAB_RUNS_DIR", str(tmp_path / "runs"))

    class FakeSvc:
        def post(self, path, json=None):
            if path == "/snapshot":
                return {"snapshot_id": "s1"}
            if path == "/run-episode":
                return {"outcome": "budget_exhausted", "turns": 1, "attempts": 1}
            return {"ok": True}

    manifest = run_campaign(
        {
            "configs": {"mode": "point", "point": "g0"},
            "styles": {"mode": "point", "point": "patient"},
            "tactics": {"mode": "point", "point": "direct_task"},
            "agent_models": {"mode": "point", "point": "openai/gpt-4o-mini"},
            "episodes": {"mode": "point", "point": 1},
            "seeds": {"mode": "point", "point": 0},
            "budget": 2,
            "allow_remote_llm": True,
        },
        services={k: FakeSvc() for k in ("shop", "traffic", "attack", "metrics")},
    )
    cell = manifest["cells"][0]
    assert cell["agent_model"] == {
        "name": "openai/gpt-4o-mini",
        "role": "agent",
        "params_b": None,
        "revision": "remote-verification",
    }


def test_remote_models_off_roster_in_campaign_agent_and_attacker(tmp_path, monkeypatch):
    monkeypatch.setenv("LAB_RUNS_DIR", str(tmp_path / "runs"))

    class FakeSvc:
        def post(self, path, json=None):
            if path == "/snapshot":
                return {"snapshot_id": "s1"}
            if path == "/run-episode":
                return {"outcome": "budget_exhausted", "turns": 1, "attempts": 1}
            return {"ok": True}

    manifest = run_campaign(
        {
            "configs": {"mode": "point", "point": "g0"},
            "styles": {"mode": "point", "point": "patient"},
            "tactics": {"mode": "point", "point": "direct_task"},
            "agent_models": {"mode": "point", "point": "proxy/agent-x"},
            "attacker_models": {"mode": "point", "point": "proxy/attacker-y"},
            "episodes": {"mode": "point", "point": 1},
            "seeds": {"mode": "point", "point": 0},
            "budget": 2,
            "allow_remote_llm": True,
        },
        services={k: FakeSvc() for k in ("shop", "traffic", "attack", "metrics")},
    )
    cell = manifest["cells"][0]
    assert cell["agent_model"]["revision"] == "remote-verification"
    assert cell["attacker_model"] == {
        "name": "proxy/attacker-y",
        "role": "attacker",
        "params_b": None,
        "revision": "remote-verification",
    }


def test_probe_remote_model_off_roster(tmp_path, monkeypatch):
    from launcher.campaign import probe

    class FakeSvc:
        def post(self, path, json=None):
            if path == "/run-episode":
                return {"outcome": "budget_exhausted", "turns": 1, "attempts": 1}
            return {"ok": True}

    result = probe(
        {
            "config": "g0",
            "tactic": "direct_task",
            "agent_model": "proxy/agent-x",
            "allow_remote_llm": True,
        },
        services={k: FakeSvc() for k in ("shop", "traffic", "attack", "metrics")},
    )
    assert result["outcome"] == "budget_exhausted"


def test_axes_set_mode_accepts_off_roster_models_only_with_remote():
    from launcher.axes import resolve_axis

    axis = {"mode": "set", "values": ["proxy/agent-x", "proxy/agent-y"]}
    with pytest.raises(ValueError, match="отсутствуют в frozen"):
        resolve_axis("agent_models", axis)
    assert resolve_axis("agent_models", axis, allow_remote=True) == [
        "proxy/agent-x",
        "proxy/agent-y",
    ]
    with pytest.raises(ValueError, match="отсутствуют в frozen"):
        resolve_axis("configs", {"mode": "set", "values": ["no-such"]}, allow_remote=True)


def test_openai_complete_sends_model_and_bearer(monkeypatch):
    import services.traffic.record as rec

    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": "ok"}}]}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured.update({"url": url, "json": json, "headers": headers})
        return FakeResponse()

    monkeypatch.setattr(rec.httpx, "post", fake_post)
    complete = rec._openai_complete(
        "https://api.aitunnel.ru/v1", model="openai/gpt-4o-mini", api_key="sk-test"
    )
    assert complete([{"role": "user", "content": "hi"}]) == "ok"
    assert captured["json"]["model"] == "openai/gpt-4o-mini"
    assert captured["headers"]["Authorization"] == "Bearer sk-test"
    assert captured["url"].endswith("/chat/completions")


def test_shop_agent_remote_env_bypass(tmp_path, monkeypatch):
    from services.shop.llm.settings import LLMSettings

    env = {
        "RESEARCH_LLM_BASE_URL": "https://api.aitunnel.ru/v1",
        "RESEARCH_LLM_MODEL": "openai/gpt-4o-mini",
        "RESEARCH_LLM_PARAMS_B": "100",
        "RESEARCH_LLM_API_KEY": "sk-test",
        "LAB_ALLOW_REMOTE_LLM": "1",
    }
    s = LLMSettings.from_env(env)
    assert s.base_url == "https://api.aitunnel.ru/v1"
    assert s.has_api_key and s.auth_headers()["Authorization"] == "Bearer sk-test"
    with pytest.raises(Exception, match="не адрес локального контура"):
        LLMSettings.from_env({k: v for k, v in env.items() if k != "LAB_ALLOW_REMOTE_LLM"})


def test_metrics_skips_remote_records(tmp_path, monkeypatch):
    monkeypatch.setenv("LAB_RAW_DB_URL", f"sqlite:///{tmp_path}/raw.db")
    monkeypatch.setenv("LAB_METRICS_DB_URL", f"sqlite:///{tmp_path}/metrics.db")
    fclient = TestClient(filter_app.app)
    client = TestClient(metrics_app.app)
    base = {
        "episode_id": "e1",
        "channel": "attack",
        "turn": 0,
        "text": "hi",
        "model_spec": {"name": "m", "role": "attacker", "params_b": 8, "revision": "r"},
        "snapshot": {},
        "config_name": "g0",
        "raw": {
            "verdict": {"violation": True, "outcome": "x", "task_status": None, "escalated": False},
            "guard_signals": {"flagged": 1},
        },
    }
    for probe in (False, True):
        for remote in (False, True):
            r = dict(
                base,
                episode_id=f"e-probe{probe}-remote{remote}",
                raw={
                    **base["raw"],
                    **({"probe": True} if probe else {}),
                    **({"remote_llm": True} if remote else {}),
                },
            )
            assert fclient.post("/record", json=r).status_code == 200

    n_attack = lambda: [
        r["value"] for r in client.get("/metrics/g0").json()["results"] if r["metric"] == "n_attack"
    ]
    client.post("/compute", json={"config_name": "g0"})
    assert n_attack() == [1]  # по умолчанию: только обычный эпизод
    client.post("/compute", json={"config_name": "g0", "include_remote": True})
    assert n_attack() == [2]  # + remote-эпизод (probe по-прежнему исключён)
    client.post(
        "/compute", json={"config_name": "g0", "include_remote": True, "include_probe": True}
    )
    assert n_attack() == [4]  # все четыре эпизода
