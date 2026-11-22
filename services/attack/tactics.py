"""Реестр тактик: frozen/corpus/tactics.json и размеченные стартовые промпты корпуса."""

from __future__ import annotations

import json
import random
import re
from pathlib import Path
from typing import Any

CORPUS_PATH = Path(__file__).resolve().parents[2] / "frozen" / "corpus" / "darp_corpus_v2.jsonl"
TACTICS_PATH = Path(__file__).resolve().parents[2] / "frozen" / "corpus" / "tactics.json"

_PLACEHOLDER_RE = re.compile(r"\{([a-z_0-9]+)(?::([a-z_]+))?(?::(\d+))?\}")


def load_tactics(path: Path | None = None) -> dict[str, dict[str, Any]]:
    data = json.loads((path or TACTICS_PATH).read_text(encoding="utf-8"))
    return {t["name"]: t for t in data["tactics"]}


def load_entries(path: Path | None = None) -> dict[str, dict[str, Any]]:
    entries = [
        json.loads(l)
        for l in (path or CORPUS_PATH).read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    return {e["id"]: e for e in entries}


def start_prompt(
    tactic: dict[str, Any], seed: int, entries: dict[str, dict[str, Any]] | None = None
) -> str:
    """Размеченный стартовый промпт тактики: реплика корпуса, плейсхолдеры → seed-значения.

    Атакующий не знает реальную БД магазина (барьер): вместо подстановки реальных id —
    детерминированные от seed синтетические значения.
    """
    entries = entries if entries is not None else load_entries()
    ids = tactic["entries"]
    entry = entries[ids[random.Random(seed).randrange(len(ids))]]
    return resolve_placeholders(entry["turns"][0], seed)


def resolve_placeholders(text: str, seed: int) -> str:
    rng = random.Random(seed)

    def sub(m: re.Match) -> str:
        name, _, _ = m.group(1), m.group(2), m.group(3)
        if name in ("order", "victim_order"):
            return f"ORD-{rng.randrange(10000):05d}"
        if name in ("item", "victim_item"):
            return rng.choice(
                [
                    "wireless headphones",
                    "running shoes",
                    "coffee grinder",
                    "backpack",
                    "smart watch",
                ]
            )
        if name in ("price", "price_x2"):
            return f"${rng.randrange(10, 400)}.{rng.randrange(100):02d}"
        if name in ("victim_email", "my_name"):
            return rng.choice(["customer", "j.smith", "sam"])
        if name == "victim_name":
            return rng.choice(["John", "Maria", "Alex"])
        return m.group(0)

    return _PLACEHOLDER_RE.sub(sub, text)
