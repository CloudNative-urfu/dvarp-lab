"""Компонент `manual_queue`: очередь ручных разборов (FR-1.15, FR-1.16) и записи случаев.

- `model` — дискретно-событийная модель: в измерительный путь не входит, остаётся
  проверкой аналитической формулы в тестах; `CaseRecord` и `DISCIPLINES`
  используются замороженным кодом защиты;
- `arrivals` — детерминированное расписание прибытий потока прогона (легальный поток не
  зависит от атак, NFR-2.8).

Аналитика очереди (Эрланг C, отвал, сценарий ρ₀×p_att) живёт в
`services/metrics/queue.py` — расчёт post-hoc в metrics_svc (сбор ≠ расчёт,
issue #12/#34); прежний `analytic.py` удалён как дубликат со устаревшими
non-claims.
"""

from .arrivals import Slot, attack_count, build_flow, poisson_times
from .model import (
    DISCIPLINES,
    OPERATOR_LEVELS,
    SERVICE_DISTS,
    SERVICE_MODES,
    CaseOutcome,
    CaseRecord,
    ManualQueue,
    QueueConfig,
    QueueError,
    QueueResult,
    cases_from_mapping,
    simulate,
)

__all__ = [
    "DISCIPLINES",
    "OPERATOR_LEVELS",
    "SERVICE_DISTS",
    "SERVICE_MODES",
    "CaseOutcome",
    "CaseRecord",
    "ManualQueue",
    "QueueConfig",
    "QueueError",
    "QueueResult",
    "Slot",
    "attack_count",
    "build_flow",
    "cases_from_mapping",
    "poisson_times",
    "simulate",
]
