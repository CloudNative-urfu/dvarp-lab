"""Номинальная проверка конфигурации перед каждым прогоном (замена сетевой охраны)."""

from __future__ import annotations

from urllib.parse import urlparse

from lab.modelspec import FROZEN_DIR, ModelSpec, load_roster

LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost"}


def check_config(config_name: str, config: dict, agents: list[ModelSpec]) -> list[str]:
    """Возвращает список замечаний; пустой список — прогон можно запускать."""
    problems: list[str] = []
    configs_dir = FROZEN_DIR / "configs"
    if not (configs_dir / f"{config_name}.json").exists():
        problems.append(f"конфиг {config_name} отсутствует в frozen/configs/")
    known = {p.stem for p in configs_dir.glob("*.json")}
    if known and config_name not in known:
        problems.append(f"конфиг {config_name} не из замороженного набора")
    problems += _check_llm_endpoints(config)
    roster = load_roster()
    for spec in agents:
        if spec.name not in roster:
            problems.append(f"модель {spec.name} ({spec.role}) отсутствует в ростере")
    return problems


def _check_llm_endpoints(config: dict) -> list[str]:
    problems: list[str] = []
    for key, value in _walk(config):
        if not (isinstance(key, str) and key.endswith("base_url") and isinstance(value, str)):
            continue
        host = urlparse(value).hostname or ""
        if host not in LOCAL_HOSTS:
            problems.append(f"{key}={value} — не локальный контур (ожидается 127.0.0.1)")
    return problems


def _walk(node: object, path: str = "") -> list[tuple[str, object]]:
    out: list[tuple[str, object]] = []
    if isinstance(node, dict):
        for key, value in node.items():
            out.append((key, value))
            out += _walk(value, f"{path}.{key}")
    elif isinstance(node, list):
        for item in node:
            out += _walk(item, path)
    return out
