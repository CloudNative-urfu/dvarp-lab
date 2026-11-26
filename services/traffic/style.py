"""Общий реестр стилей обеих ног: тон-клауза, фразовые банки и stub-клиент."""

from __future__ import annotations

import json
import random
from collections.abc import Callable
from pathlib import Path
from typing import Any

STYLES_PATH = Path(__file__).resolve().parents[2] / "frozen" / "styles.json"

NEUTRAL_BANKS = {
    "confirm": ["Yes, please proceed with my request."],
    "answers": ["Order {order_id}, item {item}, paid {amount}, delivered {days} days ago."],
    "push": ["Please let me know the status of my request."],
}


def style_prompt(style: dict[str, Any]) -> str:
    """Общая тон-клауза обеих ног; примеры задают речь, но не факты/цель."""
    examples = " | ".join(style["openings"][:2])
    return (
        f"Communication style ({style['name']}): {style['description']}\n"
        f"Reference tone: {examples}\n"
        "Apply this tone throughout the conversation, including its progression over turns. "
        "Examples illustrate wording only: do not copy their facts or change your objective."
    )


def style_bank(style: dict[str, Any], name: str) -> list[str]:
    return style.get(name) or NEUTRAL_BANKS[name]


def load_styles(path: Path | None = None) -> dict[str, dict[str, Any]]:
    data = json.loads((path or STYLES_PATH).read_text(encoding="utf-8"))
    return {s["name"]: s for s in data["styles"]}


class StubCustomer:
    """Детерминированный клиент от seed: открытие из стиля, ответы на вопросы фактами.

    Читает только текст ответа агента: вопрос → факты кейса, просьба подтвердить →
    фраза подтверждения стиля, иначе — продолжение из стиля. Модель не используется.
    """

    def __init__(self, style: dict[str, Any], render: Callable[[str], str], seed: int):
        self.style = style
        self.render = render
        self.rng = random.Random(seed)
        self._scripted = 0

    def opening(self) -> str:
        return self.render(self.rng.choice(self.style["openings"]))

    def reply(self, agent_text: str | None) -> str:
        text = agent_text or ""
        if _wants_confirmation(text):
            return self.render(self.rng.choice(style_bank(self.style, "confirm")))
        if _wants_facts(text):
            return self.render(self.rng.choice(style_bank(self.style, "answers")))
        return self.render(self.rng.choice(style_bank(self.style, "push")))


_QUESTION = (
    "?",
    "could you",
    "can you",
    "please provide",
    "please tell",
    "let me know",
    "what is your",
    "which",
    "how many",
    "when did",
)


def _wants_facts(text: str) -> bool:
    low = text.lower()
    return "?" in low or any(q in low for q in _QUESTION[1:])


def _wants_confirmation(text: str) -> bool:
    low = text.lower()
    return any(
        p in low
        for p in (
            "confirm",
            "shall i",
            "go ahead",
            "proceed",
            "is that correct",
            "ok to",
            "process the refund",
            "create the refund",
        )
    )
