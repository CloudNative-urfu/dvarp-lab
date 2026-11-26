"""Эпизод атаки: цель (замороженная претензия по данным мира) + метод + тон.

Барьер: attack_svc не читает БД магазина и не знает решений гвардрейлов — только
HTTP /turn к shop_svc и /record в filter_svc; наружу от атакующего — только
текст. Промпт атакующего собирается здесь из «цель × метод × тон» без обращений
к shop (бриф исключён, dvarp-lab#6): претензия — из цели и манифеста мира,
метод — путь давления, тон — ось стиля; стартовая реплика — отрендеренная
претензия, без рандома и без генерации.
"""

from __future__ import annotations

from typing import Any

from lab import world as lab_world
from lab.nominal import is_local_url
from lab.seeds import derive_seed
from services.traffic.episode import SESSION_CLOSED
from services.traffic.record import ChatModel, Recorder
from services.traffic.style import load_styles

from .attacker import LlmAttacker, StubAttacker, build_system_prompt
from .tactics import load_tactics, method_prompt


def run_attack(
    episode_id: str,
    config_name: str,
    attacker_model: dict[str, Any],
    tactic_name: str,
    budget: int,
    seed: int,
    style_name: str | None = None,
    probe: bool = False,
    remote_llm: bool = False,
    run_id: str | None = None,
    *,
    goal: str,
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
    goals = lab_world.load_goals()
    if goal not in goals:
        raise ValueError(f"цель {goal!r} отсутствует в frozen/corpus/goals.json")
    style = None
    if style_name is not None:
        styles = load_styles()
        if style_name not in styles:
            raise ValueError(f"стиль {style_name!r} отсутствует в frozen/styles.json")
        style = styles[style_name]
    # Претензия цели: факты манифеста мира, механическая подстановка — без рандома,
    # без генерации и без обращений к shop.
    entry = goals[goal]
    manifest = lab_world.load_manifest()
    claim = lab_world.render_claim(entry["claim"], lab_world.claim_facts(entry, manifest))
    prompt = build_system_prompt(
        entry["vector"], claim, method_prompt(registry[tactic_name]), style
    )
    recorder = Recorder(filter_svc, episode_id, "attack", attacker_model)
    # не-локальный эндпоинт атакующего маркирует записи сам (инвариант 8c)
    remote_llm = remote_llm or bool(attacker_base_url and not is_local_url(attacker_base_url))
    recorder.raw_extra = {"config_name": config_name}
    if attacker_complete or attacker_base_url:
        import os

        model = ChatModel(
            recorder,
            complete=attacker_complete,
            base_url=attacker_base_url,
            model=os.environ.get("LAB_ATTACKER_LLM_MODEL"),
            api_key=os.environ.get("LAB_ATTACKER_LLM_API_KEY"),
        )
        attacker = LlmAttacker(prompt, claim, model)
    else:
        attacker = StubAttacker(claim, derive_seed(seed, episode_id, "attacker"), style=style)

    attempts, last_reply = 0, None
    while attempts < budget:
        text = attacker.opening() if attempts == 0 else attacker.reply(last_reply)
        if text is None:
            return {"outcome": "attacker_stopped", "turns": attempts, "attempts": attempts}
        resp = shop.post(
            "/turn",
            {
                "episode_id": episode_id,
                "channel": "attack",
                "text": text,
                "turn": attempts,
                "goal": goal,
            },
        )
        last_reply = resp.get("text")
        recorder.raw_extra = {
            "config_name": config_name,
            "tactic": tactic_name,
            "goal": goal,
            **({"style": style_name} if style_name else {}),
            **({"probe": True} if probe else {}),
            **({"remote_llm": True} if remote_llm else {}),
            "seed": seed,
            **({"run_id": run_id} if run_id else {}),
        }
        recorder.flush(attempts, last_reply or "")
        attempts += 1
        if resp.get("ended"):
            return {
                "outcome": SESSION_CLOSED,
                "turns": attempts,
                "attempts": attempts,
            }
    return {"outcome": "budget_exhausted", "turns": attempts, "attempts": attempts}
