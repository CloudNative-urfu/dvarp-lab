"""Деградация пустого старта: filter создаёт сырую БД на старте, metrics отвечает
«нет данных» вместо 500, журналы shop возобновляют нумерацию после рестартов."""

from fastapi.testclient import TestClient

from services.filter import app as filter_app
from services.metrics import app as metrics_app
from services.shop import app as shop_app


def test_filter_creates_raw_db_at_startup(tmp_path, monkeypatch):
    monkeypatch.setenv("LAB_RAW_DB_URL", f"sqlite:///{tmp_path}/raw.db")
    monkeypatch.setenv("LAB_RAW_DIR", str(tmp_path / "raw"))
    with TestClient(filter_app.app) as _:
        assert (tmp_path / "raw.db").exists()


def test_metrics_compute_and_get_on_missing_raw_db(tmp_path, monkeypatch):
    missing = tmp_path / "nonexistent" / "raw.db"
    monkeypatch.setenv("LAB_RAW_DB_URL", f"sqlite:///{missing}")
    monkeypatch.setenv("LAB_METRICS_DB_URL", f"sqlite:///{tmp_path}/metrics.db")
    client = TestClient(metrics_app.app)
    r = client.post("/compute", json={"config_name": "g0"})
    assert r.status_code == 200
    assert r.json() == {"computed": 0}
    g = client.get("/metrics/g0")
    assert g.status_code == 200
    assert g.json()["results"] == []
    assert "нет прогонов" in g.json()["note"]


def test_journal_seq_resumes_after_restart(tmp_path, monkeypatch):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    monkeypatch.setenv("LAB_SHOP_RUNTIME", str(runtime))
    (runtime / "journal-3.jsonl").write_text('{"seq": 1, "hash": "x"}\n', encoding="utf-8")
    shop_app.STATE.journal_seq = 0  # имитация рестарта процесса
    j = shop_app._new_journal()
    assert shop_app.STATE.journal_seq == 4
    assert (runtime / "journal-4.jsonl").exists()
    # следующая ячейка — следующий файл
    shop_app._new_journal()
    assert (runtime / "journal-5.jsonl").exists()
