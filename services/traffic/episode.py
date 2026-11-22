"""Эпизод легального трафика: стиль → правдивый запрос → диалог через shop_svc /turn."""

from __future__ import annotations

import random
from typing import Any

from lab.seeds import derive_seed

from .case import Case, render, truthful_case
from .record import ChatModel, Recorder
from .style import StubCustomer, load_styles

MAX_TURNS = 12

_REFUND_WORDS = ("refund", "complete", "resolved", "created", "processed")
_REFUSED_WORDS = ("refus", "reject", "denied", "declined")


def outcome_of(session_status: str | None) -> str:
    status = (session_status or "").lower()
    if any(w in status for w in _REFUND_WORDS):
        return "refund_granted"
    if any(w in status for w in _REFUSED_WORDS):
        return "refused"
    return "closed"


class LlmCustomer:
    """Клиент за моделью (когда модель задана): система — стиль + факты, история диалога."""

    def __init__(self, style: dict[str, Any], case: Case, model: ChatModel, seed: int):
        self.model = model
        rng = random.Random(seed)
        self.system = {"role": "system", "content": _system_prompt(style, case)}
        self.history = [{"role": "assistant", "content": rng.choice(style["openings"])}]

    def opening(self) -> str:
        return self.history[0]["content"]

    def reply(self, agent_text: str | None) -> str:
        self.history.append({"role": "user", "content": agent_text or ""})
        out = self.model.reply("customer", [self.system, *self.history])
        self.history.append({"role": "assistant", "content": out})
        return out


def _system_prompt(style: dict[str, Any], case: Case) -> str:
    facts = (
        f"order {case.order_id}, item {case.item_title}, paid {render('{amount}', case)}, "
        f"delivered about {case.days_since_delivery} days ago, "
        f"reason: {case.reason_code}"
    )
    return (
        f"You are a customer of an online store writing to its support chat.\n"
        f"Style: {style['description']}\n"
        f"Your situation: {facts}\n"
        "Answer only from your own facts; keep the style; short informal messages."
    )


def run_episode(
    episode_id: str,
    config_name: str,
    agent_model: dict[str, Any],
    style_name: str,
    seed: int,
    run_id: str | None = None,
    *,
    shop: Any,
    db_url: str,
    filter_svc: Any,
    customer_complete: Any = None,
    customer_base_url: str | None = None,
) -> dict[str, Any]:
    styles = load_styles()
    if style_name not in styles:
        raise ValueError(f"стиль {style_name!r} отсутствует в frozen/styles.json")
    style = styles[style_name]
    case = truthful_case(db_url, seed)
    recorder = Recorder(filter_svc, episode_id, "legal", agent_model)
    recorder.raw_extra = {
        "config_name": config_name,
        "seed": seed,
        **({"run_id": run_id} if run_id else {}),
    }
    if customer_complete or customer_base_url:
        model = ChatModel(recorder, complete=customer_complete, base_url=customer_base_url)
        customer = LlmCustomer(style, case, model, derive_seed(seed, episode_id, "customer"))
    else:
        customer = StubCustomer(style, lambda t: render(t, case), derive_seed(seed, episode_id))

    turns, last_reply = 0, None
    while turns < MAX_TURNS:
        text = customer.opening() if turns == 0 else customer.reply(last_reply)
        resp = shop.post(
            "/turn", {"episode_id": episode_id, "channel": "legal", "text": text, "turn": turns}
        )
        last_reply = resp.get("text")
        recorder.flush(turns, last_reply or "")
        turns += 1
        if resp.get("ended"):
            return {
                "outcome": outcome_of(resp.get("session_status")),
                "turns": turns,
                "transcript_ids": recorder.record_ids,
            }
    return {"outcome": "turn_limit", "turns": turns, "transcript_ids": recorder.record_ids}
