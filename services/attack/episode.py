"""Эпизод атаки: размеченный стартовый промпт тактики + прямой текстовый цикл.

Барьер: attack_svc не читает БД магазина и не знает решений гвардрейлов — только
HTTP /turn к shop_svc и /record в filter_svc; наружу от атакующего — только текст.
"""

from __future__ import annotations

from typing import Any

from lab.seeds import derive_seed
from services.traffic.episode import outcome_of
from services.traffic.record import ChatModel, Recorder

from .attacker import LlmAttacker, StubAttacker
from .tactics import load_tactics, start_prompt


def run_attack(
    episode_id: str,
    config_name: str,
    attacker_model: dict[str, Any],
    tactic_name: str,
    budget: int,
    seed: int,
    run_id: str | None = None,
    *,
    shop: Any,
    filter_svc: Any,
    attacker_complete: Any = None,
    attacker_base_url: str | None = None,
) -> dict[str, Any]:
    if budget < 1:
        raise ValueError("budget должен быть >= 1")
    registry = load_tactics()
    if tactic_name not in registry:
        raise ValueError(f"тактика {tactic_name!r} отсутствует в frozen/corpus/tactics.json")
    prompt = start_prompt(registry[tactic_name], derive_seed(seed, episode_id))
    recorder = Recorder(filter_svc, episode_id, "attack", attacker_model)
    recorder.raw_extra = {"config_name": config_name}
    if attacker_complete or attacker_base_url:
        model = ChatModel(recorder, complete=attacker_complete, base_url=attacker_base_url)
        attacker = LlmAttacker(tactic_name, prompt, model)
    else:
        attacker = StubAttacker(prompt, derive_seed(seed, episode_id, "attacker"))

    attempts, last_reply = 0, None
    while attempts < budget:
        text = attacker.opening() if attempts == 0 else attacker.reply(last_reply)
        if text is None:
            return {"outcome": "attacker_stopped", "turns": attempts, "attempts": attempts}
        resp = shop.post(
            "/turn", {"episode_id": episode_id, "channel": "attack", "text": text, "turn": attempts}
        )
        last_reply = resp.get("text")
        recorder.raw_extra = {
            "config_name": config_name,
            "tactic": tactic_name,
            "seed": seed,
            **({"run_id": run_id} if run_id else {}),
        }
        recorder.flush(attempts, last_reply or "")
        attempts += 1
        if resp.get("ended"):
            return {
                "outcome": outcome_of(resp.get("session_status")),
                "turns": attempts,
                "attempts": attempts,
            }
    return {"outcome": "budget_exhausted", "turns": attempts, "attempts": attempts}
