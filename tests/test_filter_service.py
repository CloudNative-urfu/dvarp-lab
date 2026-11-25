"""filter_svc: barrier on /text, hash chain, cassettes."""

from __future__ import annotations

import json

from services.filter.store import settings as filter_settings

from .conftest import MODEL_SPEC, make_raw, record_turn, seed_episode

RAW_KEYS = [
    "config_name",
    "llm_calls",
    "guard_signals",
    "internal_notes",
    "verdict",
    "snapshot_ref",
    "tools",
    "escalations",
]


async def test_text_barrier(filter_client):
    for i in range(4):
        raw = make_raw(
            config_name="g0",
            guard_signals={"flag": i},
            verdict={"violation": True},
            extra={"snapshot_ref": f"s{i}", "tools": ["refund"]},
        )
        await record_turn(
            filter_client,
            episode_id="ep1",
            turn=i,
            channel="attack",
            text=f"hello {i}",
            raw=raw,
            snapshot={"state": i},
        )
    r = await filter_client.get("/text/ep1")
    r.raise_for_status()
    body = r.json()
    assert len(body["turns"]) == 4
    for t in body["turns"]:
        assert set(t) == {"turn", "channel", "text"}
    assert [t["text"] for t in body["turns"]] == [f"hello {i}" for i in range(4)]


async def test_text_barrier_property_no_raw_values(filter_client):
    """Property: no raw field name or value of any turn leaks through the text endpoint."""
    for i in range(6):
        raw = make_raw(
            config_name=f"g{i}",
            guard_signals={"block": 1, "flag": 2},
            verdict={"outcome": "executed", "task_status": "lost"},
            extra={k: f"secret-{i}-{k}" for k in RAW_KEYS},
        )
        raw["llm_calls"] = [
            {"role": "agent", "request": {"p": f"req-{i}"}, "response": {"q": f"resp-{i}"}}
        ]
        await record_turn(
            filter_client,
            episode_id=f"ep{i}",
            turn=0,
            channel="attack",
            text=f"public {i}",
            raw=raw,
        )
    r = await filter_client.get("/text/ep3")
    r.raise_for_status()
    blob = json.dumps(r.json(), ensure_ascii=False)
    assert "secret" not in blob
    for key in RAW_KEYS:
        assert key not in blob


async def test_text_unknown_episode(filter_client):
    r = await filter_client.get("/text/nope")
    assert r.status_code == 200 and r.json()["turns"] == []


async def test_record_rejects_bad_channel(filter_client):
    r = await filter_client.post(
        "/record",
        json={
            "episode_id": "e",
            "channel": "admin",
            "turn": 0,
            "text": "x",
            "model_spec": MODEL_SPEC,
            "raw": make_raw(),
        },
    )
    assert r.status_code == 400


async def test_record_rejects_missing_config(filter_client):
    raw = {"llm_calls": []}
    r = await filter_client.post(
        "/record",
        json={
            "episode_id": "e",
            "channel": "legal",
            "turn": 0,
            "text": "x",
            "model_spec": MODEL_SPEC,
            "raw": raw,
        },
    )
    assert r.status_code == 400
    # config_name may come from raw.config_name instead of the top-level field
    raw["config_name"] = "g0"
    r = await filter_client.post(
        "/record",
        json={
            "episode_id": "e",
            "channel": "legal",
            "turn": 0,
            "text": "x",
            "model_spec": MODEL_SPEC,
            "raw": raw,
        },
    )
    assert r.status_code == 200


async def test_chain_intact_after_records(filter_client):
    for i in range(5):
        await record_turn(
            filter_client,
            episode_id=f"ep{i}",
            turn=0,
            channel="legal",
            text=f"t{i}",
            config_name="g0",
        )
    r = await filter_client.get("/chain/verify")
    r.raise_for_status()
    assert r.json()["defects"] == []


async def test_chain_detects_tampering(filter_client):
    await record_turn(filter_client, episode_id="ep1", turn=0, channel="legal", text="t0")
    await record_turn(filter_client, episode_id="ep1", turn=1, channel="legal", text="t1")
    assert (await filter_client.get("/chain/verify")).json()["defects"] == []

    chain_path = filter_settings.chain_path
    lines = chain_path.read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[0])
    rec["payload"]["text"] = "forged"
    lines[0] = json.dumps(rec, ensure_ascii=False, sort_keys=True)
    chain_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    defects = (await filter_client.get("/chain/verify")).json()["defects"]
    assert defects and any("payload изменён" in d for d in defects)


async def test_cassette_line_per_llm_call(filter_client):
    calls = [{"role": "agent", "request": {"n": i}, "response": {"a": i}} for i in range(3)]
    raw = make_raw(config_name="g0", extra={})
    raw["llm_calls"] = calls
    await record_turn(filter_client, episode_id="ep1", turn=0, raw=raw)
    await record_turn(filter_client, episode_id="ep1", turn=1, raw=raw)  # 3 more calls
    cassette = filter_settings.cassette_path("ep1")
    lines = [json.loads(line) for line in cassette.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 6
    for i, line in enumerate(lines):
        assert line["model"] == MODEL_SPEC
        assert line["request"] == {"n": i % 3}
        assert line["response"] == {"a": i % 3}


async def test_seed_episode_writes_chain_and_text(filter_client):
    await seed_episode(
        filter_client, config_name="g0", episode_id="ep-legal", channel="legal", turns=2
    )
    body = (await filter_client.get("/text/ep-legal")).json()
    assert [t["turn"] for t in body["turns"]] == [0, 1]
    assert (await filter_client.get("/chain/verify")).json()["defects"] == []


async def test_dialog_is_texts_only_and_deduplicated(filter_client):
    def msg(direction, turn, text):
        return {"kind": "message", "data": {"direction": direction, "turn": turn, "text": text}}

    events = [
        msg("to_defender", 0, "верните деньги"),
        msg("to_attacker", 0, "назовите номер заказа"),
        {"kind": "tool_call", "data": {"tool": "refund", "secret": "shop-private"}},
    ]
    shop_raw = make_raw(extra={"events": events}, guard_signals={"flagged": 1})
    for _ in range(2):  # повторная доставка той же записи схлопывается
        await record_turn(
            filter_client, episode_id="dlg", raw=shop_raw, text="назовите номер заказа"
        )
    await record_turn(filter_client, episode_id="dlg", raw=make_raw(), text="назовите номер заказа")
    body = (await filter_client.get("/dialog/dlg")).json()
    assert body["lines"] == [
        {"turn": 0, "channel": "legal", "author": "customer", "text": "верните деньги"},
        {"turn": 0, "channel": "legal", "author": "agent", "text": "назовите номер заказа"},
    ]
    blob = json.dumps(body, ensure_ascii=False)
    for leak in ("shop-private", "tool_call", "flagged", *RAW_KEYS):
        assert leak not in blob

    # без записей shop: только ответы агента
    await record_turn(filter_client, episode_id="sim-only", raw=make_raw(), text="ответ")
    lines = (await filter_client.get("/dialog/sim-only")).json()["lines"]
    assert lines == [{"turn": 0, "channel": "legal", "author": "agent", "text": "ответ"}]


async def test_record_id_is_idempotent(filter_client):
    """#16: повтор доставки с тем же record_id не дублирует строку и звено цепочки."""
    body = {
        "episode_id": "ep-idem",
        "channel": "legal",
        "turn": 1,
        "text": "t",
        "model_spec": MODEL_SPEC,
        "raw": make_raw(config_name="g0"),
        "record_id": "rec-fixed",
    }
    first = (await filter_client.post("/record", json=body)).json()
    again = (await filter_client.post("/record", json=body)).json()
    assert first == {"record_id": "rec-fixed"}
    assert again == {"record_id": "rec-fixed", "duplicate": True}
    assert len((await filter_client.get("/text/ep-idem")).json()["turns"]) == 1
    assert (await filter_client.get("/chain/verify")).json()["defects"] == []
    lines = filter_settings.chain_path.read_text().splitlines()
    assert sum("rec-fixed" in line for line in lines) == 1


async def test_finalize_one_row_per_episode_and_outcome(filter_client):
    """#10: финальная строка эпизода отдельно от трейса; повтор доставки её не дублирует."""
    body = {
        "episode_id": "ep-fin",
        "config_name": "g0",
        "channel": "attack",
        "model_spec": MODEL_SPEC,
        "verdict": {"violation": True, "outcome": "executed", "task_status": "violation"},
        "guard_signals": {"flag": 2},
    }
    for _ in range(2):
        assert (await filter_client.post("/finalize", json=body)).json() == {"ok": True}
    got = (await filter_client.get("/finals/ep-fin")).json()
    assert got["outcome"] == "executed" and got["violation"] is True
    assert set(got) == {"episode_id", "outcome", "violation", "task_status", "escalated", "leak"}
    assert (await filter_client.get("/finals/nope")).status_code == 404

    from sqlalchemy.orm import Session

    from services.filter import store
    from services.filter.models import EpisodeFinal

    with Session(store.engine()) as s:
        assert s.query(EpisodeFinal).filter_by(episode_id="ep-fin").count() == 1
