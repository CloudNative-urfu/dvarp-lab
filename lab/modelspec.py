"""Ростер моделей (frozen/llm.json) и пинирование model_spec в записях прогонов."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

FROZEN_DIR = Path(__file__).resolve().parent.parent / "frozen"


@dataclass(frozen=True)
class ModelSpec:
    name: str
    role: str
    params_b: float
    revision: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_roster(path: Path | None = None) -> dict[str, ModelSpec]:
    source = Path(path) if path else FROZEN_DIR / "llm.json"
    data = json.loads(source.read_text(encoding="utf-8"))
    return {m["name"]: ModelSpec(**m) for m in data["models"]}


def resolve(name: str, role: str, roster: dict[str, ModelSpec] | None = None) -> ModelSpec:
    roster = roster if roster is not None else load_roster()
    spec = roster.get(name)
    if spec is None:
        raise KeyError(f"модель {name!r} отсутствует в ростере frozen/llm.json")
    return ModelSpec(spec.name, role, spec.params_b, spec.revision)
