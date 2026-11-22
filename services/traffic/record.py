"""LLM-клиент и кассета: строка в raw.llm_calls на каждый вызов модели."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx

Messages = list[dict[str, str]]
Complete = Callable[[Messages], str]


class Recorder:
    """Отправка сырья в filter_svc POST /record; наружу record_id, текстов кассеты нет."""

    def __init__(self, svc: Any, episode_id: str, channel: str, model_spec: dict):
        self.svc = svc
        self.episode_id = episode_id
        self.channel = channel
        self.model_spec = model_spec
        self.llm_calls: list[dict] = []
        self.record_ids: list[str] = []
        self.raw_extra: dict = {}

    def add_call(self, role: str, request: Messages, response: str) -> None:
        self.llm_calls.append(
            {"role": role, "model": self.model_spec, "request": request, "response": response}
        )

    def flush(self, turn: int, text: str) -> str:
        raw = {"llm_calls": self.llm_calls, **self.raw_extra}
        record = self.svc.post(
            "/record",
            {
                "episode_id": self.episode_id,
                "channel": self.channel,
                "turn": turn,
                "text": text,
                "model_spec": self.model_spec,
                "raw": raw,
                "snapshot": {},
            },
        )
        self.llm_calls = []
        record_id = record.get("record_id")
        if record_id is not None:
            self.record_ids.append(record_id)
        return record_id

    def llm_lines(self) -> list[str]:
        """Кассетные строки (запрос→ответ) текущего буфера — сырьё, не остаётся в ответе."""
        return [json.dumps(c, ensure_ascii=False, sort_keys=True) for c in self.llm_calls]


class ChatModel:
    """Обёртка вызова модели: каждый вызов уходит строкой в кассету рекордера.

    complete — внешний вызов (http в проде, заглушка в тестах); когда не задан,
    используется OpenAI-совместимый endpoint по base_url.
    """

    def __init__(
        self, recorder: Recorder, *, complete: Complete | None = None, base_url: str | None = None
    ):
        self.recorder = recorder
        self._complete = complete or _openai_complete(base_url or "")

    def reply(self, role: str, messages: Messages) -> str:
        response = self._complete(messages)
        self.recorder.add_call(role, messages, response)
        return response


def _openai_complete(base_url: str) -> Complete:
    def complete(messages: Messages) -> str:
        r = httpx.post(
            base_url.rstrip("/") + "/chat/completions",
            json={"messages": messages},
            timeout=600.0,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    return complete
