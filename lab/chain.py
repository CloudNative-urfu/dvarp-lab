"""Хеш-цепочка журнала: JSONL, каждая строка содержит seq, prev и собственный хеш."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def _canonical(data: object) -> bytes:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _line_hash(seq: int, prev: str, payload: object) -> str:
    return hashlib.sha256(_canonical({"seq": seq, "prev": prev, "payload": payload})).hexdigest()


GENESIS = "0" * 64


class Chain:
    """Append-only журнал с цепочкой хешей поверх JSONL-файла."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def append(self, payload: dict) -> str:
        seq, prev = self._tail()
        digest = _line_hash(seq, prev, payload)
        record = {"seq": seq, "prev": prev, "payload": payload, "hash": digest}
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        return digest

    def verify(self) -> list[str]:
        """Возвращает список дефектов цепочки; пустой список — цепочка цела."""
        defects: list[str] = []
        if not self.path.exists():
            return defects
        seq_expected, prev_expected = 1, GENESIS
        for raw in self.path.read_text(encoding="utf-8").splitlines():
            if not raw.strip():
                continue
            rec = json.loads(raw)
            if rec.get("seq") != seq_expected:
                defects.append(f"seq {rec.get('seq')} != {seq_expected}")
            if rec.get("prev") != prev_expected:
                defects.append(f"prev сломан на seq {rec.get('seq')}")
            digest = _line_hash(rec["seq"], rec["prev"], rec["payload"])
            if rec.get("hash") != digest:
                defects.append(f"payload изменён на seq {rec.get('seq')}")
            prev_expected, seq_expected = rec.get("hash"), seq_expected + 1
        return defects

    def _tail(self) -> tuple[int, str]:
        if not self.path.exists():
            return 1, GENESIS
        lines = [
            line for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()
        ]
        if not lines:
            return 1, GENESIS
        rec = json.loads(lines[-1])
        return rec["seq"] + 1, rec["hash"]
