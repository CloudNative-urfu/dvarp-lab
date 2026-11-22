"""Кассета: по строке на пару запрос→ответ к модели, для офлайн-разбора живых прогонов."""

from __future__ import annotations

import json
from pathlib import Path


class Cassette:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def record(self, role: str, model: dict, request: object, response: object) -> None:
        entry = {
            "role": role,
            "model": model,
            "request": request,
            "response": response,
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
