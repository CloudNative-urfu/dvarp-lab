import json

from lab import nominal
from lab.modelspec import ModelSpec


def test_nominal_accepts_remote_endpoint_and_marks_it(tmp_path):
    config = {"llm": {"base_url": "https://api.example.com/v1"}}
    assert nominal.check_config("g0", config, []) == []
    env = {
        "RESEARCH_LLM_BASE_URL": "https://api.example.com/v1",
        "LAB_CUSTOMER_LLM_BASE_URL": "http://127.0.0.1:8000/v1",
        "LAB_ATTACKER_LLM_BASE_URL": "",
    }
    assert nominal.remote_endpoints(env) == ["RESEARCH_LLM_BASE_URL"]
    for url in ("http://127.0.0.1:1/v1", "http://localhost/v1", "http://[::1]:9/v1"):
        assert nominal.is_local_url(url), url
    for url in ("http://10.1.2.3/v1", "https://api.openai.com/v1", "http://8.8.8.8/v1"):
        assert not nominal.is_local_url(url), url


def test_nominal_accepts_loopback(tmp_path):
    config = {"llm": {"base_url": "http://127.0.0.1:8000/v1"}}
    assert nominal.check_config("g0", config, []) == []


def test_nominal_unknown_config_and_model(tmp_path):
    config = {"llm": {"base_url": "http://127.0.0.1:8000/v1"}}
    problems = nominal.check_config("no_such", config, [ModelSpec("x", "agent", 8, "r")])
    assert any("отсутствует в frozen/configs" in p for p in problems)
    assert not any("ростер" in p for p in problems)  # ростер — не гейт


def test_frozen_configs_copy_complete():
    from lab.modelspec import FROZEN_DIR

    names = [p.stem for p in (FROZEN_DIR / "configs").glob("*.json")]
    assert "g0" in names
    assert len(names) >= 15
    data = json.loads((FROZEN_DIR / "configs" / "g0.json").read_text())
    assert isinstance(data, dict)
