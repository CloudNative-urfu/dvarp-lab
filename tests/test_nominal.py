import json

from lab import nominal
from lab.modelspec import ModelSpec


def test_nominal_rejects_remote_endpoint(tmp_path):
    config = {"llm": {"base_url": "https://api.example.com/v1"}}
    problems = nominal.check_config("g0", config, [])
    assert any("не локальный контур" in p for p in problems)


def test_nominal_accepts_loopback(tmp_path):
    config = {"llm": {"base_url": "http://127.0.0.1:8000/v1"}}
    assert nominal.check_config("g0", config, []) == []


def test_nominal_unknown_config_and_model(tmp_path):
    config = {"llm": {"base_url": "http://127.0.0.1:8000/v1"}}
    problems = nominal.check_config("no_such", config, [ModelSpec("x", "agent", 8, "r")])
    assert any("отсутствует в frozen/configs" in p for p in problems)
    assert any("отсутствует в ростере" in p for p in problems)


def test_frozen_configs_copy_complete():
    from lab.modelspec import FROZEN_DIR

    names = [p.stem for p in (FROZEN_DIR / "configs").glob("*.json")]
    assert "g0" in names
    assert len(names) >= 15
    data = json.loads((FROZEN_DIR / "configs" / "g0.json").read_text())
    assert isinstance(data, dict)
