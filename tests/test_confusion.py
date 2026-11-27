"""Ось confusion легальной ноги (#56): честная путаница с якорем none.

Почему это не завышение FP: события правдивы (меняют формулировки, не факты),
редки (одно на эпизод) и реалистичны по частоте. Якорь none сохраняет «святошу»
— нижнюю границу вреда. Свойство только легальной ноги; режимы пинятся в raw
и перебираются осью кампании (сид и id ног включают режим).
"""

import pytest

from launcher import run_campaign
from launcher.axes import resolve_axis
from services.traffic.confusion import (
    StubConfusion,
    confusion_prompt,
    load_confusion,
    mangle,
    typo_text,
)
from services.traffic.episode import run_episode
from services.traffic.style import StubCustomer, load_styles
from services.ui.describe import axes
from tests.test_campaign import SPEC, FakeSvc
from tests.test_traffic import AGENT_MODEL, LEGAL_CASE, FakeFilter, FakeShop, make_db

MODES = load_confusion()


def test_registry_and_axes():
    assert set(MODES) == {"none", "forgetful", "typo", "tech_soup"}
    assert MODES["none"].get("phrases") in (None, [])  # якорь — без событий
    # default-якорь живёт в resolve_campaign: старые спеки не меняют объём
    from launcher.axes import resolve_campaign

    assert resolve_campaign({}).confusion == ["none"]
    assert resolve_axis("confusion", {"mode": "all"}) == ["forgetful", "none", "tech_soup", "typo"]
    ui = next(a for a in axes() if a["name"] == "confusion")
    assert ui["universe"] == ["forgetful", "none", "tech_soup", "typo"]


def test_stub_confusion_deterministic():
    mode = MODES["forgetful"]
    a = StubCustomer(load_styles()["patient"], lambda t: t, 17, confusion=StubConfusion(mode, 5))
    b = StubCustomer(load_styles()["patient"], lambda t: t, 17, confusion=StubConfusion(mode, 5))
    script = ["Which order?", "Please confirm", "Reviewing", "Closed"]
    assert [a.reply(t) for t in script] == [b.reply(t) for t in script]


def test_none_anchor_keeps_plain_behavior():
    """Якорь none = поведение без путаницы (совместимость со старыми прогонами)."""
    style = load_styles()["patient"]
    plain = StubCustomer(style, lambda t: t, 7)
    anchor = StubCustomer(style, lambda t: t, 7, confusion=StubConfusion(MODES["none"], 3))
    script = ["Which order?", "Please confirm", "Reviewing", "Closed"]
    assert [plain.reply(t) for t in script] == [anchor.reply(t) for t in script]


def test_typo_mangles_item_not_facts():
    rng_seed = 11
    text = "Order O-51001, item Smart Watch, paid $249.00, delivered 6 days ago."
    item = "Smart Watch"
    out = typo_text(text, item, __import__("random").Random(rng_seed))
    assert out != text and item not in out  # имя испорчено — опечатка
    assert "O-51001" in out and "$249.00" in out and "delivered 6 days ago" in out  # факты целы
    assert mangle("ab", __import__("random").Random(1)) == "ab"  # короткие слова не портятся


def test_phrase_mode_fires_once_per_episode():
    mode = MODES["tech_soup"]
    customer = StubCustomer(
        load_styles()["patient"], lambda t: t, 3, confusion=StubConfusion(mode, 9)
    )
    phrases = [p for p in mode["phrases"]]
    fired = 0
    for agent in ["Which order?", "Please confirm", "Reviewing", "Closed"]:
        reply = customer.reply(agent)
        if any(p.split("{")[0].strip()[:30] in reply for p in phrases):
            fired += 1
    assert fired == 1  # одно событие за эпизод, не постоянный шум


@pytest.mark.parametrize("live", [False, True], ids=["stub", "live-transport"])
def test_run_episode_pins_and_validates(tmp_path, live):
    script = [
        {"text": "What is your order?", "ended": False},
        {"text": "Please confirm", "ended": False},
        {"text": "Case closed.", "ended": True, "session_status": "closed"},
    ]
    flt = FakeFilter()
    prompts: list[list] = []

    def customer_complete(messages):
        prompts.append(messages)
        return "I want my refund please."

    result = run_episode(
        "legal-1",
        "g0",
        AGENT_MODEL,
        "patient",
        7,
        confusion="forgetful" if live else "none",
        shop=FakeShop(list(script)),
        legal_case=LEGAL_CASE,
        db_url=make_db(tmp_path),
        filter_svc=flt,
        customer_complete=customer_complete if live else None,
    )
    assert result["turns"] == 3
    for rec in flt.records:
        assert rec["raw"]["confusion"] == ("forgetful" if live else "none")
    if live:
        assert "absent-minded" in prompts[0][0]["content"]  # клауза роли в system
        assert confusion_prompt(MODES["none"]) is None


def test_unknown_mode_rejected(tmp_path):
    with pytest.raises(ValueError, match="confusion"):
        run_episode(
            "legal-1",
            "g0",
            AGENT_MODEL,
            "patient",
            7,
            confusion="gibberish",
            shop=FakeShop([]),
            legal_case=LEGAL_CASE,
            db_url=make_db(tmp_path),
            filter_svc=FakeFilter(),
        )


def test_campaign_confusion_axis(tmp_path, monkeypatch):
    """Ось confusion умножает ячейки; id и сиды ног включают режим."""
    monkeypatch.setenv("LAB_RUNS_DIR", str(tmp_path))
    svcs = {k: FakeSvc() for k in ("shop", "traffic", "attack", "metrics")}
    spec = {
        **SPEC,
        "confusion": {"mode": "all"},
        "confirm": True,
    }
    manifest = run_campaign(spec, services=svcs)
    assert manifest["axes"]["confusion"] == ["forgetful", "none", "tech_soup", "typo"]
    eps = [e for c in manifest["cells"] for e in c["episodes"]]
    legal_ids = [e["legal_episode_id"] for e in eps]
    attack_ids = [e["attack_episode_id"] for e in eps]
    n = len(eps)  # SPEC: 2 сида × 4 режима = 8
    assert n == 8
    assert len(set(legal_ids)) == len(legal_ids)
    assert len(set(attack_ids)) == len(attack_ids)
    # сигнатура пары включает режим: L- и A-ids отличаются только маркером
    assert {lid.replace("-L1-", "-A1-", 1) for lid in legal_ids} == set(attack_ids)
    bodies = [c[2] for c in svcs["traffic"].calls if c[1] == "/run-episode"]
    assert {b["confusion"] for b in bodies} == {"forgetful", "none", "tech_soup", "typo"}
    seeds = {b["seed"] for b in bodies}
    assert len(seeds) == 8  # производный сид легальной ноги зависит от режима
