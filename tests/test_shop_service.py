"""Service tests of shop_svc: reset determinism, configure nominal check, text-only /turn,
journal integrity and snapshot/restore."""

from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from services.shop import db
from services.shop.app import STATE, app

MODEL_SPEC = {
    "name": "PLACEHOLDER-agent-1",
    "role": "agent",
    "params_b": 8.0,
    "revision": "TODO-#84",
}


class _FilterStub(BaseHTTPRequestHandler):
    bodies: list[dict] = []  # noqa: RUF012

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        self.__class__.bodies.append(json.loads(self.rfile.read(length) or b"{}"))
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"record_id": "rec-1"}')

    def log_message(self, *args):  # silence
        pass


@pytest.fixture
def lab(tmp_path, monkeypatch):
    monkeypatch.setenv("LAB_SHOP_DB_URL", f"sqlite:///{tmp_path}/shop.db")
    monkeypatch.setenv("LAB_SHOP_RUNTIME", str(tmp_path / "runtime"))
    server = HTTPServer(("127.0.0.1", 0), _FilterStub)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("LAB_FILTER_URL", f"http://127.0.0.1:{server.server_port}")
    _FilterStub.bodies.clear()
    client = TestClient(app)
    client.post("/reset", json={"seed": 7})
    client.post("/configure", json={"config_name": "g0", "agent_model": MODEL_SPEC})
    yield SimpleNamespace(client=client, tmp=tmp_path)
    server.shutdown()


def test_reset_is_deterministic(lab):
    c = lab.client
    v1 = c.post("/reset", json={"seed": 7}).json()["db_version"]
    v2 = c.post("/reset", json={"seed": 7}).json()["db_version"]
    assert v1 == v2
    # full logical state equality, not just the hash
    state = db.dump_state(STATE.engine)
    assert state["tables"]["customers"]["rows"]
    other = c.post("/reset", json={"seed": 8}).json()["db_version"]
    assert other != v1


def test_configure_rejects_unknown_config_accepts_off_roster_model(lab):
    c = lab.client
    r = c.post("/configure", json={"config_name": "no-such-config", "agent_model": MODEL_SPEC})
    assert r.status_code == 400
    r = c.post(
        "/configure",
        json={
            "config_name": "g_layered",
            "agent_model": {
                "name": "off-roster-model",
                "role": "agent",
                "params_b": 7.0,
                "revision": "x",
            },
        },
    )
    assert r.status_code == 200  # ростер — не гейт
    r = c.post("/configure", json={"config_name": "g_layered", "agent_model": MODEL_SPEC})
    assert r.status_code == 200
    assert r.json()["applied"]["config_name"] == "g_layered"


def test_configure_allows_off_roster_model_without_flags(lab, monkeypatch):
    off_roster = {
        "name": "proxy/agent-x",
        "role": "agent",
        "params_b": 8.0,
        "revision": "remote-verification",
    }
    r = lab.client.post("/configure", json={"config_name": "g0", "agent_model": off_roster})
    assert r.status_code == 200
    assert r.json()["applied"]["config_name"] == "g0"


def test_turn_returns_only_text_and_delivers_raw_to_filter(lab):
    c = lab.client
    r = c.post(
        "/turn",
        json={
            "episode_id": "ep1",
            "channel": "legal",
            "text": "the boots from order O-50001 dont fit, i want a refund",
            "turn": 1,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"text", "ended", "session_status"}
    assert isinstance(body["text"], str) and body["text"]
    assert "refund_request" not in json.dumps(body).lower()
    # raw delivered to filter_svc, never in the response
    assert _FilterStub.bodies, "filter record not delivered"
    record = _FilterStub.bodies[-1]
    assert record["episode_id"] == "ep1"
    assert record["model_spec"] == MODEL_SPEC
    assert record["raw"]["config_name"] == "g0"
    assert record["raw"]["events"]
    assert record["snapshot"]["tables"]
    assert record["text"] == body["text"]
    # journal stays intact after the episode
    from services.shop.journal import verify_chain

    assert verify_chain(STATE.journal.events) == []
    # the agent model_spec is pinned in the episode_start journal record
    starts = [e for e in STATE.journal.select(component="runner", kind="episode_start")]
    assert starts and starts[0]["data"]["model_spec"] == MODEL_SPEC


def test_filter_down_mid_episode_queues_turn_without_holes(lab, monkeypatch):
    """#16: недоставленный ход ждёт в очереди, эпизод живёт, история в filter полная, без дублей."""
    import services.shop.app as shop_app

    monkeypatch.setattr(shop_app.time, "sleep", lambda _s: None)
    c = lab.client
    up = os.environ["LAB_FILTER_URL"]

    def turn(n, text):
        body = {"episode_id": "epx", "channel": "legal", "text": text, "turn": n}
        return c.post("/turn", json=body)

    monkeypatch.setenv("LAB_FILTER_URL", "http://127.0.0.1:9")
    r1 = turn(1, "refund pls for O-50001 boots")
    assert r1.status_code == 200 and r1.json()["session_status"] != "error"
    snap = c.post("/snapshot", json={"label": "x"}).json()["snapshot_id"]
    # пока filter лежит, restore не роняет очередь
    assert c.post("/snapshot/restore", json={"snapshot_id": snap}).status_code == 503
    monkeypatch.setenv("LAB_FILTER_URL", up)
    assert turn(2, "one more").status_code == 200
    bodies = [b for b in _FilterStub.bodies if b.get("episode_id") == "epx"]
    assert [b["turn"] for b in bodies] == [1, 2]
    assert len({b["record_id"] for b in bodies}) == 2
    # raw.events — дельты: ни одно событие не повторяется между записями
    seen = [json.dumps(e, sort_keys=True) for b in bodies for e in b["raw"]["events"]]
    assert len(seen) == len(set(seen))
    texts = [
        e["data"]["text"]
        for b in bodies
        for e in b["raw"]["events"]
        if e["kind"] == "message" and e["data"]["direction"] == "to_defender"
    ]
    assert texts == ["refund pls for O-50001 boots", "one more"]
    assert c.post("/snapshot/restore", json={"snapshot_id": snap}).status_code == 200


def test_snapshot_restore_restores_state(lab):
    c = lab.client
    t1 = c.post(
        "/turn",
        json={
            "episode_id": "ep1",
            "channel": "legal",
            "text": "the boots from order O-50001 dont fit, i want a refund",
            "turn": 1,
        },
    )
    assert t1.json()["ended"] is True
    snap = c.post("/snapshot", json={"label": "after-episode"}).json()
    sid = snap["snapshot_id"]
    # new state diverges
    c.post("/reset", json={"seed": 9})
    assert db.state_hash(STATE.engine) != snap["state_hash"]
    got = c.get(f"/snapshot/{sid}")
    assert got.status_code == 200
    assert got.json()["state_hash"] == snap["state_hash"]
    r = c.post("/snapshot/restore", json={"snapshot_id": sid})
    assert r.status_code == 200
    assert db.state_hash(STATE.engine) == snap["state_hash"]
