"""Component `guards`: the guarded side of shop_svc — boundary + executor, guardrail
contract, plugins, reaction policy, tools.

- `boundary` — immutable boundary declaration: roles, operations, codes, checks; the
  `BOUNDARY_FINGERPRINT` fingerprint;
- `executor` — `Session`, `Executor.execute(role, op, **args)` → `ExecResult`; journal
  `exec_request`/`exec_result`, transactions with rollback, idempotent replay;
- `contract` — the guardrail plugin contract;
- `plugins` — built-in offline plugins and disabled-by-default OSS adapters;
- `policy` — the installation-point pipeline and the reaction policy;
- `tools` — exactly five refund-agent tools over the executor.
"""

from services.shop.guards.boundary import (
    AGENT_JUDGMENT_RULES,
    BOUNDARY_FINGERPRINT,
    BOUNDARY_FINGERPRINTS,
    BOUNDARY_V1_TO_V2,
    BOUNDARY_V2_FINGERPRINT,
    BOUNDARY_V2_TO_V2R,
    BOUNDARY_V2_VERSION,
    BOUNDARY_V2R_FINGERPRINT,
    BOUNDARY_V2R_VERSION,
    BOUNDARY_VERSION,
    BOUNDARY_VERSIONS,
    CHECKS,
    CHECKS_V2,
    CHECKS_V2R,
    DENIAL_CODES,
    DENIAL_CODES_V2,
    FINALIZING_OPS,
    OPS,
    READ_OPS,
    REFUSAL_CODES_BY_ROLE,
    REVIEW_REASONS_BY_ROLE,
    ROLE_OPS,
    ROLES,
    ROUTABLE_DENIALS,
    SERVER_ROUTING_ROLE,
    SERVER_RULE_BOUNDARIES,
    TRUSTED_WRITER_ROLES,
    WRITE_OPS,
    boundary_spec,
    boundary_spec_v2,
    boundary_spec_v2r,
)
from services.shop.guards.executor import (
    AGENT_MESSAGES,
    ExecResult,
    Executor,
    ExecutorError,
    Session,
)

__all__ = [
    "AGENT_JUDGMENT_RULES",
    "AGENT_MESSAGES",
    "BOUNDARY_FINGERPRINT",
    "BOUNDARY_FINGERPRINTS",
    "BOUNDARY_V1_TO_V2",
    "BOUNDARY_V2R_FINGERPRINT",
    "BOUNDARY_V2R_VERSION",
    "BOUNDARY_V2_FINGERPRINT",
    "BOUNDARY_V2_TO_V2R",
    "BOUNDARY_V2_VERSION",
    "BOUNDARY_VERSION",
    "BOUNDARY_VERSIONS",
    "CHECKS",
    "CHECKS_V2",
    "CHECKS_V2R",
    "DENIAL_CODES",
    "DENIAL_CODES_V2",
    "FINALIZING_OPS",
    "OPS",
    "READ_OPS",
    "REFUSAL_CODES_BY_ROLE",
    "REVIEW_REASONS_BY_ROLE",
    "ROLES",
    "ROLE_OPS",
    "ROUTABLE_DENIALS",
    "SERVER_ROUTING_ROLE",
    "SERVER_RULE_BOUNDARIES",
    "TRUSTED_WRITER_ROLES",
    "WRITE_OPS",
    "ExecResult",
    "Executor",
    "ExecutorError",
    "Session",
    "boundary_spec",
    "boundary_spec_v2",
    "boundary_spec_v2r",
]
