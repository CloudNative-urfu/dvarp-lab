"""Unified event and cost journal (FR-1.17) with per-side accounting, on lab.chain.

- `EventLog` — the journal of one run. Events live in memory and, if a `sink` is given,
  are appended line by line to a lab.chain JSONL file (hash chain: seq/prev/hash).
- Components write only through a `ComponentWriter` obtained from `EventLog.writer(name)`.
  The recording side is taken from the `schema.COMPONENT_SIDES` registry.
- Episodes are opened and closed by the orchestrator (`start_episode`/`end_episode`); an
  event with an unopened or closed episode is rejected, so costs never leak between episodes.
- Each record is linked to the previous one by a hash: editing, deletion or reordering of a
  stored line is detected by `verify_chain`.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lab.chain import GENESIS, Chain, line_hash
from services.shop.repro import HashingError, canonical_json, strip_volatile
from services.shop.repro import trajectory_fingerprint as _trajectory_fingerprint

from .schema import (
    KINDS,
    RESEARCH_ONLY_KINDS,
    SCHEMA,
    TRAFFIC_CLASSES,
    EventLogError,
    component_class,
    side_of,
    validate_cost,
    validate_payload,
)

# Fields that go through the hash chain; not part of the payload.
CHAIN_KEYS = ("prev", "h")
# Volatile measurements excluded from the trajectory (repro VOLATILE_KEYS + gpu_ms).
TRAJECTORY_VOLATILE = frozenset(
    {
        "ts",
        "time",
        "created_at",
        "wall_ms",
        "wall_s",
        "latency_ms",
        "cpu_ms",
        "cpu_s",
        "duration_ms",
        "gpu_ms",
    }
)


class ComponentWriter:
    """Writer of one component: write-only, no journal read access."""

    __slots__ = ("_component", "_emit", "_side")

    def __init__(self, component: str, side: str, emit: Callable[..., dict]):
        object.__setattr__(self, "_component", component)
        object.__setattr__(self, "_side", side)
        object.__setattr__(self, "_emit", emit)

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError("ComponentWriter is immutable")

    @property
    def component(self) -> str:
        return self._component

    @property
    def side(self) -> str:
        return self._side

    def emit(
        self,
        kind: str,
        data: Mapping[str, Any] | None = None,
        *,
        episode_id: str | None = None,
        cost: Mapping[str, Any] | None = None,
        t_sim: float | None = None,
    ) -> int:
        """Record an event; returns its ordinal number `seq`."""
        return self._emit(self._component, kind, data, episode_id, cost, t_sim)["seq"]

    @contextmanager
    def measure(
        self,
        kind: str,
        data: Mapping[str, Any] | None = None,
        *,
        episode_id: str | None = None,
        t_sim: float | None = None,
        error_kind: str | None = None,
    ) -> Iterator[dict]:
        """Wall-clock latency and process CPU measurement around a block.

        The block appends tokens/requests to `m["cost"]` and content to `m["data"]`. On an
        exception the costs are still recorded as an `error_kind` event (if given): a failed
        detector call costs money too.
        """
        m: dict[str, Any] = {"data": dict(data or {}), "cost": {}}
        w0, c0 = time.perf_counter(), time.process_time()
        try:
            yield m
        except BaseException as exc:
            if error_kind is not None:
                cost = dict(
                    m["cost"],
                    latency_ms=(time.perf_counter() - w0) * 1000.0,
                    cpu_ms=(time.process_time() - c0) * 1000.0,
                )
                self.emit(
                    error_kind,
                    dict(m["data"], error=type(exc).__name__),
                    episode_id=episode_id,
                    cost=cost,
                    t_sim=t_sim,
                )
            raise
        cost = dict(
            m["cost"],
            latency_ms=(time.perf_counter() - w0) * 1000.0,
            cpu_ms=(time.process_time() - c0) * 1000.0,
        )
        self.emit(kind, m["data"], episode_id=episode_id, cost=cost, t_sim=t_sim)

    def __repr__(self) -> str:
        return f"ComponentWriter({self.component!r}, side={self.side!r})"


@dataclass
class _Episode:
    traffic: str
    open: bool = True


class EventLog:
    """Journal of one run."""

    def __init__(
        self,
        run_id: str,
        *,
        research_mode: bool = False,
        sink: str | Path | None = None,
        meta: Mapping[str, Any] | None = None,
        clock: Callable[[], float] = time.perf_counter,
    ):
        if not isinstance(run_id, str) or not run_id:
            raise EventLogError("run_id is required")
        self.run_id = run_id
        self.research_mode = bool(research_mode)
        self._events: list[dict] = []
        self._episodes: dict[str, _Episode] = {}
        self._prev = GENESIS
        self._clock = clock
        self._t0 = clock()
        self._sink = None
        if sink is not None:
            p = Path(sink)
            if p.exists() and p.stat().st_size > 0:
                raise EventLogError(f"journal file already exists: {p}")
            p.parent.mkdir(parents=True, exist_ok=True)
            self._sink = Chain(p)
        self._runner = self.writer("runner")
        self._runner.emit(
            "run_start",
            {"schema": SCHEMA, "research_mode": self.research_mode, "meta": dict(meta or {})},
        )

    # --- recording -------------------------------------------------------------------------

    def writer(self, component: str) -> ComponentWriter:
        return ComponentWriter(component, side_of(component), self._append)

    def _append(
        self,
        component: str,
        kind: str,
        data: Mapping[str, Any] | None,
        episode_id: str | None,
        cost: Mapping[str, Any] | None,
        t_sim: float | None,
    ) -> dict:
        cls = component_class(component)
        if kind not in KINDS[cls]:
            raise EventLogError(f"{component}: event kind {kind!r} not in {sorted(KINDS[cls])}")
        if kind in RESEARCH_ONLY_KINDS and not self.research_mode:
            raise EventLogError(f"{component}.{kind}: only allowed in a research-mode journal")
        data = dict(data or {})
        validate_payload(cls, kind, data)
        cost = validate_cost(cost)
        traffic = None
        if episode_id is not None:
            ep = self._episodes.get(episode_id)
            if ep is None:
                raise EventLogError(f"episode {episode_id!r} is not open")
            if not ep.open:
                raise EventLogError(f"episode {episode_id!r} is already closed")
            traffic = ep.traffic
        if t_sim is not None and (isinstance(t_sim, bool) or not isinstance(t_sim, (int, float))):
            raise EventLogError("t_sim must be a number (model minutes)")
        body = {
            "run_id": self.run_id,
            "episode_id": episode_id,
            "traffic": traffic,
            "component": component,
            "side": side_of(component),
            "kind": kind,
            "t_sim": t_sim,
            "data": data,
            "cost": cost,
            "wall_ms": (self._clock() - self._t0) * 1000.0,
        }
        try:
            canonical_json(body)  # early serializability check (NaN, sets, etc.)
        except HashingError as exc:
            raise EventLogError(f"{component}.{kind}: {exc}") from exc
        seq = len(self._events) + 1
        digest = line_hash(seq, self._prev, body)
        event = dict(body, seq=seq, prev=self._prev, h=digest)
        self._prev = digest
        self._events.append(event)
        if self._sink is not None:
            self._sink.append(body)
        return event

    def start_episode(self, episode_id: str, traffic: str, **data: Any) -> None:
        if traffic not in TRAFFIC_CLASSES:
            raise EventLogError(f"traffic class {traffic!r} not in {TRAFFIC_CLASSES}")
        if not isinstance(episode_id, str) or not episode_id:
            raise EventLogError("episode_id is required")
        if episode_id in self._episodes:
            raise EventLogError(f"episode {episode_id!r} was already opened in this run")
        self._episodes[episode_id] = _Episode(traffic)
        self._runner.emit("episode_start", dict(data, traffic=traffic), episode_id=episode_id)

    def end_episode(self, episode_id: str, **data: Any) -> None:
        self._runner.emit("episode_end", data, episode_id=episode_id)
        self._episodes[episode_id].open = False

    def close(self, **data: Any) -> None:
        open_eps = sorted(e for e, ep in self._episodes.items() if ep.open)
        if open_eps:
            raise EventLogError(f"open episodes: {open_eps}")
        self._runner.emit("run_end", data)

    # --- reading (defended side, evaluator and report only) --------------------------------

    @property
    def events(self) -> list[dict]:
        return [dict(e) for e in self._events]

    def episodes(self) -> dict[str, str]:
        return {e: ep.traffic for e, ep in self._episodes.items()}

    def select(self, **where: Any) -> list[dict]:
        return select(self._events, **where)

    def trajectory(self, episode_id: str) -> list[dict]:
        return trajectory(self._events, episode_id)

    def chain(self) -> Chain | None:
        return self._sink


# --- functions over event lists (including ones loaded from a file) ---------------------


def select(events: Iterable[Mapping[str, Any]], **where: Any) -> list[dict]:
    out = []
    for e in events:
        if all((e.get(k) == v) if not callable(v) else v(e.get(k)) for k, v in where.items()):
            out.append(dict(e))
    return out


def trajectory(events: Iterable[Mapping[str, Any]], episode_id: str) -> list[dict]:
    """Episode trajectory for rerun comparison: no wall-clock, latency, CPU or hash chain.
    `seq` is replaced by the ordinal number inside the episode."""
    steps = []
    for i, e in enumerate(x for x in events if x.get("episode_id") == episode_id):
        step = {k: v for k, v in e.items() if k not in CHAIN_KEYS and k not in ("seq", "run_id")}
        step["step"] = i
        steps.append(strip_volatile(step, TRAJECTORY_VOLATILE))
    return steps


def episode_fingerprint(events: Iterable[Mapping[str, Any]], episode_id: str) -> str:
    return _trajectory_fingerprint(trajectory(events, episode_id))


def verify_chain(events: list[Mapping[str, Any]]) -> list[str]:
    """Empty list if the journal is intact; otherwise a description of the first violations."""
    errors: list[str] = []
    prev = GENESIS
    for i, e in enumerate(events):
        if e.get("seq") != i + 1:
            errors.append(f"line {i}: seq={e.get('seq')!r}, expected {i + 1}")
        if e.get("prev") != prev:
            errors.append(f"line {i}: broken chain (prev mismatch)")
        payload = {k: v for k, v in e.items() if k not in ("seq", "prev", "h")}
        if line_hash(e.get("seq", 0), e.get("prev", ""), payload) != e.get("h"):
            errors.append(f"line {i}: record hash mismatch (record modified)")
        prev = e.get("h", "")
        if len(errors) >= 10:
            break
    if events and not errors:
        first = events[0]
        if first.get("component") != "runner" or first.get("kind") != "run_start":
            errors.append("journal does not start with runner.run_start")
    return errors


@dataclass(frozen=True)
class LoadedLog:
    run_id: str
    research_mode: bool
    events: list[dict]
    complete: bool  # is there a run_end


def load_jsonl(path: str | Path, *, strict: bool = True) -> LoadedLog:
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    events = []
    for line in lines:
        if not line.strip():
            continue
        rec = json.loads(line)
        payload = rec.get("payload", {})
        events.append({**payload, "seq": rec["seq"], "prev": rec["prev"], "h": rec["hash"]})
    errors = verify_chain(events)
    if errors and strict:
        raise EventLogError(f"journal {path} is damaged: {errors[:3]}")
    if not events:
        raise EventLogError(f"journal {path} is empty")
    head = events[0]
    return LoadedLog(
        run_id=head["run_id"],
        research_mode=bool(head["data"].get("research_mode")),
        events=events,
        complete=events[-1].get("kind") == "run_end",
    )
