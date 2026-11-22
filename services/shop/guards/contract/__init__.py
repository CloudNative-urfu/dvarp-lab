"""Компонент `guard_contract`: единый контракт плагина-гвардрейла (FR-1.5–FR-1.8).

- `types` — вход (`GuardInput`: текст, `ContextFragment` с происхождением, `TrustedTask`,
  неисполненный `ProposedCall`) и закрытый сигнал (`GuardSignal`: allow/flag/block/score);
- `plugin` — базовый класс `GuardPlugin` (метаданные, замороженные параметры, отпечаток) и
  `GuardRuntime` (БД только на чтение, начисление затрат, вызов модели-детектора);
- `registry` — `GuardRegistry` (каталог плагинов, NFR-2.4 только builtin/self_hosted,
  адаптеры выключены по умолчанию) и замороженный `GuardSet` конфигурации;
- `host` — `GuardHost`: вызов плагина с замером latency/CPU, записью `guard_signal`/
  `guard_error` в журнал и обнаружением записи в БД;
- `context` — фрагменты контекста из результатов чтения исполнителя.

Плагины не знают об агенте, агент не знает о плагинах (FR-1.9): связывает их политика.
CLI: `python3 -m services.shop.guards.contract demo`.
"""

from .context import fragments_from_read
from .host import GuardHost, GuardResult, input_digest
from .plugin import (
    DEPLOYMENTS,
    MECHANISMS,
    GuardPlugin,
    GuardRuntime,
    open_readonly,
    validate_plugin_class,
)
from .registry import DEFAULT_REGISTRY, GuardRegistry, GuardSet, Installed, register
from .types import (
    FORBIDDEN_SIGNAL_KEYS,
    STAGES,
    TRUSTED_PROVENANCES,
    ContextFragment,
    GuardContractError,
    GuardContractViolation,
    GuardInput,
    GuardSignal,
    ProposedCall,
    TrustedTask,
    as_signal,
    fragments,
    freeze,
    thaw,
)

CONTRACT_VERSION = "guard-contract-1"

__all__ = [
    "CONTRACT_VERSION",
    "DEFAULT_REGISTRY",
    "DEPLOYMENTS",
    "FORBIDDEN_SIGNAL_KEYS",
    "MECHANISMS",
    "STAGES",
    "TRUSTED_PROVENANCES",
    "ContextFragment",
    "GuardContractError",
    "GuardContractViolation",
    "GuardHost",
    "GuardInput",
    "GuardPlugin",
    "GuardRegistry",
    "GuardResult",
    "GuardRuntime",
    "GuardSet",
    "GuardSignal",
    "Installed",
    "ProposedCall",
    "TrustedTask",
    "as_signal",
    "fragments",
    "fragments_from_read",
    "freeze",
    "input_digest",
    "open_readonly",
    "register",
    "thaw",
    "validate_plugin_class",
]
