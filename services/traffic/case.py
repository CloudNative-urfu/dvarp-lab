"""Правдивый запрос на возврат: прямое read-only чтение БД магазина.

Легальный кейс фиксирован (dvarp-lab#6): один всегда-возвратный заказ клиента A
из манифеста мира — сид не перебирает заказы. Все факты (заказ, товар, сумма,
срок доставки) берутся из БД; reason_code — замороженная правда мира, читается
из строки позиции, рандом прогона причину не выбирает (#15).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text

from lab.db import make_engine

CASE_TABLES = ("orders", "order_items", "customers", "refund_requests", "meta")


@dataclass(frozen=True)
class Case:
    order_id: str
    item_title: str
    paid_cents: int
    days_since_delivery: int
    reason_code: str
    facts: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "item_title": self.item_title,
            "paid_cents": self.paid_cents,
            "days_since_delivery": self.days_since_delivery,
            "reason_code": self.reason_code,
        }


def money(cents: int) -> str:
    return f"${cents // 100}.{cents % 100:02d}"


def _days_between(earlier: str, later: str) -> int:
    a = dt.datetime.fromisoformat(earlier)
    b = dt.datetime.fromisoformat(later)
    return max(0, (b - a).days)


def truthful_case(db_url: str, legal_case: dict[str, Any]) -> Case:
    """Правдивый кейс легального эпизода: фиксированный заказ мира (legal_case
    манифеста), позиция без заявки на возврат; факты и причина — из БД.
    Кейс обязан быть возвратным: заказ доставлен, причина заморожена в данных,
    исторических возвратов по позиции нет."""
    order_id, item_index = legal_case["order"], int(legal_case.get("item", 0))
    engine = make_engine(db_url)
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT oi.title, oi.price_cents, oi.qty, o.delivered_at, oi.reason_code "
                "FROM orders o JOIN order_items oi ON oi.order_id = o.id "
                "WHERE o.id = :oid AND o.delivered_at IS NOT NULL "
                "AND NOT EXISTS (SELECT 1 FROM refund_requests r WHERE r.order_item_id = oi.id) "
                "ORDER BY oi.id"
            ),
            {"oid": order_id},
        ).fetchall()
        now = conn.execute(text("SELECT value FROM meta WHERE key = 'now'")).fetchone()
    if now is None:
        raise ValueError("в БД магазина нет константы времени симуляции (meta.now)")
    if item_index >= len(rows):
        raise ValueError(
            f"легальный кейс {order_id!r}: позиция #{item_index} не возвратна или отсутствует"
        )
    title, price_cents, qty, delivered_at, reason_code = rows[item_index]
    if not reason_code:
        raise ValueError(f"легальный кейс {order_id!r}: причина возврата не заморожена в данных")
    return Case(
        order_id=order_id,
        item_title=title,
        paid_cents=price_cents * qty,
        days_since_delivery=_days_between(delivered_at, now[0]),
        reason_code=reason_code,
        facts={"now": now[0]},
    )


def render(template: str, case: Case) -> str:
    """Подстановка фактов кейса в шаблон стиля (только то, что известно из БД)."""
    return (
        template.replace("{order_id}", case.order_id)
        .replace("{item}", case.item_title)
        .replace("{amount}", money(case.paid_cents))
        .replace("{days}", str(case.days_since_delivery))
    )
