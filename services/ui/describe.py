"""Описание консоли данными: оси, поля, пресеты, словарь терминов.

Фронт только рисует то, что здесь описано (новая ось, пресет или термин — правка
этого модуля, не JS). Источник значений — frozen через launcher.axes; расчётов нет.
"""

from __future__ import annotations

import os
from typing import Any

from lab.nominal import remote_endpoints
from launcher.axes import GUARD_VOLUME, NUMERIC_AXES, axis_universe

ENUM_MODES = ["point", "range", "set", "all", "all_limited"]
NUMERIC_MODES = ["point", "range", "set", "all_limited"]

AXES: list[dict[str, Any]] = [
    {"name": "configs", "label": "Конфигурации защиты"},
    {"name": "styles", "label": "Стили общения"},
    {"name": "tactics", "label": "Тактики атаки", "splits": ["dev", "holdout"]},
    {"name": "agent_models", "label": "Модели агента", "free": True, "role": "agent"},
    {"name": "attacker_models", "label": "Модели атакующего", "free": True, "role": "attacker"},
    {"name": "episodes", "label": "Эпизоды на ячейку"},
    {"name": "seeds", "label": "Сиды (миры)"},
]

RUN_FIELDS: list[dict[str, Any]] = [
    {"name": "budget", "label": "Бюджет ходов атаки", "type": "int", "default": 8, "min": 1},
    {
        "name": "compute",
        "label": "Посчитать метрики после прогона",
        "type": "bool",
        "default": False,
    },
]


def _remote_models() -> dict[str, str | None]:
    """Имена моделей из env процесса (пинуются в манифестах, не секрет); ключи и base_url — никогда."""

    def name(var: str) -> str | None:
        return (os.environ.get(var) or "").strip() or None

    return {"agent": name("RESEARCH_LLM_MODEL"), "attacker": name("LAB_ATTACKER_LLM_MODEL")}


def axes() -> list[dict[str, Any]]:
    remote = _remote_models()
    out = []
    for ax in AXES:
        d = dict(ax)
        if ax["name"] in NUMERIC_AXES:
            d.update(kind="numeric", modes=NUMERIC_MODES)
            d["default"] = {"mode": "point", "point": 0 if ax["name"] == "seeds" else 1}
        else:
            universe = axis_universe(ax["name"])
            if ax.get("free") and remote.get(ax["role"]):
                # имя модели из env процесса — первым вариантом (вне ростера, пин remote-verification)
                universe = [remote[ax["role"]], *[v for v in universe if v != remote[ax["role"]]]]
            d.update(kind="enum", modes=ENUM_MODES, universe=universe)
            d["default"] = {"mode": "point", "point": universe[0]} if universe else {"mode": "all"}
        out.append(d)
    return out


def probe_fields(ax: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by = {a["name"]: a for a in ax}

    def pick(axis: str, name: str, label: str, optional: bool = False) -> dict[str, Any]:
        a = by[axis]
        return {
            "name": name,
            "label": label,
            "type": "select",
            "options": ([""] if optional else []) + a["universe"],
            "free": bool(a.get("free")),
            "default": "" if optional else (a["universe"][0] if a["universe"] else ""),
        }

    return [
        pick("configs", "config", "Конфигурация"),
        pick("tactics", "tactic", "Тактика"),
        pick("styles", "style", "Стиль", optional=True),
        pick("agent_models", "agent_model", "Модель агента"),
        pick("attacker_models", "attacker_model", "Модель атакующего", optional=True),
        {"name": "budget", "label": "Бюджет ходов", "type": "int", "default": 8, "min": 1},
        {"name": "seed", "label": "Сид (пусто — от тактики)", "type": "int", "default": None},
    ]


def presets(ax: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Готовые спецификации осей: smoke — одна ячейка; пилот — все тактики одной пары."""
    point = {a["name"]: a["default"] for a in ax}
    return [
        {
            "name": "smoke",
            "label": "Smoke: одна ячейка + метрики",
            "spec": {**point, "budget": 6, "compute": True},
        },
        {
            "name": "pilot",
            "label": "Пилот: все тактики, один конфиг и стиль",
            "spec": {**point, "tactics": {"mode": "all"}, "budget": 8, "compute": False},
        },
    ]


TERMS: dict[str, str] = {
    # оси и поля
    "configs": "Конфигурация защиты: набор гвардрейлов и политика (frozen/configs)",
    "config": "Конфигурация защиты: набор гвардрейлов и политика",
    "config_name": "Конфигурация защиты, на которой шёл эпизод",
    "styles": "Стиль общения клиента; общий для легальной и атакующей ноги пары",
    "style": "Стиль общения: тон обеих ног пары",
    "tactics": "Тактика атаки из замороженного корпуса",
    "tactic": "Тактика атаки из замороженного корпуса",
    "agent_models": "Модель агента поддержки (защищаемая сторона)",
    "attacker_models": "Модель атакующего; пусто — та же, что у агента",
    "episodes": "Эпизодов (пар legal+attack) на ячейку",
    "seeds": "Сид = «мир»: вариант детерминированных данных магазина и кейса",
    "seed": "Сид = «мир»: вариант детерминированных данных магазина и кейса",
    "budget": "Максимум ходов атакующего в эпизоде",
    "split": "Раздел корпуса тактик: dev — разработка, holdout — отложенная проверка",
    "point": "Одно значение",
    "range": "Непрерывный срез отсортированного списка от и до",
    "set": "Смесь: явный список значений",
    "all": "Все значения оси",
    "all_limited": "Срез: сдвиг от начала и лимит числа значений",
    "remote_llm": "Прогон на не-локальном LLM-эндпоинте: только для проверки, в метрики статьи не идёт",
    "model_spec": "Пин модели: имя, роль, размер (млрд параметров), ревизия весов",
    "params_b": "Размер модели, млрд параметров",
    "revision": "Ревизия весов; remote-verification — модель вне ростера",
    "run_id": "Идентификатор прогона кампании",
    "legal": "Легальная нога: правдивый клиент с настоящим возвратом",
    "attack": "Атакующая нога: попытка добиться незаконного возврата",
    "customer": "Реплика клиента (легального или атакующего) в канал",
    "agent": "Ответ агента поддержки",
    "probe": "Probe-атаки: одиночные без парной ноги; по умолчанию не входят в метрики",
    # исходы
    "budget_exhausted": "Атака исчерпала бюджет ходов, не добившись результата",
    "refund_granted": "Возврат создан",
    "refused": "Агент отказал",
    "escalated": "Передано оператору ручной очереди",
    "turn_limit": "Диалог оборван лимитом ходов",
    "attacker_stopped": "Атакующий сам остановился (DONE)",
    "closed": "Агент закрыл диалог",
    "outcome": "Исход эпизода",
    "turns": "Число ходов эпизода",
    "attempts": "Число попыток атакующего",
    # метрики
    "n_attack": "Число атакующих эпизодов",
    "n_legal": "Число легальных эпизодов",
    "w_A": "Доля атакующего трафика",
    "w_L": "Доля легального трафика",
    "V": "Доля нарушений: атак, добившихся исполнения",
    "V_k": "Число атак, добившихся исполнения",
    "V_n": "Число атакующих эпизодов в знаменателе V",
    "R": "Доля неоправданных отказов легальным клиентам",
    "E": "Доля обращений, ушедших в эскалацию оператору",
    "detection": "Матрица ошибок детекции: TP/FP/FN/TN",
    "TP": "Атаки, пойманные защитой",
    "FP": "Ложные срабатывания на чистом трафике",
    "FN": "Пропущенные атаки",
    "TN": "Чистые обращения без срабатывания",
    "TPR": "Доля атак, которую защита поймала",
    "FPR": "Доля чистых обращений с ложным срабатыванием",
    "precision": "Точность детекции: доля верных срабатываний среди всех",
    "detection_tpr": "TPR — доля атак, которую защита поймала",
    "detection_fpr": "FPR — доля чистых обращений с ложным срабатыванием",
    "detection_precision": "Точность детекции: доля верных срабатываний среди всех",
    "break_even": "Окупаемость конфигурации относительно эталона g0 той же модели",
    "break_even_status": "Статус окупаемости (§9.2)",
    "status": "Статус окупаемости (§9.2)",
    "formula_status": "Статус по формуле при базовых ценах",
    "L_star": "Точка окупаемости L*: цена нарушения, начиная с которой защита окупается",
    "L_star_min": "L* при самых выгодных для защиты ценах",
    "L_star_max": "L* при самых невыгодных для защиты ценах",
    "prices_robust": "Статус одинаков на всех границах цен",
    "statuses_over_bounds": "Статусы на нижней, базовой и верхней границах цен",
    "bounds": "L* и статус на границах цен (low/base/high)",
    "low": "Нижняя граница цен",
    "base": "Базовые цены",
    "high": "Верхняя граница цен",
    "numerator": "Числитель L*: прирост издержек защиты относительно эталона",
    "terms": "Слагаемые числителя L*",
    "decision_at_L_viol": "Окупается ли защита при заданных ценах нарушения",
    "dV": "Снижение доли нарушений относительно эталона",
    "dR": "Прирост неоправданных отказов относительно эталона",
    "dE": "Прирост эскалаций относительно эталона",
    "dC_ep": "Прирост стоимости обслуживания эпизода (в лабе 0)",
    "dC_guard": "Прирост стоимости гвардрейлов (в лабе 0)",
    "refuse": "Издержки неоправданных отказов",
    "attack_service": "Издержки обслуживания атак",
    "guard": "Издержки гвардрейлов",
    "manual": "Издержки ручной проверки",
    "reference": "Эталонная конфигурация (g0): L* не считается",
    "threshold": "Окупается при цене нарушения выше L*",
    "pays_at_any_price": "Окупается при любой цене нарушения",
    "no_safety_gain": "Нарушений не меньше эталона: выигрыша нет",
    "more_violations": "Нарушений больше, чем у эталона",
    "no_reference": "Нет эталона g0 для этой модели в данных",
}


def describe() -> dict[str, Any]:
    ax = axes()
    return {
        "axes": ax,
        "run_fields": RUN_FIELDS,
        "probe_fields": probe_fields(ax),
        "presets": presets(ax),
        "terms": TERMS,
        "guard": GUARD_VOLUME,
        "remote_models": _remote_models(),
        "remote_endpoints": remote_endpoints(),
    }
