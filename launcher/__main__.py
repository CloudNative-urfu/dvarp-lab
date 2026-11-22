"""Запускатель: перебор сетки «модель × конфигурация × сценарий», парные прогоны.

Матрица ячейки = (config, style, tactic). На каждую ячейку: номинальная проверка,
сброс БД магазина от seed, снимок исходного состояния, парные прогоны (легальный
и атакующий эпизоды на одном исходном состоянии), манифест в runs/<run_id>/.
Расчёт метрик — по флагу --compute, в любое время (metrics_svc).
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from lab import nominal
from lab.modelspec import FROZEN_DIR, ModelSpec, load_roster, resolve
from lab.seeds import derive_seed
from lab.svc_client import Svc

SHOP_URL = os.environ.get("LAB_SHOP_URL", "http://127.0.0.1:9411")
TRAFFIC_URL = os.environ.get("LAB_TRAFFIC_URL", "http://127.0.0.1:9412")
ATTACK_URL = os.environ.get("LAB_ATTACK_URL", "http://127.0.0.1:9413")
METRICS_URL = os.environ.get("LAB_METRICS_URL", "http://127.0.0.1:9415")
RUNS_DIR = Path(os.environ.get("LAB_RUNS_DIR", "runs"))


def _agent_model(name: str | None) -> ModelSpec:
    roster = load_roster()
    if name:
        return resolve(name, "agent", roster)
    spec = next(m for m in roster.values() if m.role == "agent")
    return resolve(spec.name, "agent", roster)


def _attacker_model(name: str | None) -> ModelSpec | None:
    if not name:
        return None
    return resolve(name, "attacker", load_roster())


def _scenarios(args: argparse.Namespace) -> list[dict]:
    styles = args.styles.split(",") if args.styles else _default_styles()
    tactics = args.tactics.split(",") if args.tactics else _default_tactics()
    pairs = [(s, t) for s in styles for t in tactics]
    if args.pairs:
        pairs = [tuple(p.split("=")) for p in args.pairs.split(",")]  # style=tactic
    return [{"style": s, "tactic": t} for s, t in pairs]


def _default_styles() -> list[str]:
    styles = json.loads((FROZEN_DIR / "styles.json").read_text())["styles"]
    return sorted(s["name"] for s in styles)


def _default_tactics() -> list[str]:
    tactics = json.loads((FROZEN_DIR / "corpus" / "tactics.json").read_text())["tactics"]
    return sorted(t["name"] for t in tactics)


def run(args: argparse.Namespace) -> dict:
    shop, traffic, attack, metrics = (
        Svc(SHOP_URL),
        Svc(TRAFFIC_URL),
        Svc(ATTACK_URL),
        Svc(METRICS_URL),
    )
    agent_model = _agent_model(args.agent)
    attacker_model = _attacker_model(args.attacker)
    config = json.loads((FROZEN_DIR / "configs" / f"{args.config}.json").read_text())
    problems = nominal.check_config(args.config, config, [agent_model])
    if problems:
        raise SystemExit("номинальная проверка не пройдена:\n" + "\n".join(problems))

    run_id = f"{args.config}-{args.seed}-{time.strftime('%Y%m%dT%H%M%S')}"
    manifest = {
        "run_id": run_id,
        "seed": args.seed,
        "config": args.config,
        "agent_model": agent_model.as_dict(),
        "attacker_model": attacker_model.as_dict() if attacker_model else None,
        "episodes_per_scenario": args.episodes,
        "budget": args.budget,
        "cells": [],
    }

    for scenario in _scenarios(args):
        cell = {"scenario": scenario, "episodes": []}
        shop.post("/reset", {"seed": args.seed})
        snap = shop.post("/snapshot", {"label": f"{run_id}-start"})
        for i in range(args.episodes):
            seed_l = derive_seed(args.seed, args.config, scenario["style"], i, "legal")
            legal = traffic.post(
                "/run-episode",
                {
                    "episode_id": f"{run_id}-L{i}-{scenario['style']}",
                    "config_name": args.config,
                    "agent_model": agent_model.as_dict(),
                    "style": scenario["style"],
                    "seed": seed_l,
                    "run_id": run_id,
                },
            )
            shop.post("/snapshot/restore", {"snapshot_id": snap["snapshot_id"]})
            seed_a = derive_seed(args.seed, args.config, scenario["tactic"], i, "attack")
            body = {
                "episode_id": f"{run_id}-A{i}-{scenario['tactic']}",
                "config_name": args.config,
                "attacker_model": (attacker_model or agent_model).as_dict(),
                "tactic": scenario["tactic"],
                "budget": args.budget,
                "seed": seed_a,
                "run_id": run_id,
            }
            attacked = attack.post("/run-episode", body)
            shop.post("/snapshot/restore", {"snapshot_id": snap["snapshot_id"]})
            cell["episodes"].append({"legal": legal, "attack": attacked})
        manifest["cells"].append(cell)

    out = RUNS_DIR / run_id
    out.mkdir(parents=True, exist_ok=True)
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if args.compute:
        metrics.post("/compute", {"config_name": args.config})
    return manifest


def main() -> None:
    p = argparse.ArgumentParser(prog="launcher")
    p.add_argument("--config", default="g0")
    p.add_argument("--episodes", type=int, default=1)
    p.add_argument("--budget", type=int, default=8)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--agent", default=None, help="имя модели агента из frozen/llm.json")
    p.add_argument("--attacker", default=None, help="модель атакующего из frozen/llm.json")
    p.add_argument("--styles", default=None, help="стили через запятую (default: все)")
    p.add_argument("--tactics", default=None, help="тактики через запятую (default: все)")
    p.add_argument(
        "--pairs",
        default=None,
        help="явные пары style=tactic через запятую (иначе декартово произведение)",
    )
    p.add_argument("--compute", action="store_true", help="запустить расчёт метрик после прогона")
    args = p.parse_args()
    manifest = run(args)
    print(json.dumps({"run_id": manifest["run_id"], "cells": len(manifest["cells"])}, indent=2))


if __name__ == "__main__":
    main()
