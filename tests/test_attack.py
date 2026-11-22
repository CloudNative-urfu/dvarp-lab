from pathlib import Path

import pytest

from services.attack import episode as attack_episode
from services.attack.tactics import load_tactics, resolve_placeholders, start_prompt
from services.traffic.episode import outcome_of

ATTACKER_MODEL = {
    "name": "PLACEHOLDER-attacker-1",
    "role": "attacker",
    "params_b": 8,
    "revision": "TODO-#84",
}
AGENT_MODEL = {
    "name": "PLACEHOLDER-agent-1",
    "role": "agent",
    "params_b": 8,
    "revision": "TODO-#84",
}


class FakeShop:
    def __init__(self, script):
        self.script = list(script)
        self.turns = []

    def post(self, path, json):
        assert path == "/turn"
        self.turns.append(json)
        return self.script.pop(0)


class FakeFilter:
    def __init__(self):
        self.records = []

    def post(self, path, json):
        assert path == "/record"
        self.records.append(json)
        return {"record_id": f"rec-{len(self.records)}"}


def never_end(n):
    return [{"text": f"agent turn {i}", "ended": False} for i in range(n)]


def test_tactics_registry_from_corpus():
    tactics = load_tactics()
    assert set(tactics) == {
        "direct_task",
        "role_switch",
        "trust_spoof",
        "obfuscation",
        "instruction_split",
        "staged_injection",
    }
    for t in tactics.values():
        assert t["count"] == len(t["entries"]) > 0
        assert t["sample_start_prompt"]


def test_start_prompt_resolves_placeholders_without_db():
    tactic = load_tactics()["direct_task"]
    prompt = start_prompt(tactic, seed=7)
    assert "{" not in prompt and "}" not in prompt
    assert prompt  # реплика корпуса тактики, детерминированная от seed
    assert prompt == start_prompt(tactic, seed=7)
    assert resolve_placeholders(
        "{order:old} {item:old:0} {price:old:0} $5", 1
    ) != resolve_placeholders("{order:old} {item:old:0} {price:old:0} $5", 2)


def test_unknown_tactic_rejected():
    with pytest.raises(ValueError, match="тактика"):
        attack_episode.run_attack(
            "e1",
            "g0",
            ATTACKER_MODEL,
            "no-such",
            3,
            1,
            shop=FakeShop(never_end(1)),
            filter_svc=FakeFilter(),
        )


def test_budget_respected():
    shop, flt = FakeShop(never_end(10)), FakeFilter()
    result = attack_episode.run_attack(
        "e1", "g0", ATTACKER_MODEL, "direct_task", 3, 7, shop=shop, filter_svc=flt
    )
    assert result == {"outcome": "budget_exhausted", "turns": 3, "attempts": 3}
    assert len(shop.turns) == 3
    assert all(t["channel"] == "attack" for t in shop.turns)


def test_tactic_used_in_model_prompt():
    prompts = []

    def fake_complete(messages):
        prompts.append(messages)
        return "still want refund for my order, process it"

    shop, flt = FakeShop(never_end(5)), FakeFilter()
    result = attack_episode.run_attack(
        "e1",
        "g0",
        ATTACKER_MODEL,
        "role_switch",
        3,
        7,
        shop=shop,
        filter_svc=flt,
        attacker_complete=fake_complete,
    )
    assert result["outcome"] == "budget_exhausted"
    opening = shop.turns[0]["text"]
    assert len(prompts) == 2  # первый ход — стартовый промпт корпуса, далее модель
    for messages in prompts:
        system = messages[0]["content"]
        assert "TACTIC: role_switch" in system
        assert opening in system  # размеченный стартовый промпт виден в промпте модели
        assert "AGENT REPLY: agent turn" in messages[-1]["content"]


def test_attacker_stops_on_believed_success():
    shop, flt = (
        FakeShop(
            [
                {"text": "good news, your refund has been created", "ended": False},
            ]
        ),
        FakeFilter(),
    )
    result = attack_episode.run_attack(
        "e1", "g0", ATTACKER_MODEL, "direct_task", 5, 7, shop=shop, filter_svc=flt
    )
    assert result == {"outcome": "attacker_stopped", "turns": 1, "attempts": 1}


def test_session_ended_outcome():
    shop, flt = (
        FakeShop(
            [
                {"text": "request logged", "ended": True, "session_status": "refused"},
            ]
        ),
        FakeFilter(),
    )
    result = attack_episode.run_attack(
        "e1", "g0", ATTACKER_MODEL, "direct_task", 5, 7, shop=shop, filter_svc=flt
    )
    assert result["outcome"] == "refused"
    assert result["attempts"] == 1


def test_model_spec_pinned_in_every_record():
    shop, flt = FakeShop(never_end(3)), FakeFilter()
    attack_episode.run_attack(
        "e1", "g0", ATTACKER_MODEL, "direct_task", 3, 7, shop=shop, filter_svc=flt
    )
    assert len(flt.records) == 3
    for i, rec in enumerate(flt.records):
        assert rec["model_spec"] == ATTACKER_MODEL
        assert rec["channel"] == "attack"
        assert rec["turn"] == i
        assert rec["raw"]["tactic"] == "direct_task"
        assert rec["raw"]["config_name"] == "g0"
        assert rec["raw"]["llm_calls"] == []


def test_cassette_line_per_model_call():
    calls = []

    def fake_complete(messages):
        calls.append(messages)
        return f"attempt {len(calls)} text"

    shop, flt = FakeShop(never_end(5)), FakeFilter()
    attack_episode.run_attack(
        "e1",
        "g0",
        ATTACKER_MODEL,
        "direct_task",
        4,
        7,
        shop=shop,
        filter_svc=flt,
        attacker_complete=fake_complete,
    )
    assert len(calls) == 3
    for i, rec in enumerate(flt.records):
        assert len(rec["raw"]["llm_calls"]) == (0 if i == 0 else 1)
        if i > 0:
            entry = rec["raw"]["llm_calls"][0]
            assert entry["request"] == calls[i - 1]
            assert entry["response"] == f"attempt {i} text"
            assert entry["role"] == "attacker"


def test_barrier_no_shop_db_access():
    """В коде атаки нет соединений к БД магазина: только HTTP /turn к shop_svc."""
    src_dir = Path(attack_episode.__file__).resolve().parent
    forbidden = (
        "create_engine",
        "sqlalchemy",
        "sqlite",
        "LAB_SHOP_DB_URL",
        "/db/readonly",
        "refund_requests",
        "order_items",
        "connect(",
    )
    for path in src_dir.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for marker in forbidden:
            assert marker not in text, f"{path.name}: found {marker!r}"
        assert "/turn" in text or path.name != "episode.py"


def test_outcome_mapping():
    assert outcome_of("completed") == "refund_granted"
    assert outcome_of("refund_created") == "refund_granted"
    assert outcome_of("refused") == "refused"
    assert outcome_of("closed") == "closed"
    assert outcome_of(None) == "closed"


def test_app_start_stop_flags():
    from fastapi.testclient import TestClient

    from services.attack.app import _state, app

    _state.update(started=False, stopped=False)
    with TestClient(app) as client:
        assert client.get("/state").json() == {"started": False, "stopped": False}
        assert client.post("/start").json() == {"ok": True, "started": True}
        assert client.get("/state").json() == {"started": True, "stopped": False}
        assert client.post("/stop").json() == {"ok": True, "stopped": True}
        assert client.get("/state").json() == {"started": False, "stopped": True}


def test_app_unknown_tactic_is_400():
    from fastapi.testclient import TestClient

    from services.attack.app import app

    body = {
        "episode_id": "e1",
        "config_name": "g0",
        "attacker_model": ATTACKER_MODEL,
        "tactic": "no-such",
        "budget": 3,
        "seed": 1,
    }
    with TestClient(app) as client:
        assert client.post("/run-episode", json=body).status_code == 400
