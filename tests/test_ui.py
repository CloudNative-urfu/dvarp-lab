"""UI-сервис: meta, жизненный цикл run, объём, прокси, статическая страница."""

import json

import pytest
from fastapi.testclient import TestClient

from services.ui import app as ui_app


@pytest.fixture()
def client(monkeypatch):
    return TestClient(ui_app.app)


def test_meta_lists_frozen_and_guard(client):
    m = client.get("/api/meta").json()
    assert "g0" in m["configs"]
    assert "patient" in m["styles"]
    assert "third_party_emergency" in m["tactics"]
    assert m["guard"] == 1000
    assert set(m["health"]) == {"shop", "traffic", "attack", "filter", "metrics"}


def test_volume_endpoint(client):
    r = client.post(
        "/api/volume",
        json={
            "spec": {
                "configs": {"mode": "point", "point": "g0"},
                "styles": {"mode": "point", "point": "patient"},
                "tactics": {"mode": "point", "point": "direct_task"},
                "agent_models": {"mode": "point", "point": "PLACEHOLDER-agent-1"},
                "episodes": {"mode": "point", "point": 2},
                "seeds": {"mode": "range", "range": [0, 1]},
            }
        },
    ).json()
    assert r == {"cells": 2, "episodes": 4}


def test_run_lifecycle_with_fake_campaign(client, monkeypatch):
    calls = []

    def fake_run_campaign(spec, *, progress=None, services=None):
        calls.append(spec)
        if progress:
            progress(
                {
                    "stage": "episode",
                    "cells_done": 1,
                    "cells_total": 1,
                    "episodes_total": 1,
                    "current": {"scenario": {"style": "patient", "tactic": "direct_task"}},
                }
            )
        return {"run_id": "run-x", "cells": [], "axes": {}, "episodes": [1]}

    monkeypatch.setattr(ui_app, "run_campaign", fake_run_campaign)
    r = client.post(
        "/api/run",
        json={
            "configs": {"mode": "point", "point": "g0"},
            "styles": {"mode": "point", "point": "patient"},
            "tactics": {"mode": "point", "point": "direct_task"},
            "agent_models": {"mode": "point", "point": "PLACEHOLDER-agent-1"},
            "episodes": {"mode": "point", "point": 1},
            "seeds": {"mode": "point", "point": 0},
            "budget": 3,
        },
    )
    assert r.json() == {"started": True, "episodes": 1}
    for _ in range(50):
        s = client.get("/api/run/status").json()
        if s.get("status") in ("done", "error"):
            break
    assert s["status"] == "done"
    assert s["manifest"]["run_id"] == "run-x"
    assert calls and calls[0]["budget"] == 3
    # второй запуск во время выполняющегося запрещён (пока статус done — уже свободен)
    r2 = client.post(
        "/api/run",
        json={
            "configs": {"mode": "point", "point": "g0"},
            "styles": {"mode": "point", "point": "patient"},
            "tactics": {"mode": "point", "point": "direct_task"},
            "agent_models": {"mode": "point", "point": "PLACEHOLDER-agent-1"},
            "episodes": {"mode": "point", "point": 1},
            "seeds": {"mode": "point", "point": 0},
        },
    )
    assert r2.status_code == 200


def test_run_rejects_while_running(client, monkeypatch):
    import time as _time

    def slow_campaign(spec, *, progress=None, services=None):
        _time.sleep(0.6)
        return {"run_id": "run-slow", "cells": [], "axes": {}, "episodes": [1]}

    monkeypatch.setattr(ui_app, "run_campaign", slow_campaign)
    body = {
        "configs": {"mode": "point", "point": "g0"},
        "styles": {"mode": "point", "point": "patient"},
        "tactics": {"mode": "point", "point": "direct_task"},
        "agent_models": {"mode": "point", "point": "PLACEHOLDER-agent-1"},
        "episodes": {"mode": "point", "point": 1},
        "seeds": {"mode": "point", "point": 0},
    }
    first = client.post("/api/run", json=body)
    assert first.status_code == 200
    second = client.post("/api/run", json=body)
    assert second.status_code == 409
    for _ in range(60):
        if client.get("/api/run/status").json().get("status") in ("done", "error"):
            break


def test_static_page_served(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "dvarp-lab" in r.text and "app.js" in r.text
    assert client.get("/static/style.css").status_code == 200


def test_meta_remote_models_from_env(client, monkeypatch):
    monkeypatch.delenv("RESEARCH_LLM_MODEL", raising=False)
    monkeypatch.delenv("LAB_ATTACKER_LLM_MODEL", raising=False)
    m = client.get("/api/meta").json()
    assert m["remote_models"] == {"agent": None, "attacker": None}

    monkeypatch.setenv("RESEARCH_LLM_MODEL", "proxy/agent-x")
    monkeypatch.setenv("LAB_ATTACKER_LLM_MODEL", "proxy/attacker-y")
    monkeypatch.setenv("RESEARCH_LLM_API_KEY", "sk-secret")
    m = client.get("/api/meta").json()
    assert m["remote_models"] == {"agent": "proxy/agent-x", "attacker": "proxy/attacker-y"}
    assert "sk-secret" not in json.dumps(m)  # ключи не раскрываются
    assert "BASE_URL" not in json.dumps(m)  # base_url не раскрывается


def test_probe_forwards_allow_remote_llm(client, monkeypatch):
    captured = {}

    def fake_probe(spec):
        captured.update(spec)
        return {"outcome": "budget_exhausted"}

    monkeypatch.setattr(ui_app, "launcher_probe", fake_probe)
    r = client.post(
        "/api/probe",
        json={"config": "g0", "tactic": "direct_task", "allow_remote_llm": True},
    )
    assert r.status_code == 200
    assert captured["allow_remote_llm"] is True
    assert captured["config"] == "g0"
