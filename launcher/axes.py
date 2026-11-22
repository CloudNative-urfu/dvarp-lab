"""Оси кампании: point / range / all / all_limited над замороженными наборами.

Перечисления (configs, styles, tactics, модели) — отсортированные списки frozen;
range = непрерывный срез отсортированного списка по значениям-границам;
числовые оси (episodes, seeds) — целые от 1, "all" на них запрещён (неограничен).
Технический режим "set" (явный список значений) — для CLI и пресетов.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from lab.modelspec import FROZEN_DIR

GUARD_VOLUME = 1000

ENUM_AXES = ("configs", "styles", "tactics", "agent_models", "attacker_models")
NUMERIC_AXES = ("episodes", "seeds")


def _sorted_configs() -> list[str]:
    """Конфигурации защиты; lock-файл и история заморозки — не оси кампании."""
    return sorted(
        p.stem for p in (FROZEN_DIR / "configs").glob("*.json") if p.stem not in ("configs.lock",)
    )


def _sorted_styles() -> list[str]:
    styles = json.loads((FROZEN_DIR / "styles.json").read_text())["styles"]
    return sorted(s["name"] for s in styles)


def _sorted_tactics(split: str | None = None) -> list[str]:
    data = json.loads((FROZEN_DIR / "corpus" / "tactics.json").read_text())
    names = sorted(t["name"] for t in data["tactics"])
    if split not in (None, "dev", "holdout"):
        raise ValueError(f"split тактик: dev|holdout, получено {split!r}")
    if split:
        entries = {
            e["id"]: e.get("split", "dev")
            for e in (
                json.loads(l)
                for l in (FROZEN_DIR / "corpus" / "darp_corpus_v2.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
                if l.strip()
            )
        }
        ext = FROZEN_DIR / "corpus" / "darp_corpus_v2_ext.jsonl"
        if ext.exists():
            entries.update(
                {
                    e["id"]: e.get("split", "dev")
                    for e in (
                        json.loads(l)
                        for l in ext.read_text(encoding="utf-8").splitlines()
                        if l.strip()
                    )
                }
            )
        by_name = {t["name"]: t["entries"] for t in data["tactics"]}
        names = [n for n in names if all(entries.get(eid, "dev") == split for eid in by_name[n])]
    return names


def _sorted_models(role: str) -> list[str]:
    roster = json.loads((FROZEN_DIR / "llm.json").read_text())["models"]
    return sorted(m["name"] for m in roster if m.get("role") == role)


def axis_universe(axis: str) -> list[Any]:
    if axis == "configs":
        return _sorted_configs()
    if axis == "styles":
        return _sorted_styles()
    if axis == "tactics":
        return _sorted_tactics()
    if axis == "agent_models":
        return _sorted_models("agent")
    if axis == "attacker_models":
        return _sorted_models("attacker")
    raise ValueError(f"неизвестная перечислимая ось {axis!r}")


def resolve_axis(axis: str, spec: dict[str, Any] | None) -> list[Any]:
    """spec: {"mode": point|range|all|all_limited|set, ...} или None = all (enum) / point(1) (numeric)."""
    spec = dict(spec) if spec else None
    if axis in NUMERIC_AXES:
        if spec is None:
            spec = {"mode": "point", "point": 0 if axis == "seeds" else 1}
        mode = spec.get("mode", "point")
        if mode == "point":
            if axis == "episodes":
                return list(range(1, int(spec["point"]) + 1))  # точечно = N эпизодов с 1-го
            return [int(spec["point"])]
        if mode == "range":
            lo, hi = int(spec["range"][0]), int(spec["range"][1])
            return list(range(lo, hi + 1))
        if mode == "all_limited":
            start = int(spec.get("offset", 1))
            return list(range(start, start + int(spec["limit"])))
        if mode == "set":
            return sorted({int(v) for v in spec["values"]})
        if mode == "all":
            raise ValueError(f"ось {axis} неограничена: используйте range/all_limited/point")
        raise ValueError(f"неизвестный режим {mode!r} оси {axis}")
    universe = axis_universe(axis)
    if spec is None:
        spec = {"mode": "all"}
    mode = spec.get("mode", "all")
    if mode == "all":
        split = spec.get("split")
        if axis == "tactics" and split:
            return _sorted_tactics(split)
        return list(universe)
    if mode == "point":
        v = spec["point"]
        if v not in universe:
            raise ValueError(f"{axis}: {v!r} отсутствует в frozen ({len(universe)} значений)")
        return [v]
    if mode == "set":
        missing = [v for v in spec["values"] if v not in universe]
        if missing:
            raise ValueError(f"{axis}: отсутствуют в frozen: {missing}")
        return sorted(spec["values"])
    if mode == "range":
        lo, hi = spec["range"]
        try:
            i, j = universe.index(lo), universe.index(hi)
        except ValueError as exc:
            raise ValueError(f"{axis}: границы range отсутствуют в frozen: {exc}") from None
        if i > j:
            i, j = j, i
        return universe[i : j + 1]
    if mode == "all_limited":
        offset = int(spec.get("offset", 0))
        limit = int(spec["limit"])
        return universe[offset : offset + limit]
    raise ValueError(f"неизвестный режим {mode!r} оси {axis}")


@dataclass
class Campaign:
    configs: list[str]
    styles: list[str]
    tactics: list[str]
    agent_models: list[str]
    attacker_models: list[str | None]
    episodes: list[int]
    seeds: list[int]
    budget: int
    scenario_pairs: list[tuple[str, str]] | None = None

    def cells(self) -> list[dict[str, Any]]:
        pairs = self.scenario_pairs or [(s, t) for s in self.styles for t in self.tactics]
        out = []
        for cfg in self.configs:
            for style, tactic in pairs:
                for am in self.agent_models:
                    for am_att in self.attacker_models or [None]:
                        for seed in self.seeds:
                            out.append(
                                {
                                    "config": cfg,
                                    "style": style,
                                    "tactic": tactic,
                                    "agent_model": am,
                                    "attacker_model": am_att,
                                    "seed": seed,
                                }
                            )
        return out

    def volume(self) -> tuple[int, int]:
        cells = len(self.cells())
        return cells, cells * len(self.episodes)


def resolve_campaign(spec: dict[str, Any]) -> Campaign:
    """spec: оси в формате resolve_axis + budget/episodes-оси; сценарные пары — опционально."""
    pairs = None
    if spec.get("scenario_pairs"):
        pairs = [(p["style"], p["tactic"]) for p in spec["scenario_pairs"]]
    attacker = resolve_axis("attacker_models", spec.get("attacker_models"))
    return Campaign(
        configs=resolve_axis("configs", spec.get("configs")),
        styles=resolve_axis("styles", spec.get("styles")),
        tactics=resolve_axis("tactics", spec.get("tactics")),
        agent_models=resolve_axis("agent_models", spec.get("agent_models")),
        attacker_models=attacker or [None],
        episodes=resolve_axis("episodes", spec.get("episodes")),
        seeds=resolve_axis("seeds", spec.get("seeds")),
        budget=int(spec.get("budget", 8)),
        scenario_pairs=pairs,
    )
