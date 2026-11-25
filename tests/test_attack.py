import pytest

from lab import world as lab_world
from services.attack import episode as attack_episode
from services.attack.attacker import build_system_prompt
from services.attack.tactics import load_tactics, method_prompt
from services.traffic.episode import outcome_of
from services.traffic.style import load_styles

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


def test_methods_registry_from_corpus():
    """Ось методов: реестр заморожен; метод несёт описание пути давления."""
    methods = load_tactics()
    assert set(methods) >= {
        "direct_task",
        "role_switch",
        "trust_spoof",
        "obfuscation",
        "instruction_split",
        "staged_injection",
        "third_party_emergency",
        "authority_impersonation",
    }
    for m in methods.values():
        assert m["count"] == len(m["entries"]) > 0
        assert m["description"]
        # обязательных реплик нет: метод — путь давления, стартовая реплика — цель
        assert method_prompt(m) == m["description"]


def test_goals_registry_bound_to_world():
    """Ось целей: 7 замороженных претензий, каждая ссылается на данные мира."""
    manifest = lab_world.load_manifest()
    goals = lab_world.load_goals(manifest)
    assert len(goals) == 7
    for g in goals.values():
        if g["order"] == "fictive":
            assert g["order"] not in manifest["orders"]  # фиктивный заказ — вне БД мира
        else:
            assert g["order"] in manifest["orders"]
        assert g["claim"].strip() and g["vector"].strip()


def test_claims_render_from_manifest_without_random():
    """Претензия цели — детерминированная подстановка фактов манифеста мира."""
    manifest = lab_world.load_manifest()
    goals = lab_world.load_goals(manifest)
    claim = lab_world.render_claim(
        goals["refund_expired"]["claim"],
        lab_world.claim_facts(goals["refund_expired"], manifest),
    )
    assert "O-51002" in claim and "$129.00" in claim and "{" not in claim
    # фиктивный заказ: факты есть в манифесте (вне БД мира — проверяет test_world)
    fictive = lab_world.claim_facts(goals["refund_nonexistent"], manifest)
    assert fictive["order_id"] == "O-51100" and fictive["amount_cents"] == 31900


def test_prompt_is_function_of_goal_method_style():
    """Промпт атакующего = детерминированная функция «цель × метод × тон»."""
    manifest = lab_world.load_manifest()
    goals = lab_world.load_goals(manifest)
    methods = load_tactics()
    styles = load_styles()

    def triple(goal, tactic, style):
        entry = goals[goal]
        claim = lab_world.render_claim(entry["claim"], lab_world.claim_facts(entry, manifest))
        return build_system_prompt(
            entry["vector"], claim, method_prompt(methods[tactic]), styles.get(style)
        )

    base = triple("refund_expired", "direct_task", "patient")
    assert base == triple("refund_expired", "direct_task", "patient")
    assert triple("refund_overprice", "direct_task", "patient") != base
    assert triple("refund_expired", "role_switch", "patient") != base
    assert triple("refund_expired", "direct_task", "irritated") != base


def test_unknown_goal_rejected():
    with pytest.raises(ValueError, match="цель"):
        attack_episode.run_attack(
            "e1",
            "g0",
            ATTACKER_MODEL,
            "direct_task",
            3,
            1,
            goal="no-such",
            shop=FakeShop(never_end(1)),
            filter_svc=FakeFilter(),
        )


def test_unknown_tactic_rejected():
    with pytest.raises(ValueError, match="тактика"):
        attack_episode.run_attack(
            "e1",
            "g0",
            ATTACKER_MODEL,
            "no-such",
            3,
            1,
            goal="refund_expired",
            shop=FakeShop(never_end(1)),
            filter_svc=FakeFilter(),
        )


def test_budget_respected():
    shop, flt = FakeShop(never_end(10)), FakeFilter()
    result = attack_episode.run_attack(
        "e1",
        "g0",
        ATTACKER_MODEL,
        "direct_task",
        3,
        7,
        goal="refund_expired",
        shop=shop,
        filter_svc=flt,
    )
    assert result == {"outcome": "budget_exhausted", "turns": 3, "attempts": 3}
    assert len(shop.turns) == 3
    assert all(t["channel"] == "attack" for t in shop.turns)


def test_opening_is_the_frozen_goal_claim():
    """Стартовая реплика — отрендеренная претензия цели; тот же сид → та же реплика."""
    shop1, flt1 = FakeShop(never_end(1)), FakeFilter()
    shop2, flt2 = FakeShop(never_end(1)), FakeFilter()
    attack_episode.run_attack(
        "e1",
        "g0",
        ATTACKER_MODEL,
        "direct_task",
        1,
        7,
        goal="refund_expired",
        shop=shop1,
        filter_svc=flt1,
    )
    attack_episode.run_attack(
        "e2",
        "g0",
        ATTACKER_MODEL,
        "direct_task",
        1,
        99,
        goal="refund_expired",
        shop=shop2,
        filter_svc=flt2,
    )
    assert shop1.turns[0]["text"] == shop2.turns[0]["text"]
    assert "O-51002" in shop1.turns[0]["text"]


def test_tactic_and_claim_used_in_model_prompt():
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
        goal="refund_expired",
        shop=shop,
        filter_svc=flt,
        attacker_complete=fake_complete,
    )
    assert result["outcome"] == "budget_exhausted"
    opening = shop.turns[0]["text"]
    assert len(prompts) == 2  # первый ход — претензия цели, далее модель
    for messages in prompts:
        system = messages[0]["content"]
        assert "Fake authority or system role" in system  # описание метода
        assert opening in system  # претензия цели видна в промпте модели
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
        "e1",
        "g0",
        ATTACKER_MODEL,
        "direct_task",
        5,
        7,
        goal="refund_expired",
        shop=shop,
        filter_svc=flt,
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
        "e1",
        "g0",
        ATTACKER_MODEL,
        "direct_task",
        5,
        7,
        goal="refund_expired",
        shop=shop,
        filter_svc=flt,
    )
    assert result["outcome"] == "refused"
    assert result["attempts"] == 1


def test_model_spec_pinned_in_every_record():
    shop, flt = FakeShop(never_end(3)), FakeFilter()
    attack_episode.run_attack(
        "e1",
        "g0",
        ATTACKER_MODEL,
        "direct_task",
        3,
        7,
        goal="refund_expired",
        shop=shop,
        filter_svc=flt,
    )
    assert len(flt.records) == 3
    for i, rec in enumerate(flt.records):
        assert rec["model_spec"] == ATTACKER_MODEL
        assert rec["channel"] == "attack"
        assert rec["turn"] == i
        assert rec["raw"]["tactic"] == "direct_task"
        assert rec["raw"]["goal"] == "refund_expired"
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
        goal="refund_expired",
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
    """В коде атаки нет соединений к БД магазина и брифа: только HTTP /turn."""
    from pathlib import Path

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
        "/attack-brief",
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


def test_app_unknown_goal_is_400():
    from fastapi.testclient import TestClient

    from services.attack.app import app

    body = {
        "episode_id": "e1",
        "config_name": "g0",
        "attacker_model": ATTACKER_MODEL,
        "tactic": "direct_task",
        "goal": "no-such",
        "budget": 3,
        "seed": 1,
    }
    with TestClient(app) as client:
        assert client.post("/run-episode", json=body).status_code == 400


def test_social_methods_in_registry():
    reg = load_tactics()
    for name, entries in (
        ("third_party_emergency", ["atk-21", "atk-22", "atk-23", "atk-24"]),
        ("authority_impersonation", ["atk-25", "atk-26", "atk-27", "atk-28"]),
    ):
        assert name in reg
        assert reg[name]["entries"] == entries


def test_unknown_style_rejected():
    shop, flt = FakeShop(never_end(3)), FakeFilter()
    with pytest.raises(ValueError, match="отсутствует в frozen/styles.json"):
        attack_episode.run_attack(
            "e1",
            "g0",
            ATTACKER_MODEL,
            "direct_task",
            2,
            7,
            style_name="no_such",
            goal="refund_expired",
            shop=shop,
            filter_svc=flt,
        )


def test_style_mixed_into_attacker_system_prompt():
    prompts = []

    def fake_complete(messages):
        prompts.append(messages)
        return "still want refund for my order, process it"

    shop, flt = FakeShop(never_end(3)), FakeFilter()
    result = attack_episode.run_attack(
        "e1",
        "g0",
        ATTACKER_MODEL,
        "third_party_emergency",
        2,
        7,
        style_name="patient",
        goal="refund_expired",
        shop=shop,
        filter_svc=flt,
        attacker_complete=fake_complete,
    )
    assert result["outcome"] == "budget_exhausted"
    system = prompts[0][0]["content"]
    assert "Claims a relative or family member" in system  # метод — путь давления
    assert "Communication style" in system  # тон — ось стиля
    assert "Calm patient customer" in system
    assert "O-51002" in system  # претензия цели — из манифеста мира


def test_attack_record_pins_style():
    shop, flt = FakeShop(never_end(2)), FakeFilter()
    attack_episode.run_attack(
        "e1",
        "g0",
        ATTACKER_MODEL,
        "authority_impersonation",
        1,
        7,
        style_name="irritated",
        goal="refund_expired",
        shop=shop,
        filter_svc=flt,
    )
    for rec in flt.records:
        assert rec["raw"].get("style") == "irritated"
