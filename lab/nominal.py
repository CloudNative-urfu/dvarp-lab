"""Номинальная проверка конфигурации перед каждым прогоном и маркировка remote-эндпоинтов.

Локальность LLM-эндпоинтов не гейт: любой http(s) base_url допускается, а
не-локальный автоматически включает тройной guard remote-прогона (инвариант 8c).
Ростер моделей — справочник заморозки, тоже не гейт.
"""

from __future__ import annotations

import ipaddress
import os
from collections.abc import Mapping
from urllib.parse import urlsplit

from lab.modelspec import FROZEN_DIR, ModelSpec

# base_url живых клиентов: агент shop_svc, легальный клиент traffic_svc, атакующий attack_svc
LLM_BASE_URL_ENV = (
    "RESEARCH_LLM_BASE_URL",
    "LAB_CUSTOMER_LLM_BASE_URL",
    "LAB_ATTACKER_LLM_BASE_URL",
    "LAB_GUARD_LLM_BASE_URL",
)


def is_local_url(url: str) -> bool:
    """Локальный контур = loopback (127.0.0.0/8, ::1, localhost); всё прочее — remote."""
    host = (urlsplit(url.strip()).hostname or "").lower()
    if host == "localhost" or host.endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def remote_endpoints(environ: Mapping[str, str] | None = None) -> list[str]:
    """Заданные в env не-локальные base_url живых клиентов (только имена переменных)."""
    env = os.environ if environ is None else environ
    return [
        key
        for key in LLM_BASE_URL_ENV
        if (env.get(key) or "").strip() and not is_local_url(env[key])
    ]


def check_config(
    config_name: str,
    config: dict,
    agents: list[ModelSpec],
    allow_remote: bool = False,
) -> list[str]:
    """Возвращает список замечаний; пустой список — прогон можно запускать.

    Проверяется только принадлежность конфига замороженному набору. allow_remote
    и agents приняты для совместимости и не гейтят (remote маркируется, а не запрещается).
    """
    problems: list[str] = []
    configs_dir = FROZEN_DIR / "configs"
    if not (configs_dir / f"{config_name}.json").exists():
        problems.append(f"конфиг {config_name} отсутствует в frozen/configs/")
    known = {p.stem for p in configs_dir.glob("*.json")}
    if known and config_name not in known:
        problems.append(f"конфиг {config_name} не из замороженного набора")
    return problems
