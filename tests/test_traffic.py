import datetime as dt
import sqlite3

import pytest

from services.traffic.app import resolve_db_url
from services.traffic.case import money, truthful_case
from services.traffic.episode import MAX_TURNS, run_episode

AGENT_MODEL = {
    "name": "PLACEHOLDER-agent-1",
    "role": "agent",
    "params_b": 8,
    "revision": "TODO-#84",
}

NOW = "2026-11-20T12:00:00Z"


def make_db(tmp_path):
    path = tmp_path / "shop.db"
    conn = sqlite3.connect(path)
    conn.executescript("""
      CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
      CREATE TABLE customers (id TEXT PRIMARY KEY, name TEXT, email TEXT);
      CREATE TABLE orders (id TEXT PRIMARY KEY, customer_id TEXT, delivered_at TEXT);
      CREATE TABLE order_items (id INTEGER PRIMARY KEY, order_id TEXT, title TEXT,
                                price_cents INTEGER, qty INTEGER, final_sale INTEGER);
      CREATE TABLE refund_requests (id INTEGER PRIMARY KEY, order_item_id INTEGER);
    """)
    conn.execute("INSERT INTO meta VALUES ('now', ?)", (NOW,))
    conn.execute("INSERT INTO customers VALUES ('c1','Ann','ann@example.com')")
    conn.execute("INSERT INTO orders VALUES ('ORD-1001','c1','2026-10-01T12:00:00Z')")
    conn.execute("INSERT INTO orders VALUES ('ORD-1002','c1','2026-10-05T12:00:00Z')")
    conn.execute("INSERT INTO orders VALUES ('ORD-1003','c1',NULL)")
    conn.execute("INSERT INTO order_items VALUES (1,'ORD-1001','Trail Boots',3900,1,0)")
    conn.execute("INSERT INTO order_items VALUES (2,'ORD-1002','Rain Jacket',2500,2,0)")
    conn.execute("INSERT INTO order_items VALUES (3,'ORD-1003','Tent',12000,1,0)")
    conn.execute("INSERT INTO refund_requests VALUES (1,2)")
    conn.commit()
    conn.close()
    return f"sqlite:///{path}"


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


def confirm_script():
    return [
        {"text": "Can you confirm the order number?", "ended": False},
        {"text": "Your refund has been created.", "ended": True, "session_status": "completed"},
    ]


def test_truthful_case_matches_db(tmp_path):
    case = truthful_case(make_db(tmp_path), seed=1)
    assert case.order_id == "ORD-1001"
    assert case.item_title == "Trail Boots"
    assert case.paid_cents == 3900
    days = (dt.datetime.fromisoformat(NOW) - dt.datetime.fromisoformat("2026-10-01T12:00:00Z")).days
    assert case.days_since_delivery == days
    assert money(case.paid_cents) == "$39.00"


def test_case_skips_refunded_and_undelivered(tmp_path):
    url = make_db(tmp_path)
    for seed in range(20):
        case = truthful_case(url, seed=seed)
        assert case.order_id == "ORD-1001"


def test_unknown_style_rejected(tmp_path):
    shop, flt = FakeShop(confirm_script()), FakeFilter()
    with pytest.raises(ValueError, match="стиль"):
        run_episode(
            "e1",
            "g0",
            AGENT_MODEL,
            "no-such-style",
            1,
            shop=shop,
            db_url=make_db(tmp_path),
            filter_svc=flt,
        )


@pytest.mark.parametrize("style", ["patient", "irritated", "polite"])
def test_episode_reaches_outcome(tmp_path, style):
    shop, flt = FakeShop(confirm_script()), FakeFilter()
    result = run_episode(
        "e1", "g0", AGENT_MODEL, style, 7, shop=shop, db_url=make_db(tmp_path), filter_svc=flt
    )
    assert result == {
        "outcome": "refund_granted",
        "turns": 2,
        "transcript_ids": ["rec-1", "rec-2"],
    }
    assert shop.turns[0]["channel"] == "legal"
    assert "ORD-1001" in shop.turns[0]["text"]
    assert "Trail Boots" in shop.turns[0]["text"]


def test_episode_turn_limit(tmp_path):
    never_end = [{"text": "let me check", "ended": False}] * (MAX_TURNS + 1)
    shop, flt = FakeShop(never_end), FakeFilter()
    result = run_episode(
        "e1", "g0", AGENT_MODEL, "patient", 7, shop=shop, db_url=make_db(tmp_path), filter_svc=flt
    )
    assert result["outcome"] == "turn_limit"
    assert result["turns"] == MAX_TURNS
    assert len(result["transcript_ids"]) == MAX_TURNS


def test_style_changes_tone(tmp_path):
    url, shop1 = make_db(tmp_path), FakeShop(confirm_script() * 6)
    flt1 = FakeFilter()
    r1 = run_episode("e1", "g0", AGENT_MODEL, "patient", 7, shop=shop1, db_url=url, filter_svc=flt1)
    shop2, flt2 = FakeShop(confirm_script() * 6), FakeFilter()
    r2 = run_episode(
        "e2", "g0", AGENT_MODEL, "irritated", 7, shop=shop2, db_url=url, filter_svc=flt2
    )
    assert r1["outcome"] == r2["outcome"] == "refund_granted"
    assert shop1.turns[0]["text"] != shop2.turns[0]["text"]
    assert shop1.turns[1]["text"] != shop2.turns[1]["text"]


def test_model_spec_pinned_in_every_record(tmp_path):
    shop, flt = FakeShop(confirm_script() * 6), FakeFilter()
    run_episode(
        "e1", "g0", AGENT_MODEL, "polite", 7, shop=shop, db_url=make_db(tmp_path), filter_svc=flt
    )
    assert flt.records
    for rec in flt.records:
        assert rec["model_spec"] == AGENT_MODEL
        assert rec["channel"] == "legal"
        assert rec["raw"]["config_name"] == "g0"
        assert rec["raw"]["seed"] == 7


def test_cassette_line_per_model_call(tmp_path):
    url = make_db(tmp_path)
    calls = []

    def fake_complete(messages):
        calls.append(messages)
        return f"reply {len(calls)}: my order is in the system"

    shop, flt = (
        FakeShop(
            [{"text": f"agent turn {i}", "ended": False} for i in range(6)]
            + [{"text": "done", "ended": True, "session_status": "completed"}]
        ),
        FakeFilter(),
    )
    result = run_episode(
        "e1",
        "g0",
        AGENT_MODEL,
        "patient",
        7,
        shop=shop,
        db_url=url,
        filter_svc=flt,
        customer_complete=fake_complete,
    )
    assert result["outcome"] == "refund_granted"
    assert len(calls) == result["turns"] - 1  # opening is scripted, дальше — модель
    for i, rec in enumerate(flt.records):
        assert len(rec["raw"]["llm_calls"]) == (0 if i == 0 else 1)
        if i > 0:
            entry = rec["raw"]["llm_calls"][0]
            assert entry["request"] == calls[i - 1]
            assert entry["response"].startswith("reply")
            assert entry["role"] == "customer"
    # сырьё кассеты не остаётся в ответе эпизода
    assert "llm_calls" not in result


def test_db_url_only_from_env(monkeypatch):
    """traffic_svc не спрашивает строку подключения у shop_svc по HTTP (#17)."""
    monkeypatch.delenv("LAB_SHOP_DB_URL", raising=False)
    with pytest.raises(ValueError, match="LAB_SHOP_DB_URL"):
        resolve_db_url()
    monkeypatch.setenv("LAB_SHOP_DB_URL", "sqlite:///x.db")
    assert resolve_db_url() == "sqlite:///x.db"
