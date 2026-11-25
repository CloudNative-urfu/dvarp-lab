"""Запускатель: перебор сетки «модель × конфигурация × сценарий», парные прогоны.

Оси кампании — launcher.axes (point/range/all/all_limited над frozen-наборами).
Ячейка = (config, style, tactic, agent_model, attacker_model, seed). На каждую
ячейку: /configure (номинальная проверка + пин модели), /reset(seed), снимок
исходного состояния, парные прогоны (легальный и атакующий эпизоды в одном
стиле общения на одном исходном состоянии), манифест в runs/<run_id>/.
Расчёт метрик — по флагу compute, в любое время (metrics_svc).
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from lab import nominal
from lab.modelspec import ModelSpec, load_roster, resolve
from lab.seeds import derive_seed
from lab.svc_client import Svc
from launcher.axes import GUARD_VOLUME, resolve_campaign

SHOP_URL = os.environ.get("LAB_SHOP_URL", "http://127.0.0.1:9411")
TRAFFIC_URL = os.environ.get("LAB_TRAFFIC_URL", "http://127.0.0.1:9412")
ATTACK_URL = os.environ.get("LAB_ATTACK_URL", "http://127.0.0.1:9413")
METRICS_URL = os.environ.get("LAB_METRICS_URL", "http://127.0.0.1:9415")
FILTER_URL = os.environ.get("LAB_FILTER_URL", "http://127.0.0.1:9414")


def _runs_dir() -> Path:
    return Path(os.environ.get("LAB_RUNS_DIR", "runs"))


def default_services() -> dict[str, Svc]:
    return {
        "shop": Svc(SHOP_URL),
        "traffic": Svc(TRAFFIC_URL),
        "attack": Svc(ATTACK_URL),
        "metrics": Svc(METRICS_URL),
        "filter": Svc(FILTER_URL),
    }


def _final_outcome(flt: Svc | None, episode_id: str) -> str | None:
    """Structural outcome of a finished leg from filter episode_finals (#10)."""
    if flt is None:
        return None
    try:
        return (flt.get(f"/finals/{episode_id}") or {}).get("outcome")
    except Exception:  # noqa: BLE001 — no final row (old filter, failed finalize): unknown
        return None


def _model_spec(name: str | None, role: str) -> ModelSpec:
    """Модель по имени; None/без имени — первая модель роли из ростера.

    Ростер — не гейт: имя вне ростера даёт честный model_spec с пометкой
    remote-verification (params_b неизвестен).
    """
    roster = load_roster()
    if not name:
        spec = next(m for m in roster.values() if m.role == role)
        name = spec.name
    if name not in roster:
        return ModelSpec(name, role, params_b=None, revision="remote-verification")
    return resolve(name, role, roster)


# Оси, по которым эпизоды и так различаются в метриках (ключ config × model_spec × episode_id)
# или которые стоят в id отдельно (сид); остальные оси ячейки — сценарная сигнатура ноги.
_KEYED_ELSEWHERE = ("config", "agent_model", "attacker_model", "seed")


def attack_signature(cell: dict[str, Any]) -> list[str]:
    """Сценарные оси ячейки по порядку: стиль, тактика и любые новые (цель #4) — без правки формата."""
    return [str(v) for k, v in cell.items() if k not in _KEYED_ELSEWHERE and v is not None]


def attack_episode_id(run_id: str, i: int, cell: dict[str, Any]) -> str:
    return f"{run_id}-A{i}-{'-'.join(attack_signature(cell))}-s{cell['seed']}"


def run_campaign(
    spec: dict[str, Any],
    *,
    progress: Callable[[dict[str, Any]], None] | None = None,
    services: dict[str, Svc] | None = None,
) -> dict[str, Any]:
    """Кампания по спецификации осей. Возвращает манифест прогона."""
    svcs = services or default_services()
    shop, traffic, attack, metrics = (
        svcs["shop"],
        svcs["traffic"],
        svcs["attack"],
        svcs["metrics"],
    )
    flt = svcs.get("filter")
    camp = resolve_campaign(spec)
    cells = camp.cells()
    _, episodes_total = camp.volume()
    if episodes_total > GUARD_VOLUME and not spec.get("confirm"):
        return {"needs_confirm": True, "episodes": episodes_total, "guard": GUARD_VOLUME}
    report = progress or (lambda _p: None)

    configs = "+".join(camp.configs) if len(camp.configs) <= 2 else "multi"
    run_id = f"{configs}-s{camp.seeds[0]}-{time.strftime('%Y%m%dT%H%M%S')}"
    # allow_remote_llm в спеке принимается и игнорируется: remote определяется эндпоинтами
    remote = bool(nominal.remote_endpoints())
    manifest: dict[str, Any] = {
        "run_id": run_id,
        "remote_llm": remote,
        "budget": camp.budget,
        "episodes": camp.episodes,
        "axes": {
            "configs": camp.configs,
            "styles": camp.styles,
            "tactics": camp.tactics,
            "agent_models": camp.agent_models,
            "attacker_models": camp.attacker_models,
            "seeds": camp.seeds,
            "scenario_pairs": camp.scenario_pairs,
        },
        "cells": [],
    }
    report({"stage": "start", "run_id": run_id, "cells": len(cells)})

    done = 0
    for cell in cells:
        cfg, seed = cell["config"], cell["seed"]
        agent = _model_spec(cell["agent_model"], "agent")
        config = json.loads(
            (Path(__file__).resolve().parents[1] / "frozen" / "configs" / f"{cfg}.json").read_text()
        )
        problems = nominal.check_config(cfg, config, [agent])
        if problems:
            raise SystemExit(
                f"конфиг {cfg}: номинальная проверка не пройдена:\n" + "\n".join(problems)
            )
        attacker = (
            _model_spec(cell["attacker_model"], "attacker") if cell["attacker_model"] else agent
        )

        shop.post("/reset", {"seed": seed})  # сначала reset: он инициализирует журнал shop
        shop.post("/configure", {"config_name": cfg, "agent_model": agent.as_dict()})
        snap = shop.post("/snapshot", {"label": f"{run_id}-start"})
        cell_result: dict[str, Any] = {
            "config": cfg,
            "seed": seed,
            "agent_model": agent.as_dict(),
            "attacker_model": attacker.as_dict(),
            "scenario": {"style": cell["style"], "tactic": cell["tactic"]},
            "episodes": [],
        }
        for i in camp.episodes:
            legal = traffic.post(
                "/run-episode",
                {
                    "episode_id": f"{run_id}-L{i}-{cell['style']}-s{seed}",
                    "config_name": cfg,
                    "agent_model": agent.as_dict(),
                    "style": cell["style"],
                    "seed": derive_seed(seed, cfg, cell["style"], i, "legal"),
                    "run_id": run_id,
                    **({"remote_llm": True} if remote else {}),
                },
            )
            shop.post("/snapshot/restore", {"snapshot_id": snap["snapshot_id"]})
            attack_id = attack_episode_id(run_id, i, cell)
            legal["outcome"] = _final_outcome(
                flt, f"{run_id}-L{i}-{cell['style']}-s{seed}"
            ) or legal.get("outcome")
            attacked = attack.post(
                "/run-episode",
                {
                    "episode_id": attack_id,
                    "config_name": cfg,
                    "attacker_model": attacker.as_dict(),
                    "tactic": cell["tactic"],
                    "budget": camp.budget,
                    "seed": derive_seed(seed, cfg, *attack_signature(cell), i, "attack"),
                    "style": cell["style"],
                    "run_id": run_id,
                    **({"remote_llm": True} if remote else {}),
                },
            )
            shop.post("/snapshot/restore", {"snapshot_id": snap["snapshot_id"]})
            attacked["outcome"] = _final_outcome(flt, attack_id) or attacked.get("outcome")
            cell_result["episodes"].append(
                {
                    "episode": i,
                    "legal_episode_id": f"{run_id}-L{i}-{cell['style']}-s{seed}",
                    "attack_episode_id": attack_id,
                    "legal": legal,
                    "attack": attacked,
                }
            )
            done += 1
            report(
                {
                    "stage": "episode",
                    "cells_done": done,
                    "cells_total": len(cells),
                    "episodes_total": episodes_total,
                    "current": cell_result,
                }
            )
        manifest["cells"].append(cell_result)

    out = _runs_dir() / run_id
    out.mkdir(parents=True, exist_ok=True)
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if spec.get("compute"):
        for cfg in camp.configs:
            metrics.post("/compute", {"config_name": cfg})
    report({"stage": "done", "run_id": run_id})
    return manifest


def probe(
    spec: dict[str, Any],
    *,
    services: dict[str, Svc] | None = None,
) -> dict[str, Any]:
    """Одна атака без парной ноги: raw.probe=true, манифест не пишется, метрики пропускают."""
    svcs = services or default_services()
    shop, attack = svcs["shop"], svcs["attack"]
    agent = _model_spec(spec["agent_model"], "agent")
    attacker = (
        _model_spec(spec["attacker_model"], "attacker") if spec.get("attacker_model") else agent
    )
    cfg = spec["config"]
    config = json.loads(
        (Path(__file__).resolve().parents[1] / "frozen" / "configs" / f"{cfg}.json").read_text()
    )
    problems = nominal.check_config(cfg, config, [agent])
    if problems:
        raise SystemExit("номинальная проверка не пройдена:\n" + "\n".join(problems))
    seed = spec.get("seed")
    seed = int(seed) if seed is not None else derive_seed(0, cfg, spec["tactic"], 0, "probe")
    shop.post("/reset", {"seed": seed})  # reset инициализирует журнал, затем configure
    shop.post("/configure", {"config_name": cfg, "agent_model": agent.as_dict()})
    return attack.post(
        "/run-episode",
        {
            "episode_id": f"probe-{time.strftime('%Y%m%dT%H%M%S')}",
            "config_name": cfg,
            "attacker_model": attacker.as_dict(),
            "tactic": spec["tactic"],
            "budget": int(spec.get("budget", 8)),
            "seed": derive_seed(seed, cfg, spec["tactic"], 0, "attack"),
            "style": spec.get("style"),
            "probe": True,
            **({"remote_llm": True} if nominal.remote_endpoints() else {}),
        },
    )
