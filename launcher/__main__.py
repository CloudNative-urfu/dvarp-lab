"""CLI-обёртка над спецификацией осей кампании (для статьи и воспроизводителей)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from launcher.campaign import run_campaign


def main() -> None:
    """CLI-обёртка над спецификацией осей (для статьи и воспроизводителей)."""

    p = argparse.ArgumentParser(prog="launcher")
    p.add_argument("--config", default=None)
    p.add_argument("--episodes", type=int, default=1)
    p.add_argument("--budget", type=int, default=8)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--seeds-to", type=int, default=None, help="перебор сидов --seed..N")
    p.add_argument("--agent", default=None)
    p.add_argument("--attacker", default=None)
    p.add_argument("--styles", default=None, help="стили через запятую (default: все)")
    p.add_argument("--goals", default=None, help="цели через запятую (default: все)")
    p.add_argument("--tactics", default=None, help="методы через запятую (default: все)")
    p.add_argument("--pairs", default=None, help="пары style=tactic через запятую")
    p.add_argument("--tactics-split", default=None, choices=["dev", "holdout"])
    p.add_argument("--compute", action="store_true")
    p.add_argument("--yes", action="store_true", help="подтвердить объём сверх guard")
    p.add_argument(
        "--allow-remote-llm",
        action="store_true",
        help="устарел: принимается и игнорируется (remote маркируется автоматически)",
    )
    p.add_argument("--spec", default=None, help="путь к JSON-спецификации осей (вместо флагов)")
    args = p.parse_args()
    if args.spec:
        spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    else:
        spec: dict[str, Any] = {"budget": args.budget, "compute": args.compute}
        if args.config:
            spec["configs"] = {"mode": "point", "point": args.config}
        if args.styles:
            spec["styles"] = {"mode": "set", "values": args.styles.split(",")}
        if args.goals:
            spec["goals"] = {"mode": "set", "values": args.goals.split(",")}
        if args.tactics:
            spec["tactics"] = {"mode": "set", "values": args.tactics.split(",")}
        elif args.tactics_split:
            spec["tactics"] = {"mode": "all", "split": args.tactics_split}
        if args.pairs:
            spec["scenario_pairs"] = [
                {"style": s, "tactic": t} for s, t in (x.split("=") for x in args.pairs.split(","))
            ]
        spec["episodes"] = {"mode": "point", "point": args.episodes}
        if args.seeds_to:
            spec["seeds"] = {"mode": "range", "range": [args.seed, args.seeds_to]}
        else:
            spec["seeds"] = {"mode": "point", "point": args.seed}
        if args.agent:
            spec["agent_models"] = {"mode": "point", "point": args.agent}
        if args.attacker:
            spec["attacker_models"] = {"mode": "point", "point": args.attacker}
        if args.yes:
            spec["confirm"] = True
        if args.allow_remote_llm:
            spec["allow_remote_llm"] = True
    try:
        manifest = run_campaign(spec)
    except SystemExit as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(2) from None
    if manifest.get("needs_confirm"):
        print(
            f"объём {manifest['episodes']} эпизодов сверх guard {manifest['guard']}; "
            "перезапустите с --yes (или confirm: true в спеке)",
            file=sys.stderr,
        )
        raise SystemExit(2) from None
    print(json.dumps({"run_id": manifest["run_id"], "cells": len(manifest["cells"])}, indent=2))


if __name__ == "__main__":
    main()
