"""Компонент `evaluator`: независимый оценщик эпизода — сверка итогового состояния БД с
ground truth без чтения текста агента (FR-1.18) и явное различение исходов атаки
`executed`/`refused`/`ignored` в журнале (FR-1.19).

- `state` — изменения состояния эпизода, предикаты нарушений, сверка с ожидаемым исходом;
- `evidence` — структурированные свидетельства журнала с вырезанным текстом сторон;
- `evaluator` — `capture_start`, `evaluate`, `finalize_pair` (slow/burn), `record`, `summarize`.

Только стандартная библиотека. CLI: `python3 -m services.shop.evaluator demo`.
"""

from .evaluator import (
    EPISODE_KINDS,
    EVALUATOR_V2_VERSION,
    EVALUATOR_VERSION,
    EVALUATOR_VERSIONS,
    TASK_STATUSES,
    EpisodeTruth,
    StartState,
    Verdict,
    capture_start,
    evaluate,
    finalize_pair,
    record,
    summarize,
)
from .evidence import (
    BLOCKING_DENIALS,
    BLOCKING_POLICY_ACTIONS,
    TEXT_KEYS,
    LogEvidence,
    collect,
    strip_text,
    structured_view,
)
from .state import (
    EvaluationError,
    StateChanges,
    check_predicate,
    extract_changes,
    task_matches,
    violations,
)

__all__ = [
    "BLOCKING_DENIALS",
    "BLOCKING_POLICY_ACTIONS",
    "EPISODE_KINDS",
    "EVALUATOR_V2_VERSION",
    "EVALUATOR_VERSION",
    "EVALUATOR_VERSIONS",
    "TASK_STATUSES",
    "TEXT_KEYS",
    "EpisodeTruth",
    "EvaluationError",
    "LogEvidence",
    "StartState",
    "StateChanges",
    "Verdict",
    "capture_start",
    "check_predicate",
    "collect",
    "evaluate",
    "extract_changes",
    "finalize_pair",
    "record",
    "strip_text",
    "structured_view",
    "summarize",
    "task_matches",
    "violations",
]
