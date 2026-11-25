"""Замороженный мир магазина (frozen/seed_worlds) — единственный статический мир.

Манифест мира — файл вне БД защитника: привязка ролей (legal/attack) к клиенту,
легальный кейс, фиктивный заказ и факты заказов для сборки промпта атакующего
(dvarp-lab#6). Один и тот же загрузчик используют shop_svc, traffic_svc и
attack_svc; в БД магазина следа роли не остаётся. Реестр целей
(`frozen/corpus/goals.json`) ссылается на заказы мира — здесь же проверяется,
что ссылки целостны. Загрузка fail-closed: битый мир не запускает прогон.

Хеш-пин версии мира (`dataset_hash`) считает shop_svc через
`services.shop.repro.hash_tree`; lab не зависит от сервисов.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import Any

FROZEN_DIR = Path(__file__).resolve().parents[1] / "frozen"
SEED_WORLDS_DIR = FROZEN_DIR / "seed_worlds"
GOALS_PATH = FROZEN_DIR / "corpus" / "goals.json"
DEFAULT_WORLD = "world_a"

MANIFEST_SCHEMA = "dvarp.world-manifest/1"
GOALS_SCHEMA = "dvarp.goals/1"


class WorldError(ValueError):
    pass


def world_dir(name: str = DEFAULT_WORLD) -> Path:
    d = SEED_WORLDS_DIR / name
    if not d.is_dir():
        raise WorldError(f"мир {name!r} отсутствует в frozen/seed_worlds/")
    return d


def load_manifest(name: str = DEFAULT_WORLD) -> dict[str, Any]:
    """Манифест мира: роли → клиент → заказы, легальный кейс, фиктивный заказ,
    факты заказов, константа времени. Схема и минимальные связи проверяются."""
    path = world_dir(name) / "manifest.json"
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise WorldError(f"манифест мира {name!r} не читается: {exc}") from None
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise WorldError(f"{path.name}: schema должен быть {MANIFEST_SCHEMA!r}")
    if manifest.get("world") != name:
        raise WorldError(f"{path.name}: поле world не совпадает с каталогом {name!r}")
    if not isinstance(manifest.get("now"), str) or not manifest["now"].endswith("Z"):
        raise WorldError(f"{path.name}: now — ISO-8601 UTC с суффиксом Z")
    clients = manifest.get("clients")
    if not isinstance(clients, list) or not clients:
        raise WorldError(f"{path.name}: clients — непустой список")
    ids = [c.get("id") for c in clients]
    if any(not i for i in ids) or len(set(ids)) != len(ids):
        raise WorldError(f"{path.name}: клиенты без id или с повторами")
    for c in clients:
        roles = c.get("roles")
        if not isinstance(roles, list) or not roles:
            raise WorldError(f"{path.name}: у клиента {c.get('id')} нет ролей")
        if not isinstance(c.get("orders"), list) or not c["orders"]:
            raise WorldError(f"{path.name}: у клиента {c.get('id')} нет заказов")
    for role in ("legal", "attack"):
        if not any(role in c["roles"] for c in clients):
            raise WorldError(f"{path.name}: ни один клиент не несёт роль {role!r}")
    orders = manifest.get("orders")
    if not isinstance(orders, dict) or not orders:
        raise WorldError(f"{path.name}: facts заказов обязательны")
    bound = {o for c in clients for o in c["orders"]}
    if set(orders) != bound:
        raise WorldError(f"{path.name}: facts заказов не совпадают с заказами клиентов")
    for oid, facts in orders.items():
        _check_order_facts(path.name, oid, facts)
    _check_legal_case(manifest)
    _check_fictive(manifest)
    return manifest


def _check_order_facts(where: str, oid: str, facts: Any) -> None:
    if not isinstance(facts, dict):
        raise WorldError(f"{where}: facts заказа {oid} — объект")
    delivered = facts.get("delivered_at")
    if delivered is not None and not (isinstance(delivered, str) and delivered.endswith("Z")):
        raise WorldError(f"{where}: {oid}.delivered_at — ISO-8601 UTC или null")
    items = facts.get("items")
    if not isinstance(items, list) or not items:
        raise WorldError(f"{where}: у заказа {oid} нет позиций")
    for it in items:
        if not isinstance(it.get("title"), str) or not it["title"]:
            raise WorldError(f"{where}: у позиции заказа {oid} нет наименования")
        for f in ("price_cents", "qty"):
            v = it.get(f)
            if isinstance(v, bool) or not isinstance(v, int) or v <= 0:
                raise WorldError(f"{where}: {oid}.items.{f} — целое > 0")
        if it.get("final_sale") not in (0, 1):
            raise WorldError(f"{where}: {oid}.items.final_sale — 0 или 1")


def _check_legal_case(manifest: dict[str, Any]) -> None:
    case = manifest.get("legal_case")
    if not isinstance(case, dict):
        raise WorldError("манифест: legal_case обязателен")
    client = next((c for c in manifest["clients"] if c["id"] == case.get("customer")), None)
    if client is None:
        raise WorldError(f"манифест: legal_case.customer {case.get('customer')!r} не найден")
    if case.get("order") not in client["orders"]:
        raise WorldError(f"манифест: legal_case.order {case.get('order')!r} не заказ клиента")
    if "legal" not in client["roles"]:
        raise WorldError("манифест: легальный кейс привязан к клиенту без роли legal")
    if (
        isinstance(case.get("item"), bool)
        or not isinstance(case.get("item"), int)
        or case["item"] < 0
    ):
        raise WorldError("манифест: legal_case.item — индекс позиции")


def _check_fictive(manifest: dict[str, Any]) -> None:
    fictive = manifest.get("fictive_order")
    if not isinstance(fictive, dict):
        raise WorldError("манифест: fictive_order обязателен")
    if fictive.get("id") in manifest["orders"] or any(
        fictive.get("id") in c["orders"] for c in manifest["clients"]
    ):
        raise WorldError("манифест: фиктивный заказ не должен существовать в данных мира")
    _check_order_facts("манифест: fictive_order", fictive.get("id", "?"), fictive)
    if not isinstance(fictive.get("reason_code"), str):
        raise WorldError("манифест: у фиктивного заказа нет reason_code")


# ------------------------------------------------------------------ goals


def load_goals(manifest: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    """Реестр целей (frozen/corpus/goals.json): ключ → запись; ссылки на заказы
    мира проверяются (реальный заказ клиента или фиктивный заказ манифеста)."""
    try:
        data = json.loads(GOALS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise WorldError(f"реестр целей не читается: {exc}") from None
    if data.get("schema") != GOALS_SCHEMA:
        raise WorldError(f"{GOALS_PATH.name}: schema должен быть {GOALS_SCHEMA!r}")
    entries = data.get("goals")
    if not isinstance(entries, list) or not entries:
        raise WorldError(f"{GOALS_PATH.name}: goals — непустой список")
    goals: dict[str, dict[str, Any]] = {}
    for g in entries:
        name = g.get("name")
        if not name or name in goals:
            raise WorldError(f"{GOALS_PATH.name}: имя цели {name!r} пустое или повторяется")
        claim = g.get("claim")
        if not isinstance(claim, str) or not claim.strip():
            raise WorldError(f"{GOALS_PATH.name}: у цели {name!r} нет претензии")
        goals[name] = g
    manifest = manifest if manifest is not None else load_manifest()
    for name, g in goals.items():
        order = g.get("order")
        if order == "fictive":
            continue
        known = any(order in c["orders"] for c in manifest["clients"])
        if not known or order not in manifest["orders"]:
            raise WorldError(f"{GOALS_PATH.name}: цель {name!r} ссылается на чужой заказ {order!r}")
    return goals


def goal_binding(goal: dict[str, Any]) -> str | None:
    """Заказ претензии цели: id заказа мира или None для фиктивного заказа."""
    return None if goal["order"] == "fictive" else goal["order"]


# ------------------------------------------------------------------ claim facts


def days_since(delivered_at: str | None, now: str) -> int | None:
    """Дней с доставки по замороженным временам мира (без часов симуляции)."""
    if not delivered_at:
        return None
    a = dt.datetime.fromisoformat(delivered_at[:-1])
    b = dt.datetime.fromisoformat(now[:-1])
    return max(0, (b - a).days)


def money(cents: int) -> str:
    return f"${cents // 100}.{cents % 100:02d}"


def order_facts(
    manifest: dict[str, Any], order_ref: str | None, item_index: int = 0
) -> dict[str, Any]:
    """Факты заказа мира для сборки промпта атакующего: только замороженные данные.

    order_ref=None — фиктивный заказ манифеста. Возвращает order_id, item, amount
    (требуемая сумма: цена × количество позиции), days (дней с доставки), qty.
    """
    if order_ref is None:
        fictive = manifest["fictive_order"]
        oid, facts = fictive["id"], fictive
    else:
        oid, facts = order_ref, manifest["orders"][order_ref]
    items = facts["items"]
    if item_index >= len(items):
        raise WorldError(f"в заказе {oid} нет позиции #{item_index}")
    it = items[item_index]
    return {
        "order_id": oid,
        "item": it["title"],
        "amount_cents": it["price_cents"] * it["qty"],
        "days": days_since(facts.get("delivered_at"), manifest["now"]),
        "qty": it["qty"],
    }


def claim_facts(goal: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    """Факты претензии цели: факты заказа мира + замороженные преувеличения цели
    (требуемая сумма/количество/товар подмены). Всё — данные, никакой генерации."""
    facts = order_facts(manifest, goal_binding(goal), goal.get("item", 0))
    if goal.get("claim_amount_cents") is not None:
        facts["amount_cents"] = goal["claim_amount_cents"]
    if goal.get("claim_qty") is not None:
        facts["qty"] = goal["claim_qty"]
    if goal.get("claim_item") is not None:
        facts["item"] = goal["claim_item"]
    return facts


_LEFTOVER = re.compile(r"\{[a-z_0-9]+\}")


def render_claim(template: str, facts: dict[str, Any]) -> str:
    """Механическая подстановка фактов манифеста в замороженную претензию:
    без рандома и без генерации (данные претензии входят в промпт как есть)."""
    out = template
    out = out.replace("{order_id}", facts["order_id"])
    out = out.replace("{item}", facts["item"])
    out = out.replace("{amount}", money(facts["amount_cents"]))
    out = out.replace("{days}", str(facts["days"] if facts["days"] is not None else 0))
    out = out.replace("{qty}", str(facts["qty"]))
    if _LEFTOVER.search(out):
        raise WorldError(f"претензия содержит незнакомый плейсхолдер: {out!r}")
    return out
