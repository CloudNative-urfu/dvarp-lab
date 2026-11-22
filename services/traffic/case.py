"""Правдивый запрос на возврат: прямое read-only чтение БД магазина."""

from __future__ import annotations

import datetime as dt
import random
from dataclasses import dataclass, field
from typing import Any

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


def truthful_case(db_url: str, seed: int) -> Case:
    """Правдивый кейс из БД магазина: доставленный заказ, позиция без заявки на возврат.

    Все факты (заказ, товар, сумма, срок доставки) берутся из БД; reason_code —
    детерминированный выбор от seed (причина в БД не хранится).
    """
    engine = make_engine(db_url)
    with engine.connect() as conn:
        rows = conn.exec_driver_sql(
            "SELECT o.id, oi.title, oi.price_cents, oi.qty, o.delivered_at "
            "FROM orders o JOIN order_items oi ON oi.order_id = o.id "
            "WHERE o.delivered_at IS NOT NULL AND oi.price_cents > 0 "
            "AND NOT EXISTS (SELECT 1 FROM refund_requests r WHERE r.order_item_id = oi.id) "
            "ORDER BY o.id, oi.id"
        ).fetchall()
        now = conn.exec_driver_sql("SELECT value FROM meta WHERE key = 'now'").fetchone()
    if not rows or now is None:
        raise ValueError("в БД магазина нет правдивого кейса (доставленные заказы без возвратов)")
    rng = random.Random(seed)
    order_id, title, price_cents, qty, delivered_at = rows[rng.randrange(len(rows))]
    return Case(
        order_id=order_id,
        item_title=title,
        paid_cents=price_cents * qty,
        days_since_delivery=_days_between(delivered_at, now[0]),
        reason_code=rng.choice(["defective", "wrong_item", "not_as_described", "changed_mind"]),
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
