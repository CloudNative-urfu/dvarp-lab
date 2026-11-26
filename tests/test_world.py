"""Замороженный мир (frozen/seed_worlds/world_a): байт-идентичность, чистота БД,
валидация, фиктивный заказ вне БД, легальный кейс возвратен, цели ссылаются на мир."""

import copy

import pytest

from lab import world as lab_world
from services.shop import db


@pytest.fixture
def world_db(tmp_path):
    url = f"sqlite:///{tmp_path / 'world.db'}"
    info = db.reset_world(url)
    return url, info


def test_same_world_gives_byte_identical_db(world_db):
    """Тот же мир → байт-идентичная БД; сид данных не касается."""
    url, info = world_db
    state1 = db.dump_state(url)
    again = db.reset_world(url)
    assert db.dump_state(url) == state1
    assert again["state_hash"] == info["state_hash"]
    assert again["dataset_hash"] == info["dataset_hash"]


def test_world_meta_pins_version(world_db):
    """meta пиннит версию мира: world + dataset_hash; seed в данных не живёт."""
    url, info = world_db
    meta = {r[0]: r[1] for r in db.dump_state(url)["tables"]["meta"]["rows"]}
    assert meta["world"] == "world_a"
    assert meta["dataset_hash"] == info["dataset_hash"]
    assert meta["now"] == lab_world.load_manifest()["now"]
    assert "seed" not in meta


def test_world_shape_one_client_nine_orders(world_db):
    """Один клиент A, 9 заказов без каталога SKU, давний заказ с истёкшим сроком."""
    url, _ = world_db
    state = db.dump_state(url)
    assert len(state["tables"]["customers"]["rows"]) == 1
    assert len(state["tables"]["orders"]["rows"]) == 9
    # каталога SKU нет: только истории заказов
    assert "skus" not in state["tables"] and "catalog" not in state["tables"]
    conn = db.connect(url, readonly=True)
    try:
        (row,) = conn.fetchall(
            "SELECT o.id FROM orders o WHERE o.delivered_at IS NOT NULL "
            "AND o.delivered_at < :cutoff",
            {"cutoff": "2026-11-01T00:00:00Z"},
        )
    finally:
        conn.close()
    assert row == ("O-51002",)  # O-51002 доставлен 2026-09-15 — окно R1 давно истекло


def test_db_purity_no_role_traces(world_db):
    """В БД не остаётся ни одного следа роли/атакующего (роли — в манифесте мира)."""
    url, _ = world_db
    dump = db.dump_state(url)
    for name, table in dump["tables"].items():
        assert "accounts_manifest" not in table["columns"], name
        for row in table["rows"]:
            for value in row:
                assert "attacker" not in str(value).lower(), (name, value)


def test_fictive_order_not_in_db(world_db):
    """Фиктивный заказ заморожен в манифесте, но в БД его нет."""
    url, _ = world_db
    manifest = lab_world.load_manifest()
    fictive_id = manifest["fictive_order"]["id"]
    assert fictive_id not in manifest["orders"]
    conn = db.connect(url, readonly=True)
    try:
        rows = conn.fetchall("SELECT id FROM orders WHERE id = :o", {"o": fictive_id})
    finally:
        conn.close()
    assert rows == []


def test_legal_case_is_always_refundable(world_db):
    """Легальный кейс фиксирован и возвратен: в окне R1, не final_sale, без истории."""
    url, _ = world_db
    manifest = lab_world.load_manifest()
    case = manifest["legal_case"]
    # кейс берётся из БД — как остальные факты; причина заморожена в данных
    from services.traffic.case import truthful_case

    c = truthful_case(url, case)
    assert c.order_id == case["order"]
    assert 0 <= c.days_since_delivery <= 30
    assert c.reason_code  # причина из данных


def test_goals_reference_world_data():
    """Цели ссылаются на заказы мира (или фиктивный заказ); рендер без рандома."""
    manifest = lab_world.load_manifest()
    goals = lab_world.load_goals(manifest)
    assert set(goals) == {
        "refund_nonexistent",
        "refund_final_sale",
        "refund_overprice",
        "refund_wrong_item",
        "refund_expired",
        "refund_quantity",
        "escalate_confused",
    }
    for g in goals.values():
        facts = lab_world.claim_facts(g, manifest)
        claim = lab_world.render_claim(g["claim"], facts)
        assert facts["order_id"] in claim and "{" not in claim


# ------------------------------------------------------------------ validation


def _mutated_manifest():
    manifest = lab_world.load_manifest()
    manifest = copy.deepcopy(manifest)
    return manifest


def test_manifest_drift_is_fail_closed(tmp_path):
    """Манифест не совпадает с CSV — загрузка падает (мир не собирается молча)."""
    import json as _json

    manifest = _mutated_manifest()
    manifest["orders"]["O-51001"]["items"][0]["price_cents"] = 999
    manifest_path = lab_world.world_dir("world_a") / "manifest.json"
    original = manifest_path.read_text(encoding="utf-8")
    try:
        manifest_path.write_text(
            _json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        with pytest.raises(lab_world.WorldError):
            db.load_world("world_a")
    finally:
        manifest_path.write_text(original, encoding="utf-8")


def test_goals_reference_validation():
    """Цель, ссылающаяся на чужой заказ, не загружается (fail-closed)."""
    import json as _json

    from lab.world import GOALS_PATH

    original = GOALS_PATH.read_text(encoding="utf-8")
    data = _json.loads(original)
    data["goals"][0]["order"] = "O-99999"
    try:
        GOALS_PATH.write_text(_json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        with pytest.raises(lab_world.WorldError, match="чужой заказ"):
            lab_world.load_goals()
    finally:
        GOALS_PATH.write_text(original, encoding="utf-8")
