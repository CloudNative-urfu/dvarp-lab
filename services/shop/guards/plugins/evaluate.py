"""Offline detection measurement of the built-in input/context plugins over the frozen corpus
(no agent, no model): each entry is bound to a synthetic DB, the turns go through the `input`
point and the indirect data (order note, history) through the `context` point. An episode is
"alarmed" if any `flag`/`block` signal fired. Attacks are TP/FN, clean controls FP/TN,
separately by attack mechanism and control type and by dev/holdout split."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from services.shop.corpus import load_corpus
from services.shop.corpus.bind import bind, pick_accounts
from services.shop.db import EpisodeStateManager, connect
from services.shop.guards.contract import (
    DEFAULT_REGISTRY,
    ContextFragment,
    GuardHost,
    GuardInput,
    GuardSet,
    TrustedTask,
)
from services.shop.guards.tools.specs import TOOL_NAMES
from services.shop.journal import EventLog

from . import BUILTIN_IDS  # noqa: F401  (plugin registration)

EVAL_SPEC = [
    {"id": "input-filter", "stages": ["input", "context"]},
    {"id": "context-provenance", "stages": ["input", "context"]},
]


def episode_inputs(ep) -> list[GuardInput]:
    """Guardrail inputs of an episode without an agent: turns -> input, indirect data -> context."""
    t = ep.fixture["tickets"][0]
    task = TrustedTask(
        f"task-{ep.entry_id}",
        "Handle the customer's refund request for this ticket.",
        ep.actor_id,
        ep.ticket_id,
        TOOL_NAMES,
        t.get("order_id"),
    )
    ctx = [
        ContextFragment(h["body"], h["provenance"], f"ticket:{ep.ticket_id}:msg:{i}")
        for i, h in enumerate(t.get("history", []))
    ]
    ctx += [
        ContextFragment(n["note"], "order_data", f"order:{n['order_id']}:note:0")
        for n in ep.fixture.get("order_notes", [])
    ]
    out = [GuardInput("input", turn, task, turn=i) for i, turn in enumerate(ep.turns)]
    if ctx:
        out.append(GuardInput("context", ep.turns[0], task, tuple(ctx)))
    return out


def evaluate_corpus(
    workdir: Path,
    *,
    seed: int = 7,
    split: str = "all",
    spec: list[dict[str, Any]] | None = None,
    corpus_dir: Path | None = None,
    ids: set[str] | None = None,
) -> dict[str, Any]:
    entries, manifest = load_corpus() if corpus_dir is None else load_corpus(corpus_dir)
    if ids is not None:
        entries = [e for e in entries if e["id"] in ids]
    if split != "all":
        entries = [e for e in entries if e["split"] == split]
    gs = GuardSet.from_spec(spec or EVAL_SPEC, DEFAULT_REGISTRY)
    mgr = EpisodeStateManager(workdir / "shop", seed=seed)
    log = EventLog(f"guard-plugins-eval-{seed}")
    rows = []
    for i, e in enumerate(entries):
        eid = f"ev-{e['id']}"
        db = mgr.prepare(eid)
        actor, victim = pick_accounts(mgr.spec["accounts"], e["kind"], i)
        conn = connect(db)
        ep = bind(
            e, conn, mgr.spec["accounts"], actor_id=actor, victim_id=victim, ticket_id=f"T-{i:04d}"
        )
        conn.close()
        log.start_episode(eid, "attack" if e["kind"] == "attack" else "legal")
        sigs = []
        with GuardHost(log.writer, episode_id=eid, db_path=db) as host:
            for inp in episode_inputs(ep):
                for r in host.evaluate(gs, inp):
                    sigs.append(
                        {
                            "plugin": r.plugin_id,
                            "stage": r.stage,
                            "status": r.status,
                            "signal": r.signal.signal if r.signal else None,
                            "score": r.signal.score if r.signal else None,
                            "labels": list(r.signal.labels) if r.signal else [],
                            "reasons": list(r.signal.reasons) if r.signal else [],
                        }
                    )
        log.end_episode(eid)
        mgr.finish(eid)
        alarm = [s for s in sigs if s["signal"] in ("flag", "block")]
        rows.append(
            {
                "id": e["id"],
                "kind": e["kind"],
                "split": e["split"],
                "family": e["axes"]["mechanism"] if e["kind"] == "attack" else e["control_type"],
                "goal": e["axes"]["goal"] if e["kind"] == "attack" else None,
                "alarm": bool(alarm),
                "block": any(s["signal"] == "block" for s in sigs),
                "max_score": max((s["score"] or 0.0) for s in sigs) if sigs else 0.0,
                "signals": alarm,
            }
        )
    log.close()
    return {
        "seed": seed,
        "split": split,
        "corpus_sha256": manifest["sha256"],
        "guard_set": gs.spec,
        "guard_set_fingerprint": gs.fingerprint(),
        "summary": summarize_rows(rows),
        "episodes": rows,
    }


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for split in sorted({r["split"] for r in rows}) + ["all"]:
        sel = [r for r in rows if split == "all" or r["split"] == split]
        atk = [r for r in sel if r["kind"] == "attack"]
        ctl = [r for r in sel if r["kind"] == "control"]
        tp = sum(r["alarm"] for r in atk)
        fp = sum(r["alarm"] for r in ctl)
        fam: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        for r in sel:
            fam[f"{r['kind']}:{r['family']}"][0] += r["alarm"]
            fam[f"{r['kind']}:{r['family']}"][1] += 1
        out[split] = {
            "TP": tp,
            "FN": len(atk) - tp,
            "FP": fp,
            "TN": len(ctl) - fp,
            "attacks_blocked": sum(r["block"] for r in atk),
            "controls_blocked": sum(r["block"] for r in ctl),
            "by_family": {k: {"alarm": v[0], "n": v[1]} for k, v in sorted(fam.items())},
        }
    return out
