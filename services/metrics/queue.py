"""Analytic queue of the manual-review operators (issue #12; canon dvarp#39).

Задержка легального потока не симулируется, а вычисляется аналитически
(M/M/c — Эрланг C — при K > 1) поверх уже сохранённых финалов. Сценарий
(ревизия владельца 2026-11-24, семантика «минимум 30% сразу в очередь»):

- **минимум 30% обращений идут сразу в живую очередь** (клиенты,
  требующие человека; константа, не зависящая от защиты) — этот поток
  создаёт базовую загрузку операторов ρ₀ (якорь экономики);
- остальной поток (1−h)/h раз больше обрабатывает ИИ-агент; **эскалации
  приходят только из ИИ-канала**, их доли из прогонов ревейтятся на
  реалистичный микс через сценарную константу p_att (лабовый микс
  w_A = 0.5 — внутренний парный дизайн и в очередь напрямую не
  подставляется):

      доля_эскалаций_магазина = p_att·E_A + (1 − p_att)·E_L

- якорь масштаба (Эрланг C зависит и от размера очереди): число
  операторов K, время разбора S, терпение τ и доля h «сразу в очередь» —
  из пина экономики; поток человекков λ_чел = ρ₀·K·60/S; ИИ-поток
  λ_ИИ = λ_чел·(1−h)/h;
- λ_Q = λ_ИИ·доля_эскалаций; λ = λ_чел + λ_Q — суммарный поток в очередь
  (дренаж K·μ − λ считается от суммарного);
- P_wait = Эрланг C рекурсией Эрланга B (без аппроксимаций);
  W_q = P_wait/(K·μ − λ); отвал P(W_q > τ) = P_wait·exp(−(K·μ − λ)·τ/60)
  (терпение = SLA — один порог, ревизия канона dvarp#39);
- цена ухода — C_churn из пина; член ΔNet — безусловная вероятность
  потери легального клиента: w_L·E_L·P(W_q > τ)·C_churn (атакующий,
  уйдя из очереди, бизнесу не вредит).

При ρ = λ·S/K ≥ 1 очередь нестабильна (`stable = False`, задержки не
определены). Non-claims: очередь — модель, а не живой оператор; цена
минуты ожидания (C_queue) не заявлена в пине и в деньги не переводится
(задержка публикуется как время).
"""

from __future__ import annotations

import math
from typing import Any

QUEUE_MODEL_VERSION = "queue-analytic-lab-1"

NON_CLAIMS = (
    "the queue is a model, not a live operator",
    "cost per wait-minute (C_queue) is not pinned — the delay is reported as time only",
)


class QueueError(ValueError):
    """Некорректные параметры аналитической очереди."""


def erlang_b(k: int, load: float) -> float:
    """Эрланг B рекурсией: B(0) = 1, B(k) = a·B(k−1)/(k + a·B(k−1))."""
    if isinstance(k, bool) or not isinstance(k, int) or k < 1:
        raise QueueError(f"число операторов: целое ≥ 1, получено {k!r}")
    if not (math.isfinite(load) and load >= 0):
        raise QueueError(f"нагрузка {load!r}: конечное неотрицательное число")
    b = 1.0
    for i in range(1, k + 1):
        b = load * b / (i + load * b)
    return b


def erlang_c(servers: int, load: float) -> float:
    """Вероятность ожидания в M/M/c при нагрузке `load` = λ/μ < servers (Эрланг C)."""
    b = erlang_b(servers, load)
    if load >= servers:
        raise QueueError(f"нагрузка {load!r} ≥ {servers}: очередь нестабильна")
    return b / (1.0 - load / servers * (1.0 - b))


def _pos(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise QueueError(f"{name}: ожидается число, получено {value!r}")
    v = float(value)
    if not math.isfinite(v) or v <= 0:
        raise QueueError(f"{name}: ожидается конечное положительное, получено {value!r}")
    return v


def scenario(
    e_attack: float,
    e_legal: float,
    *,
    p_att: float,
    straight_to_queue: float,
    base_rho: float,
    operators: int,
    service_minutes: float,
    patience_minutes: float,
) -> dict[str, Any]:
    """Одна ячейка сценария: доли эскалаций (E_A, E_L) → аналитическое состояние очереди."""
    for v, name in ((e_attack, "E_A"), (e_legal, "E_L")):
        if not (math.isfinite(v) and 0 <= v <= 1):
            raise QueueError(f"{name}: доля в [0, 1], получено {v!r}")
    if not (math.isfinite(p_att) and 0 <= p_att <= 1):
        raise QueueError(f"p_att: доля в [0, 1], получено {p_att!r}")
    if not (math.isfinite(base_rho) and 0 <= base_rho < 1):
        raise QueueError(f"base_rho: в [0, 1), получено {base_rho!r}")
    if not (math.isfinite(straight_to_queue) and 0 < straight_to_queue < 1):
        raise QueueError(f"straight_to_queue: доля в (0, 1), получено {straight_to_queue!r}")
    s_min = _pos(service_minutes, "service_minutes")
    tau_min = _pos(patience_minutes, "patience_minutes")
    if operators < 1:
        raise QueueError(f"operators: ≥ 1, получено {operators!r}")

    esc_share = p_att * e_attack + (1.0 - p_att) * e_legal
    lam_humans = base_rho * operators * 60.0 / s_min  # поток «сразу в очередь», в час
    lam_ai = lam_humans * (1.0 - straight_to_queue) / straight_to_queue  # ИИ-канал
    lam_q = lam_ai * esc_share
    lam_total = lam_humans + lam_q
    load = lam_total * s_min / 60.0
    rho = load / operators
    stable = rho < 1.0 - 1e-9  # граница насыщения с допуском float-точности
    out = {
        "model_version": QUEUE_MODEL_VERSION,
        "esc_share": esc_share,
        "lambda_humans_per_hour": lam_humans,
        "lambda_ai_per_hour": lam_ai,
        "lambda_q_per_hour": lam_q,
        "lambda_total_per_hour": lam_total,
        "rho": rho,
        "stable": stable,
        "non_claims": list(NON_CLAIMS),
    }
    if not stable:
        out.update(P_wait=None, W_q_min=None, P_abandon=None, Q_L_min=None)
        return out
    p_wait = erlang_c(operators, load)
    drain = operators * 60.0 / s_min - lam_total  # дренаж очереди, в час
    w_q_min = p_wait * 60.0 / drain
    p_abandon = p_wait * math.exp(-drain * tau_min / 60.0)
    out.update(
        P_wait=p_wait,
        W_q_min=w_q_min,
        P_abandon=p_abandon,
        Q_L_min=e_legal * w_q_min,  # безусловная задержка на легального клиента
    )
    return out


def churn_member(
    e_legal: float,
    p_abandon: float | None,
    w_legal: float,
    *,
    stable: bool = True,
) -> float:
    """Безусловная вероятность потери легального клиента: w_L·E_L·P_abandon (без цены).

    Деньги применяет формулы (Prices.C_churn из пина) — так цена попадает под
    чувствительность ±×2 вместе с остальными ценами декомпозиции.
    """
    if not stable or p_abandon is None:
        return 0.0
    return w_legal * max(0.0, e_legal) * p_abandon
