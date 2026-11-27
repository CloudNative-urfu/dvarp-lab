"""Реестр методов давления: frozen/corpus/tactics.json — ось «метод» атаки.

Метод задаёт, КАК давить: описание + примеры-иллюстрации (схема dvarp.tactics/2,
dvarp-lab#4: реплики корпуса atk-* живут иллюстрациями своего метода) входят в
system-промпт атакующего целиком. Данные
претензии — в цели (frozen/corpus/goals.json), тон — в оси стиля
(frozen/styles.json); обязательных реплик-диалогов нет. Стартовую реплику
LLM-атакующий пишет сам по методу; stub начинает с претензии цели.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

TACTICS_PATH = Path(__file__).resolve().parents[2] / "frozen" / "corpus" / "tactics.json"


def load_tactics(path: Path | None = None) -> dict[str, dict[str, Any]]:
    data = json.loads((path or TACTICS_PATH).read_text(encoding="utf-8"))
    return {t["name"]: t for t in data["tactics"]}


def method_prompt(method: dict[str, Any]) -> str:
    """Путь давления: описание метода + примеры-иллюстрации (если реестр их даёт)."""
    parts = [(method.get("description") or "").strip()]
    for ex in method.get("illustrations", []):
        if isinstance(ex, str) and ex.strip():
            parts.append(f"Example: {ex.strip()}")
    return "\n".join(p for p in parts if p)
