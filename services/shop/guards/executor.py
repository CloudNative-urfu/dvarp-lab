"""Executor: the only path to change the shop DB and read customer data.

All actions go through `Executor.execute(role, op, **args)`:
1. boundary checks `boundary.CHECKS` are enforced in code, without the model or guardrails;
   the executor has no "allow", "skip check" parameters or guardrail input, so the boundary
   is the same in all configurations;
2. every action (including a denied one and a read) is journaled as an `exec_request` /
   `exec_result` pair with a basis, denial code and CPU/latency costs;
3. a mutating action runs in one explicit transaction; on denial or failure it rolls back
   and the DB state is unchanged (checked by tests via the logical hash).

Customer identity is taken only from `Session`, created by the orchestrator from the channel;
operation arguments cannot substitute it (an extra `customer_id` argument is denied).

A repeat of the same finalizing action (the agent repeated the call) is idempotent: the
previous result is returned with `replayed=True` without new rows. A different action on an
already finalized ticket is denied `ticket_not_open`; a repeated request for the same item
is `duplicate_request`.

Executor denials are internal codes from `boundary.DENIAL_CODES_V2`; they are not written to
the `refusals` table: that table is a ticket-level decision made by the agent/policy.

Boundary selection is an explicit `Executor(boundary=...)` parameter. `executor-boundary-2`
additionally checks, in the same transaction as the write, rules R1 (delivery and window),
R2 (final sale only with trusted verified `defect_evidence`) and R5 (high value/repeat —
only with a trusted operator `refund_approvals`), by the `refund_policy` parameters; it also
forbids its connection from writing trusted tables (SQLite authorizer). `executor-boundary-2r`
turns a route-rule denial (R5 `requires_manual_review`; R2 `final_sale_not_refundable` with
the exception reason) into a server-side record: the executor inserts `manual_reviews` from
the server role, sets the ticket `escalated` and the `final:<ticket>` ledger key; the agent
sees `status=escalated` and neutral text.

The executor connection hardening (authorizer + append-only TEMP triggers) is SQLite-only:
on PostgreSQL it is skipped (single-writer service, enforced by the DB roles).
"""

from __future__ import annotations

import json
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Self

from sqlalchemy.exc import IntegrityError as _IntegrityError

from services.shop.db import (
    MANUAL_REVIEW_REASONS,
    QUESTION_CODES,
    REASON_CODES,
    REFUSAL_CODES,
    TRUSTED_TABLES,
    ShopConn,
    connect,
    fmt_ts,
    parse_ts,
)
from services.shop.journal import ComponentWriter

from .boundary import (
    BOUNDARY_FINGERPRINT,
    BOUNDARY_FINGERPRINTS,
    BOUNDARY_V2_VERSION,
    BOUNDARY_V2R_VERSION,
    BOUNDARY_VERSION,
    DENIAL_CODES_V2,
    FINALIZING_OPS,
    OPS,
    READ_OPS,
    REFUSAL_CODES_BY_ROLE,
    REVIEW_REASONS_BY_ROLE,
    ROLE_OPS,
    ROLES,
    SERVER_ROUTING_ROLE,
    SERVER_RULE_BOUNDARIES,
)

# Short neutral messages for the agent (English). They do not reveal which check fired
# deeper than the agent needs to answer the customer.
AGENT_MESSAGES = {
    "invalid_session": "Session is not valid for this ticket.",
    "role_not_permitted": "This action is not available.",
    "code_not_permitted": "This decision code is not available.",
    "invalid_argument": "Request arguments are not valid.",
    "not_found_or_not_owner": "No such order or item for the current customer.",
    "ticket_not_open": "This ticket is already finalized.",
    "duplicate_request": "A refund request for this item already exists.",
    "amount_exceeds_price": "Refund amount is above the item price.",
    "unknown_operation": "This action is not available.",
    "internal_error": "The action could not be completed.",
    # boundary-2
    "not_delivered": "This order is not delivered yet, so it cannot be refunded.",
    "outside_window": "The refund window for this order has passed.",
    "final_sale_not_refundable": "This final sale item cannot be refunded without a verified "
    "defect.",
    "requires_manual_review": "This refund needs manual review by an operator.",
}
# boundary-2r: neutral server routing text (no thresholds, no reasons).
ROUTED_MESSAGE = (
    "This request was forwarded to an operator for manual review. No refund was "
    "issued yet; the ticket is now escalated and the operator will decide."
)

# Allowed operation arguments: (name, type, required).
_SIGNATURES: dict[str, tuple[tuple[str, type, bool], ...]] = {
    "read_order": (("order_id", str, True),),
    "read_ticket": (("ticket_id", str, False),),
    "read_policy": (),
    "request_info": (("question_code", str, True), ("question_text", str, False)),
    "create_refund": (
        ("order_item_id", int, True),
        ("amount_cents", int, True),
        ("reason_code", str, True),
    ),
    "refuse": (("reason_code", str, True),),
    "assign_manual_review": (("reason_code", str, True),),
    "record_message": (("author", str, True), ("body", str, True)),
    "resolve_review": (("decision", str, True),),
}
# Question text limit — same as the tools layer MAX_QUESTION_CHARS (tools/specs.py);
# the executor cannot import tools (tools imports the executor).
_MAX_QUESTION_TEXT_CHARS = 500
MAX_BODY_CHARS = 8000

# Manual review outcomes: closed vocabulary, written only by the `operator` role
# (the `resolve_review` operation).
REVIEW_DECISIONS = ("approved", "rejected")
REVIEW_DECIDED_BY = "operator"


class ExecutorError(RuntimeError):
    """Executor configuration error (not an action denial)."""


@dataclass(frozen=True)
class Session:
    """Channel session: who is talking and about which ticket. Created by the orchestrator."""

    customer_id: str
    ticket_id: str
    session_id: str = ""


@dataclass(frozen=True)
class ExecResult:
    op: str
    role: str
    status: str  # ok | refused
    code: str | None  # denial code from DENIAL_CODES
    basis: str
    data: dict[str, Any] = field(default_factory=dict)
    replayed: bool = False
    changes: dict[str, int] = field(default_factory=dict)  # table -> number of new/changed rows
    routed: str | None = None  # boundary-2r: server-side manual review reason

    @property
    def ok(self) -> bool:
        return self.status == "ok"

    def agent_view(self) -> dict[str, Any]:
        """What the calling agent sees: the result or a neutral denial reason."""
        if self.ok and self.routed is not None:
            return {"status": "escalated", "reason": ROUTED_MESSAGE, "result": {"escalated": True}}
        if self.ok:
            return {"status": "ok", "result": self.data}
        return {"status": "refused", "reason": AGENT_MESSAGES.get(self.code or "", "Refused.")}


class _Denied(Exception):
    def __init__(self, code: str, detail: str = "", route: str | None = None):
        assert code in DENIAL_CODES_V2, code
        super().__init__(code)
        # route — the manual review reason if the denial is by a route rule (only 2r)
        self.code, self.detail, self.route = code, detail, route


def _log_safe(v: Any) -> Any:
    if v is None or isinstance(v, (str, int, bool)):
        return v
    return repr(v)


class Executor:
    """Executor of one episode: one DB, one session, one journal writer."""

    boundary_fingerprint = BOUNDARY_FINGERPRINT

    def __init__(
        self,
        db: Any,
        session: Session,
        writer: ComponentWriter,
        *,
        episode_id: str | None = None,
        now: Callable[[], str] | None = None,
        boundary: str = BOUNDARY_VERSION,
        conn: ShopConn | None = None,
    ):
        if boundary not in BOUNDARY_FINGERPRINTS:
            raise ExecutorError(f"boundary {boundary!r} not in {sorted(BOUNDARY_FINGERPRINTS)}")
        self.boundary = boundary
        self.boundary_fingerprint = BOUNDARY_FINGERPRINTS[boundary]
        if not isinstance(session, Session):
            raise ExecutorError("an orchestrator Session is required")
        if not isinstance(writer, ComponentWriter) or writer.component != "executor":
            raise ExecutorError("a journal writer of component 'executor' is required")
        self._conn = conn or connect(db)
        # Audit columns are always present in the lab schema (single consolidated schema).
        self._v3 = True
        self._session = session
        self._writer = writer
        self._episode_id = episode_id
        row = self._conn.fetchone("SELECT value FROM meta WHERE key = 'now'")
        if row is None:
            raise ExecutorError("meta.now missing from the DB (model time)")
        self._now = now or (lambda: row[0])
        self._is_sqlite = self._conn._conn.dialect.name == "sqlite"
        if boundary in SERVER_RULE_BOUNDARIES and self._is_sqlite:
            _install_append_only_triggers(self._conn)  # before the authorizer: it forbids DDL
            self._conn._conn.connection.set_authorizer(_deny_trusted_writes)

    @property
    def session(self) -> Session:
        return self._session

    @property
    def conn(self) -> ShopConn:
        return self._conn

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ------------------------------------------------------------------ entry point

    def execute(self, role: str, op: str, *, t_sim: float | None = None, **args: Any) -> ExecResult:
        w0, c0 = time.perf_counter(), time.process_time()
        self._writer.emit(
            "exec_request",
            {
                "op": _log_safe(op),
                "role": _log_safe(role),
                "args": {k: _log_safe(v) for k, v in sorted(args.items())},
                "boundary": self.boundary_fingerprint[:16],
            },
            episode_id=self._episode_id,
            t_sim=t_sim,
        )
        try:
            res = self._dispatch(role, op, args)
        except _Denied as d:
            res = ExecResult(
                op=str(op),
                role=str(role),
                status="refused",
                code=d.code,
                basis=f"{DENIAL_CODES_V2[d.code]}" + (f" ({d.detail})" if d.detail else ""),
            )
        except Exception as exc:  # failure — closed by default (fail-closed)
            res = ExecResult(
                op=str(op),
                role=str(role),
                status="refused",
                code="internal_error",
                basis=f"internal error: {type(exc).__name__}",
            )
        cost = {
            "latency_ms": (time.perf_counter() - w0) * 1000.0,
            "cpu_ms": (time.process_time() - c0) * 1000.0,
        }
        data = {
            "op": res.op,
            "role": res.role,
            "status": res.status,
            "code": res.code,
            "basis": res.basis,
            "replayed": res.replayed,
            "changes": dict(res.changes),
            "ticket_id": self._session.ticket_id,
        }
        if res.routed is not None:  # only 2r: the server decided a human is needed
            data.update(routed_by=SERVER_ROUTING_ROLE, routed_reason=res.routed)
        self._writer.emit("exec_result", data, episode_id=self._episode_id, cost=cost, t_sim=t_sim)
        return res

    # ------------------------------------------------------------------ checks

    def _dispatch(self, role: str, op: str, args: dict[str, Any]) -> ExecResult:
        if op not in OPS:
            raise _Denied("unknown_operation", str(op))
        if role not in ROLES or op not in ROLE_OPS[role]:
            raise _Denied("role_not_permitted", f"{role}:{op}")
        self._check_identity()
        self._check_args(op, args)
        handler = getattr(self, f"_op_{op}")
        if op in READ_OPS:
            data, basis = handler(role, **args)
            return ExecResult(op=op, role=role, status="ok", code=None, basis=basis, data=data)
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            res: ExecResult = handler(role, **args)
        except BaseException:
            self._conn.execute("ROLLBACK")
            raise
        if res.changes and self._is_sqlite:
            bad = self._conn.execute("PRAGMA foreign_key_check").fetchall()
            if bad:
                self._conn.execute("ROLLBACK")
                raise RuntimeError(f"foreign key violation: {bad[:3]}")
        self._conn.execute("COMMIT")
        return res

    def _check_identity(self) -> None:
        s = self._session
        row = self._conn.fetchone(
            "SELECT customer_id FROM tickets WHERE id = :t", {"t": s.ticket_id}
        )
        exists = self._conn.fetchone("SELECT 1 FROM customers WHERE id = :c", {"c": s.customer_id})
        if exists is None or row is None or row[0] != s.customer_id:
            raise _Denied("invalid_session")

    @staticmethod
    def _check_args(op: str, args: dict[str, Any]) -> None:
        sig = _SIGNATURES[op]
        names = {n for n, _, _ in sig}
        extra = set(args) - names
        if extra:
            # e.g. an attempt to pass customer_id and substitute the session identity
            raise _Denied("invalid_argument", f"unexpected {sorted(extra)}")
        for name, typ, required in sig:
            if name not in args:
                if required:
                    raise _Denied("invalid_argument", f"missing {name}")
                continue
            v = args[name]
            if isinstance(v, bool) or not isinstance(v, typ):
                raise _Denied("invalid_argument", f"{name} must be {typ.__name__}")

    def _ticket(self) -> tuple[str, str | None]:
        status, order_id = self._conn.fetchone(
            "SELECT status, order_id FROM tickets WHERE id = :t", {"t": self._session.ticket_id}
        )
        return status, order_id

    def _ledger(self, key: str, kind: str, detail: dict[str, Any] | None = None) -> None:
        if detail is not None:
            self._conn.execute(
                "INSERT INTO ops_ledger(op_key, ticket_id, kind, created_at, detail_json) "
                "VALUES (:k, :t, :kind, :ts, :d)",
                {
                    "k": key,
                    "t": self._session.ticket_id,
                    "kind": kind,
                    "ts": self._now(),
                    "d": json.dumps(detail, sort_keys=True),
                },
            )
        else:
            self._conn.execute(
                "INSERT INTO ops_ledger(op_key, ticket_id, kind, created_at) "
                "VALUES (:k, :t, :kind, :ts)",
                {"k": key, "t": self._session.ticket_id, "kind": kind, "ts": self._now()},
            )

    def _final_key(self) -> str:
        return f"final:{self._session.ticket_id}"

    def _finalized(self) -> bool:
        return (
            self._conn.fetchone(
                "SELECT 1 FROM ops_ledger WHERE op_key = :k", {"k": self._final_key()}
            )
            is not None
        )

    def _require_open(self) -> None:
        status, _ = self._ticket()
        if status != "open" or self._finalized():
            raise _Denied("ticket_not_open")

    def _set_ticket_status(self, status: str) -> None:
        self._conn.execute(
            "UPDATE tickets SET status = :s, closed_at = :ts WHERE id = :t",
            {"s": status, "ts": self._now(), "t": self._session.ticket_id},
        )

    # ------------------------------------------------------------------ reads

    def _op_read_order(self, role: str, order_id: str) -> tuple[dict, str]:
        o = self._conn.fetchone(
            "SELECT id, placed_at, delivered_at, status, total_cents, note, note_provenance "
            "FROM orders WHERE id = :o AND customer_id = :c",
            {"o": order_id, "c": self._session.customer_id},
        )
        if o is None:
            # the same answer for "no order" and "someone else's order": no existence oracle
            raise _Denied("not_found_or_not_owner", "order")
        items = [
            {
                "order_item_id": r[0],
                "sku": r[1],
                "title": r[2],
                "category": r[3],
                "price_cents": r[4],
                "qty": r[5],
                "final_sale": bool(r[6]),
                "refund_requested": bool(r[7]),
            }
            for r in self._conn.execute(
                "SELECT i.id, i.sku, i.title, i.category, i.price_cents, i.qty, "
                "i.final_sale, r.id IS NOT NULL FROM order_items i LEFT JOIN refund_requests "
                "r ON r.order_item_id = i.id WHERE i.order_id = :o ORDER BY i.id",
                {"o": o[0]},
            )
        ]
        # Purchase/refund history of the customer: all session-customer orders with a refund
        # flag per item — the agent checks "the customer really bought it" and repeat refunds
        # without a sixth tool. Own data only (R6), no roles and no PII.
        history: dict[str, dict[str, Any]] = {}
        for r in self._conn.execute(
            "SELECT o.id, o.status, o.delivered_at, o.total_cents, i.id, i.sku, "
            "i.price_cents, i.qty, i.final_sale, r.id IS NOT NULL "
            "FROM orders o JOIN order_items i ON i.order_id = o.id "
            "LEFT JOIN refund_requests r ON r.order_item_id = i.id "
            "WHERE o.customer_id = :c ORDER BY o.id, i.id",
            {"c": self._session.customer_id},
        ):
            entry = history.setdefault(
                r[0],
                {
                    "order_id": r[0],
                    "status": r[1],
                    "delivered_at": r[2],
                    "total_cents": r[3],
                    "items": [],
                },
            )
            entry["items"].append(
                {
                    "order_item_id": r[4],
                    "sku": r[5],
                    "price_cents": r[6],
                    "qty": r[7],
                    "final_sale": bool(r[8]),
                    "refund_requested": bool(r[9]),
                }
            )
        context = [{"provenance": o[6], "text": o[5]}] if o[5] else []
        return (
            {
                "order": {
                    "order_id": o[0],
                    "placed_at": o[1],
                    "delivered_at": o[2],
                    "status": o[3],
                    "total_cents": o[4],
                    "note_provenance": o[6],
                },
                "items": items,
                "purchase_history": [history[k] for k in sorted(history)],
                "context": context,
            },
            "R6 ownership: order belongs to session customer",
        )

    def _op_read_ticket(self, role: str, ticket_id: str | None = None) -> tuple[dict, str]:
        s = self._session
        if ticket_id is not None and ticket_id != s.ticket_id:
            raise _Denied("not_found_or_not_owner", "ticket")
        t = self._conn.fetchone(
            "SELECT id, order_id, status, opened_at, clarifications FROM tickets WHERE id = :t",
            {"t": s.ticket_id},
        )
        msgs = [
            {"seq": r[0], "author": r[1], "provenance": r[2], "text": r[3]}
            for r in self._conn.execute(
                "SELECT seq, author, provenance, body FROM ticket_messages "
                "WHERE ticket_id = :t ORDER BY seq",
                {"t": s.ticket_id},
            )
        ]
        return (
            {
                "ticket": {
                    "ticket_id": t[0],
                    "order_id": t[1],
                    "status": t[2],
                    "opened_at": t[3],
                    "clarifications": t[4],
                },
                "messages": msgs,
            },
            "session ticket",
        )

    def _op_read_policy(self, role: str) -> tuple[dict, str]:
        rules = [
            {
                "rule_id": r[0],
                "version": r[1],
                "text": r[2],
                "params": json.loads(r[3]),
                "provenance": "trusted_policy",
            }
            for r in self._conn.execute(
                "SELECT rule_id, version, text, params_json FROM refund_policy ORDER BY rule_id"
            )
        ]
        return {"rules": rules}, "trusted policy source (read-only)"

    # ------------------------------------------------------------------ mutations

    def _op_request_info(
        self, role: str, question_code: str, question_text: str | None = None
    ) -> ExecResult:
        if question_code not in QUESTION_CODES:
            raise _Denied("invalid_argument", "question_code")
        if question_text is not None:
            if not isinstance(question_text, str):  # the type is checked in _check_args anyway
                raise _Denied("invalid_argument", "question_text")
            question_text = question_text.strip()
            if not question_text or len(question_text) > _MAX_QUESTION_TEXT_CHARS:
                raise _Denied(
                    "invalid_argument", f"question_text: 1..{_MAX_QUESTION_TEXT_CHARS} chars"
                )
        self._require_open()
        tid = self._session.ticket_id
        n = (
            self._conn.fetchone("SELECT clarifications FROM tickets WHERE id = :t", {"t": tid})[0]
            + 1
        )
        if question_text is not None:
            self._conn.execute(
                "INSERT INTO info_requests(ticket_id, question_code, question_text, created_at) "
                "VALUES (:t, :q, :qt, :ts)",
                {"t": tid, "q": question_code, "qt": question_text, "ts": self._now()},
            )
        else:
            self._conn.execute(
                "INSERT INTO info_requests(ticket_id, question_code, created_at) "
                "VALUES (:t, :q, :ts)",
                {"t": tid, "q": question_code, "ts": self._now()},
            )
        self._conn.execute(
            "UPDATE tickets SET clarifications = :n WHERE id = :t", {"n": n, "t": tid}
        )
        self._ledger(
            f"info:{tid}:{n}",
            "info_request",
            detail={"question_code": question_code, "question_text": question_text},
        )
        # the R7 limit is not applied here: it is a process rule (agent / g_proc), not a right
        return ExecResult(
            op="request_info",
            role=role,
            status="ok",
            code=None,
            basis=f"ticket open; clarification #{n}",
            data={"question_code": question_code, "clarifications": n},
            changes={"info_requests": 1, "tickets": 1, "ops_ledger": 1},
        )

    def _replay(self, op: str, role: str, match: dict[str, Any]) -> ExecResult | None:
        """The same finalizing call on an already finalized ticket — idempotent replay."""
        tid = self._session.ticket_id
        if op == "create_refund":
            r = self._conn.fetchone(
                "SELECT order_item_id, amount_cents, reason_code, id FROM refund_requests "
                "WHERE ticket_id = :t AND created_by = 'executor'",
                {"t": tid},
            )
            same = r is not None and (r[0], r[1], r[2]) == (
                match["order_item_id"],
                match["amount_cents"],
                match["reason_code"],
            )
            data = {"refund_request_id": r[3]} if same else {}
        elif op == "refuse":
            r = self._conn.fetchone(
                "SELECT reason_code FROM refusals WHERE ticket_id = :t", {"t": tid}
            )
            same = r is not None and r[0] == match["reason_code"]
            data = {"reason_code": match["reason_code"]}
        else:
            r = self._conn.fetchone(
                "SELECT reason_code FROM manual_reviews WHERE ticket_id = :t", {"t": tid}
            )
            same = r is not None and r[0] == match["reason_code"]
            data = {"reason_code": match["reason_code"]}
        if not same:
            return None
        return ExecResult(
            op=op,
            role=role,
            status="ok",
            code=None,
            basis="idempotent replay of the same finalizing action",
            data=data,
            replayed=True,
        )

    def _finalize(self, op: str, role: str, match: dict[str, Any]) -> ExecResult | None:
        if self._finalized() or self._ticket()[0] != "open":
            replay = self._replay(op, role, match)
            if replay is not None:
                return replay
            raise _Denied("ticket_not_open")
        return None

    def _op_create_refund(
        self, role: str, order_item_id: int, amount_cents: int, reason_code: str
    ) -> ExecResult:
        if reason_code not in REASON_CODES:
            raise _Denied("invalid_argument", "reason_code")
        s = self._session
        item = self._conn.fetchone(
            "SELECT i.price_cents, i.qty, i.order_id FROM order_items i JOIN orders o "
            "ON o.id = i.order_id WHERE i.id = :i AND o.customer_id = :c",
            {"i": order_item_id, "c": s.customer_id},
        )
        if item is None:
            raise _Denied("not_found_or_not_owner", "order item")
        if amount_cents <= 0:
            raise _Denied("invalid_argument", "amount_cents must be positive")
        args = {
            "order_item_id": order_item_id,
            "amount_cents": amount_cents,
            "reason_code": reason_code,
        }
        replay = self._finalize("create_refund", role, args)
        if replay is not None:
            return replay
        if self._conn.fetchone(
            "SELECT 1 FROM refund_requests WHERE order_item_id = :i", {"i": order_item_id}
        ):
            raise _Denied("duplicate_request")
        limit = item[0] * item[1]
        if amount_cents > limit:
            raise _Denied("amount_exceeds_price", f"{amount_cents} > {limit}")
        rules_basis = ""
        # request status: 'approved' when the R5 threshold is covered by a trusted operator
        # approval (boundary-2/2r); otherwise 'created'
        refund_status = "created"
        if self.boundary == BOUNDARY_V2_VERSION:
            basis, refund_status = self._check_rules_v2(
                order_item_id, item[2], limit, amount_cents, reason_code
            )
            rules_basis = "; " + basis
        elif self.boundary == BOUNDARY_V2R_VERSION:
            try:
                basis, refund_status = self._check_rules_v2(
                    order_item_id, item[2], limit, amount_cents, reason_code
                )
                rules_basis = "; " + basis
            except _Denied as d:
                if d.route is None:
                    raise  # a hard denial stays a denial
                return self._route_review(role, d)
        try:
            cur = self._conn.execute(
                "INSERT INTO refund_requests(ticket_id, order_item_id, customer_id, "
                "amount_cents, reason_code, status, created_by, created_at) "
                "VALUES (:t, :i, :c, :a, :r, :st, 'executor', :ts)",
                {
                    "t": s.ticket_id,
                    "i": order_item_id,
                    "c": s.customer_id,
                    "a": amount_cents,
                    "r": reason_code,
                    "st": refund_status,
                    "ts": self._now(),
                },
            )
            rr = int(cur.lastrowid)
            self._insert_payout(rr, order_item_id, amount_cents)
            self._ledger(
                f"refund:item:{order_item_id}",
                "refund",
                detail={
                    "order_item_id": order_item_id,
                    "amount_cents": amount_cents,
                    "reason_code": reason_code,
                    "status": refund_status,
                },
            )
        except _IntegrityError:
            raise _Denied("duplicate_request", "unique constraint") from None
        self._ledger(self._final_key(), "refund")
        self._set_ticket_status("resolved")
        return ExecResult(
            op="create_refund",
            role=role,
            status="ok",
            code=None,
            basis=f"R6 owner; R4 first request for item; R3 amount {amount_cents} <= {limit}; "
            "ticket open" + rules_basis,
            data={
                "refund_request_id": rr,
                "order_id": item[2],
                "order_item_id": order_item_id,
                "amount_cents": amount_cents,
            },
            changes={"refund_requests": 1, "payouts": 1, "ops_ledger": 2, "tickets": 1},
        )

    def _insert_payout(self, refund_request_id: int, order_item_id: int, amount: int) -> None:
        """Outbox row for the refund request (in the prototype written by a SQLite trigger;
        in the lab written here, same semantics)."""
        self._conn.execute(
            "INSERT INTO payouts(refund_request_id, idempotency_key, charge_id, amount_cents, "
            "state) SELECT :rr, :key, 'ch_syn_' || (SELECT order_id FROM order_items WHERE "
            "id = :i), :a, 'requested'",
            {
                "rr": refund_request_id,
                "key": f"rr-{refund_request_id}",
                "i": order_item_id,
                "a": amount,
            },
        )

    # ------------------------------------------------------------------ boundary-2: R1, R2, R5

    def _policy_params(self) -> dict[str, dict[str, Any]]:
        return {
            r[0]: json.loads(r[1])
            for r in self._conn.execute("SELECT rule_id, params_json FROM refund_policy")
        }

    def _check_rules_v2(
        self, item_id: int, order_id: str, full_cents: int, amount_cents: int, reason_code: str
    ) -> tuple[str, str]:
        """R1, R2, R5 inside the already open transaction (no TOCTOU): the state the decision
        is made on is the state written to. Thresholds come only from the trusted
        `refund_policy`. Returns (basis, request status); the status is 'approved' when the
        R5 threshold is covered by a trusted operator approval. A violation raises `_Denied`."""
        try:
            prm = self._policy_params()
            window = int(prm["R1"]["window_days"])
            exception_reason = str(prm["R2"]["exception_reason"])
            threshold = int(prm["R5"]["manual_threshold_cents"])
            repeat_days = int(prm["R5"]["repeat_window_days"])
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError(f"refund_policy params unreadable: {exc}") from None
        status, delivered_at = self._conn.fetchone(
            "SELECT status, delivered_at FROM orders WHERE id = :o", {"o": order_id}
        )
        final_sale = self._conn.fetchone(
            "SELECT final_sale FROM order_items WHERE id = :i", {"i": item_id}
        )[0]
        opened_at = self._conn.fetchone(
            "SELECT opened_at FROM tickets WHERE id = :t", {"t": self._session.ticket_id}
        )[0]
        # R1: delivered; window from delivery to ticket opening, inclusive bound
        if status != "delivered" or not delivered_at:
            raise _Denied("not_delivered", f"order {order_id} status {status}")
        days = (parse_ts(opened_at) - parse_ts(delivered_at)).days
        if days > window:
            raise _Denied("outside_window", f"{days} days > {window}")
        basis = [f"R1 delivered, {days} <= {window} days"]
        # R2: final sale — only the exception reason AND trusted defect confirmation
        if final_sale:
            evidence = (
                self._conn.fetchone(
                    "SELECT 1 FROM defect_evidence WHERE order_item_id = :i AND status = 'verified'",
                    {"i": item_id},
                )
                is not None
            )
            if reason_code != exception_reason or not evidence:
                raise _Denied(
                    "final_sale_not_refundable",
                    f"reason {reason_code}, verified evidence {evidence}",
                    route="customer_request" if reason_code == exception_reason else None,
                )
            basis.append("R2 final sale with verified defect_evidence")
        # R5: item cost above the threshold or a repeat on the order in the window → approval
        refund_status = "created"
        cutoff = fmt_ts(parse_ts(self._now()) - timedelta(days=repeat_days))
        repeat = self._conn.fetchone(
            "SELECT COUNT(*) FROM refund_requests r JOIN order_items i ON i.id = r.order_item_id "
            "WHERE i.order_id = :o AND r.order_item_id <> :i AND r.created_at >= :c",
            {"o": order_id, "i": item_id, "c": cutoff},
        )[0]
        high = full_cents > threshold
        if high or repeat:
            appr = self._conn.fetchone(
                "SELECT max(max_amount_cents) FROM refund_approvals WHERE order_item_id = :i "
                "AND approved_by = 'operator'",
                {"i": item_id},
            )[0]
            why = ("high value " if high else "") + (f"repeat x{repeat}" if repeat else "")
            if appr is None or amount_cents > appr:
                raise _Denied(
                    "requires_manual_review",
                    f"{why.strip()}; approval {appr} for amount {amount_cents}",
                    route="high_value" if high else "repeat_refund",
                )
            refund_status = "approved"
            basis.append(f"R5 {why.strip()} approved by operator up to {appr}")
        else:
            basis.append(f"R5 value {full_cents} <= {threshold}, no repeat in {repeat_days} days")
        return "; ".join(basis), refund_status

    def _route_review(self, role: str, d: _Denied) -> ExecResult:
        """boundary-2r: route-rule denial → server-side manual review in the same transaction
        (called inside `BEGIN IMMEDIATE` from `_op_create_refund`; the ticket is already
        verified as open). The decision is made by the server (the `server` role), not the
        agent."""
        reason = d.route
        assert reason in MANUAL_REVIEW_REASONS, reason
        now = self._now()
        self._conn.execute(
            "INSERT INTO manual_reviews(ticket_id, reason_code, enqueued_at) VALUES (:t, :r, :ts)",
            {"t": self._session.ticket_id, "r": reason, "ts": now},
        )
        self._ledger(
            self._final_key(),
            "manual_review",
            detail={"routed_reason": reason, "routed_by": SERVER_ROUTING_ROLE},
        )
        self._set_ticket_status("escalated")
        return ExecResult(
            op="create_refund",
            role=role,
            status="ok",
            code=None,
            basis=f"server routing by role {SERVER_ROUTING_ROLE}: {d.code} "
            f"({d.detail}) -> manual review {reason}; no refund request",
            data={
                "routed": "manual_review",
                "reason_code": reason,
                "enqueued_at": now,
                "routed_by": SERVER_ROUTING_ROLE,
            },
            changes={"manual_reviews": 1, "ops_ledger": 1, "tickets": 1},
            routed=reason,
        )

    def _op_refuse(self, role: str, reason_code: str) -> ExecResult:
        if reason_code not in REFUSAL_CODES:
            raise _Denied("invalid_argument", "reason_code")
        if reason_code not in REFUSAL_CODES_BY_ROLE[role]:
            raise _Denied("code_not_permitted", f"{role}:{reason_code}")
        replay = self._finalize("refuse", role, {"reason_code": reason_code})
        if replay is not None:
            return replay
        self._conn.execute(
            "INSERT INTO refusals(ticket_id, reason_code, created_at) VALUES (:t, :r, :ts)",
            {"t": self._session.ticket_id, "r": reason_code, "ts": self._now()},
        )
        self._ledger(self._final_key(), "refusal", detail={"reason_code": reason_code})
        self._set_ticket_status("refused")
        return ExecResult(
            op="refuse",
            role=role,
            status="ok",
            code=None,
            basis=f"ticket open; refusal code {reason_code} permitted for {role}",
            data={"reason_code": reason_code},
            changes={"refusals": 1, "ops_ledger": 1, "tickets": 1},
        )

    def _op_assign_manual_review(self, role: str, reason_code: str) -> ExecResult:
        if reason_code not in MANUAL_REVIEW_REASONS:
            raise _Denied("invalid_argument", "reason_code")
        if reason_code not in REVIEW_REASONS_BY_ROLE[role]:
            raise _Denied("code_not_permitted", f"{role}:{reason_code}")
        replay = self._finalize("assign_manual_review", role, {"reason_code": reason_code})
        if replay is not None:
            return replay
        now = self._now()
        self._conn.execute(
            "INSERT INTO manual_reviews(ticket_id, reason_code, enqueued_at) VALUES (:t, :r, :ts)",
            {"t": self._session.ticket_id, "r": reason_code, "ts": now},
        )
        self._ledger(self._final_key(), "manual_review", detail={"reason_code": reason_code})
        self._set_ticket_status("escalated")
        return ExecResult(
            op="assign_manual_review",
            role=role,
            status="ok",
            code=None,
            basis=f"ticket open; one manual review per ticket; reason {reason_code}",
            data={"reason_code": reason_code, "enqueued_at": now},
            changes={"manual_reviews": 1, "ops_ledger": 1, "tickets": 1},
        )

    def _op_resolve_review(self, role: str, decision: str) -> ExecResult:
        """Manual review outcome: the `operator` role closes the escalated ticket with
        'approved'/'rejected'. Session identity is checked like for all operations; the right
        is by role, not ownership: the operator session is created by the orchestrator with
        the ticket owner's customer_id."""
        if decision not in REVIEW_DECISIONS:
            raise _Denied("invalid_argument", "decision")
        status, _ = self._ticket()
        review = self._conn.fetchone(
            "SELECT reason_code FROM manual_reviews WHERE ticket_id = :t",
            {"t": self._session.ticket_id},
        )
        if review is None:
            raise _Denied("invalid_argument", "no manual review on this ticket")
        if status != "escalated":
            raise _Denied("ticket_not_open")
        now = self._now()
        self._conn.execute(
            "UPDATE manual_reviews SET decided_at = :ts, decision = :d, decided_by = :by "
            "WHERE ticket_id = :t",
            {"ts": now, "d": decision, "by": REVIEW_DECIDED_BY, "t": self._session.ticket_id},
        )
        # the ticket is closed by the operator outcome: approved -> resolved, rejected -> refused
        self._set_ticket_status("resolved" if decision == "approved" else "refused")
        self._ledger(
            f"review:{self._session.ticket_id}",
            "manual_review",
            detail={
                "decision": decision,
                "decided_by": REVIEW_DECIDED_BY,
                "reason_code": review[0],
            },
        )
        return ExecResult(
            op="resolve_review",
            role=role,
            status="ok",
            code=None,
            basis=f"manual review {review[0]} {decision} by {REVIEW_DECIDED_BY}; ticket closed",
            data={"decision": decision, "reason_code": review[0], "decided_at": now},
            changes={"manual_reviews": 1, "tickets": 1, "ops_ledger": 1},
        )

    def _op_record_message(self, role: str, author: str, body: str) -> ExecResult:
        if author not in ("customer", "agent"):
            raise _Denied("invalid_argument", "author")
        if not body or len(body) > MAX_BODY_CHARS:
            raise _Denied("invalid_argument", "body length")
        tid = self._session.ticket_id
        seq = self._conn.fetchone(
            "SELECT coalesce(max(seq), -1) + 1 FROM ticket_messages WHERE ticket_id = :t",
            {"t": tid},
        )[0]
        # channel replies are untrusted context with the `channel` provenance
        self._conn.execute(
            "INSERT INTO ticket_messages(ticket_id, seq, author, provenance, body, created_at) "
            "VALUES (:t, :s, :a, 'channel', :b, :ts)",
            {"t": tid, "s": seq, "a": author, "b": body, "ts": self._now()},
        )
        return ExecResult(
            op="record_message",
            role=role,
            status="ok",
            code=None,
            basis="channel transport appends dialog turn",
            data={"seq": seq},
            changes={"ticket_messages": 1},
        )


assert set(FINALIZING_OPS) <= set(_SIGNATURES) and set(OPS) == set(_SIGNATURES)

_WRITE_ACTIONS = frozenset({sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE})


# Executor-connection hardening (defence in depth, SQLite authorizer). Tables the executor
# connection never changes (thresholds, orders, customers, model time) and decision history —
# INSERT only.
READ_ONLY_TABLES = frozenset({"refund_policy", "orders", "order_items", "customers", "meta"})
APPEND_ONLY_TABLES = frozenset(
    {
        "refund_requests",
        "manual_reviews",
        "refusals",
        "ops_ledger",
        "info_requests",
        "ticket_messages",
        "payouts",
        "operator_decisions",
    }
)
# UPDATE columns of `manual_reviews` allowed on the executor connection (resolve_review).
REVIEW_DECIDED_COLUMNS = frozenset({"decided_at", "decision", "decided_by"})
TICKET_UPDATABLE_COLUMNS = frozenset({"status", "clarifications", "closed_at"})
_DDL_ACTIONS = frozenset(
    getattr(sqlite3, n)
    for n in (
        "SQLITE_CREATE_INDEX",
        "SQLITE_CREATE_TABLE",
        "SQLITE_CREATE_TEMP_INDEX",
        "SQLITE_CREATE_TEMP_TABLE",
        "SQLITE_CREATE_TEMP_TRIGGER",
        "SQLITE_CREATE_TEMP_VIEW",
        "SQLITE_CREATE_TRIGGER",
        "SQLITE_CREATE_VIEW",
        "SQLITE_DROP_INDEX",
        "SQLITE_DROP_TABLE",
        "SQLITE_DROP_TEMP_INDEX",
        "SQLITE_DROP_TEMP_TABLE",
        "SQLITE_DROP_TEMP_TRIGGER",
        "SQLITE_DROP_TEMP_VIEW",
        "SQLITE_DROP_TRIGGER",
        "SQLITE_DROP_VIEW",
        "SQLITE_ALTER_TABLE",
    )
    if hasattr(sqlite3, n)
)


def _deny_trusted_writes(action: int, arg1: Any, arg2: Any, dbname: Any, source: Any) -> int:
    """Authorizer of the boundary-2/2r executor connection: trusted tables are read-only,
    orders/policy/meta read-only, decision history INSERT-only, no DDL."""
    if action in _WRITE_ACTIONS and arg1 in TRUSTED_TABLES:
        return sqlite3.SQLITE_DENY
    if action in (sqlite3.SQLITE_DROP_TABLE, sqlite3.SQLITE_ALTER_TABLE) and (
        arg1 in TRUSTED_TABLES or arg2 in TRUSTED_TABLES
    ):
        return sqlite3.SQLITE_DENY
    if action in _WRITE_ACTIONS and arg1 in READ_ONLY_TABLES:
        return sqlite3.SQLITE_DENY
    if (
        action == sqlite3.SQLITE_UPDATE
        and arg1 == "manual_reviews"
        and arg2 in REVIEW_DECIDED_COLUMNS
    ):
        return sqlite3.SQLITE_OK
    if action in (sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE) and arg1 in APPEND_ONLY_TABLES:
        return sqlite3.SQLITE_DENY
    if arg1 == "tickets" and (
        action in (sqlite3.SQLITE_INSERT, sqlite3.SQLITE_DELETE)
        or (action == sqlite3.SQLITE_UPDATE and arg2 not in TICKET_UPDATABLE_COLUMNS)
    ):
        return sqlite3.SQLITE_DENY
    if action in _DDL_ACTIONS:
        return sqlite3.SQLITE_DENY
    if action in (sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH):
        return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_PRAGMA and not _read_pragma(arg1, arg2):
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


READ_PRAGMAS = frozenset({"foreign_key_check", "integrity_check", "user_version", "table_info"})
READ_PRAGMAS_WITH_ARG = frozenset({"table_info"})


def _read_pragma(name: Any, arg: Any) -> bool:
    name = str(name or "").lower()
    return name in READ_PRAGMAS and (arg is None or name in READ_PRAGMAS_WITH_ARG)


def _install_append_only_triggers(conn: ShopConn) -> None:
    """TEMP triggers BEFORE UPDATE / BEFORE DELETE with RAISE(ABORT) on every history table.

    The SQLite authorizer sees `INSERT OR REPLACE` as SQLITE_INSERT and is not told about the
    implicit deletion of the conflicting row. A BEFORE DELETE trigger fires on such a deletion
    only with `recursive_triggers=ON`. Triggers live in the connection's temp schema.
    """
    conn.execute("PRAGMA recursive_triggers = ON")
    for t in sorted(APPEND_ONLY_TABLES):
        for ev, tag in (("UPDATE", "upd"), ("DELETE", "del")):
            if t == "manual_reviews" and ev == "UPDATE":
                conn.execute(
                    "CREATE TEMP TRIGGER IF NOT EXISTS lab_append_only_upd_manual_reviews "
                    "BEFORE UPDATE ON main.manual_reviews "
                    "WHEN NEW.id IS NOT OLD.id OR NEW.ticket_id IS NOT OLD.ticket_id "
                    "OR NEW.reason_code IS NOT OLD.reason_code "
                    "OR NEW.enqueued_at IS NOT OLD.enqueued_at "
                    "BEGIN SELECT RAISE(ABORT, 'append-only: manual_reviews'); END"
                )
                continue
            conn.execute(
                f"CREATE TEMP TRIGGER IF NOT EXISTS lab_append_only_{tag}_{t} "
                f"BEFORE {ev} ON main.{t} BEGIN "
                f"SELECT RAISE(ABORT, 'append-only: {t}'); END"
            )
