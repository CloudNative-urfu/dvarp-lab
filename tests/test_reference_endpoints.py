"""Read-only справочные эндпоинты: список эпизодов (filter) и конфигов с данными (metrics)."""

from fastapi.testclient import TestClient

from services.filter import app as filter_app
from services.metrics import app as metrics_app


def _seed_episodes(tmp_path):
    monkeypatch_urls = {
        "LAB_RAW_DB_URL": f"sqlite:///{tmp_path}/raw.db",
        "LAB_METRICS_DB_URL": f"sqlite:///{tmp_path}/metrics.db",
    }
    for k, v in monkeypatch_urls.items():
        monkeypatch_setenv(k, v)
    return monkeypatch_urls


def monkeypatch_setenv(k, v):
    import os

    os.environ[k] = v


def test_filter_episodes_listing(tmp_path):
    import os

    os.environ["LAB_RAW_DB_URL"] = f"sqlite:///{tmp_path}/raw.db"
    os.environ["LAB_RAW_DIR"] = str(tmp_path / "raw")
    client = TestClient(filter_app.app)
    base = {
        "channel": "legal",
        "turn": 0,
        "text": "t",
        "model_spec": {"name": "m", "role": "agent", "params_b": 8, "revision": "r"},
        "snapshot": {},
        "config_name": "g0",
        "raw": {},
    }
    for eid, turns in (("e-a", 2), ("e-b", 1)):
        for t in range(turns):
            assert (
                client.post("/record", json={**base, "episode_id": eid, "turn": t}).status_code
                == 200
            )
    eps = client.get("/episodes").json()["episodes"]
    assert {e["episode_id"] for e in eps} == {"e-a", "e-b"}
    assert all(e["n_turns"] == (2 if e["episode_id"] == "e-a" else 1) for e in eps)
    assert all("text" not in e for e in eps)  # барьер: без текстов


def test_metrics_configs_listing(tmp_path):
    import os

    os.environ["LAB_RAW_DB_URL"] = f"sqlite:///{tmp_path}/raw.db"
    os.environ["LAB_METRICS_DB_URL"] = f"sqlite:///{tmp_path}/metrics.db"
    fclient = TestClient(filter_app.app)
    client = TestClient(metrics_app.app)
    assert client.get("/configs").json() == {"configs": []}  # пусто → нет прогонов
    base = {
        "channel": "attack",
        "turn": 0,
        "text": "t",
        "snapshot": {},
        "model_spec": {"name": "m", "role": "attacker", "params_b": 8, "revision": "r"},
        "raw": {
            "verdict": {"violation": True, "outcome": "x", "task_status": None, "escalated": False}
        },
    }
    for cfg in ("g0", "g_ctx"):
        assert (
            fclient.post(
                "/record", json={**base, "episode_id": f"e-{cfg}", "config_name": cfg}
            ).status_code
            == 200
        )
    assert client.get("/configs").json() == {"configs": ["g0", "g_ctx"]}
    client.post("/compute", json={})
    # карточки по конфигам из оглавления
    for cfg in ("g0", "g_ctx"):
        m = client.get(f"/metrics/{cfg}").json()
        assert m["results"]
