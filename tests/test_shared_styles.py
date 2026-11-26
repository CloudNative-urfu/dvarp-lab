"""Общий тон пары: реестр, stub-фолбэки, реальные пути эпизодов и оси UI/CLI."""

import pytest

from launcher import run_campaign
from launcher.axes import resolve_axis
from services.attack.attacker import LlmAttacker, StubAttacker, build_system_prompt
from services.attack.episode import run_attack
from services.traffic.episode import run_episode
from services.traffic.style import NEUTRAL_BANKS, StubCustomer, load_styles, style_prompt
from services.ui.describe import axes
from tests.test_attack import ATTACKER_MODEL
from tests.test_campaign import SPEC, FakeSvc
from tests.test_traffic import AGENT_MODEL, LEGAL_CASE, FakeFilter, FakeShop, make_db

NEW_STYLES = {
    "formal",
    "friendly",
    "brief",
    "verbose",
    "confused",
    "panic",
    "aggressive",
    "fake-legal",
    "groveling",
    "sarcastic",
    "entitled",
    "emotional",
    "dry",
    "polite-insistent",
    "flattering",
    "escalating",
    "de-escalating",
    "rambling",
    "tech-jargon",
    "mimicry",
}
STYLES = load_styles()


def test_registry_and_axes_keep_legacy_and_expose_new_roles():
    assert set(STYLES) == NEW_STYLES | {"patient", "irritated", "polite"}
    for style in STYLES.values():
        assert style["description"].strip()
        assert 1 <= len(style["openings"]) <= 2
    universe = sorted(STYLES)
    assert resolve_axis("styles", {"mode": "all"}) == universe
    assert resolve_axis("styles", {"mode": "point", "point": "formal"}) == ["formal"]
    assert resolve_axis("styles", {"mode": "set", "values": ["verbose", "brief"]}) == [
        "brief",
        "verbose",
    ]
    ui_axis = next(a for a in axes() if a["name"] == "styles")
    assert ui_axis["universe"] == universe


@pytest.mark.parametrize("style_name", sorted(STYLES))
@pytest.mark.parametrize("live", [False, True], ids=["stub", "live-transport"])
def test_every_style_runs_in_both_legs(tmp_path, style_name, live):
    prompts = {"legal": [], "attack": []}

    def complete(leg):
        def reply(messages):
            prompts[leg].append(messages)
            return "Please review my request."

        return reply

    script = [
        {"text": "Can you confirm?", "ended": False},
        {"text": "What is your order?", "ended": False},
        {"text": "Still reviewing.", "ended": False},
        {"text": "Request closed.", "ended": True, "session_status": "closed"},
    ]
    legal_shop, attack_shop = FakeShop(script), FakeShop(script)
    legal_filter, attack_filter = FakeFilter(), FakeFilter()
    legal = run_episode(
        "legal",
        "g0",
        AGENT_MODEL,
        style_name,
        7,
        shop=legal_shop,
        db_url=make_db(tmp_path),
        legal_case=LEGAL_CASE,
        filter_svc=legal_filter,
        customer_complete=complete("legal") if live else None,
    )
    attack = run_attack(
        "attack",
        "g0",
        ATTACKER_MODEL,
        "direct_task",
        4,
        7,
        style_name=style_name,
        goal="refund_expired",
        shop=attack_shop,
        filter_svc=attack_filter,
        attacker_complete=complete("attack") if live else None,
    )
    assert legal["turns"] == attack["turns"] == 4
    assert "ORD-1001" in legal_shop.turns[0]["text"]
    for record in legal_filter.records + attack_filter.records:
        assert record["raw"]["style"] == style_name
    for turn in legal_shop.turns + attack_shop.turns:
        assert turn["text"] and "{order_id}" not in turn["text"]
    if live:
        for leg in prompts.values():
            assert len(leg) == 3
            assert style_prompt(STYLES[style_name]) in leg[0][0]["content"]
        system = prompts["attack"][0][0]["content"]
        assert "METHOD" in system and "YOUR CLAIM" in system
        assert len(prompts["attack"][-1]) > len(prompts["attack"][0])
        assert "short informal messages" not in prompts["legal"][0][0]["content"]
        assert "under 600 characters" not in prompts["attack"][0][0]["content"]


@pytest.mark.parametrize("empty", [False, True])
def test_optional_banks_fall_back_independently(empty):
    style = {"name": "minimal", "description": "Neutral", "openings": ["Hello"]}
    if empty:
        style.update(confirm=[], answers=[], push=[])
    customer = StubCustomer(style, lambda text: text, 1)
    assert customer.reply("Please confirm") in NEUTRAL_BANKS["confirm"]
    assert customer.reply("Which order?") in NEUTRAL_BANKS["answers"]
    assert customer.reply("Reviewing") in NEUTRAL_BANKS["push"]
    attacker = StubAttacker("corpus start", 1, style)
    assert attacker.opening() == "corpus start"
    assert attacker.reply("Reviewing") in NEUTRAL_BANKS["push"]


def test_stub_seed_is_repeatable():
    style = STYLES["formal"]
    a = StubCustomer(style, lambda text: text, 17)
    b = StubCustomer(style, lambda text: text, 17)
    assert a.opening() == b.opening()
    assert [a.reply(t) for t in ["Confirm", "Which?", "Reviewing"]] == [
        b.reply(t) for t in ["Confirm", "Which?", "Reviewing"]
    ]


@pytest.mark.parametrize("style_name", ["escalating", "de-escalating"])
def test_dynamic_tone_keeps_conversation_history(style_name):
    class Model:
        def __init__(self):
            self.prompts = []

        def reply(self, role, messages):
            self.prompts.append(messages)
            return f"Follow-up {len(self.prompts)}"

    model = Model()
    system = build_system_prompt("vector", "fixed claim", "method", STYLES[style_name])
    attacker = LlmAttacker(system, "fixed claim", model)
    attacker.reply("First answer")
    attacker.reply("Second answer")
    last = model.prompts[-1]
    assert STYLES[style_name]["description"] in last[0]["content"]
    assert any(m["content"] == "Follow-up 1" for m in last)
    assert any("First answer" in m["content"] for m in last)


def test_campaign_passes_same_style_to_both_legs(tmp_path, monkeypatch):
    monkeypatch.setenv("LAB_RUNS_DIR", str(tmp_path))
    services = {name: FakeSvc() for name in ("shop", "traffic", "attack", "metrics")}
    run_campaign({**SPEC, "styles": {"mode": "all"}}, services=services)
    legal = [body["style"] for _, path, body in services["traffic"].calls if path == "/run-episode"]
    attack = [body["style"] for _, path, body in services["attack"].calls if path == "/run-episode"]
    assert legal == attack
    assert set(legal) == set(STYLES)
