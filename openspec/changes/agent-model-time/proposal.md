## Why

Issue: https://github.com/CloudNative-urfu/dvarp-lab/issues/65.

Live-агент не знает модельное время: `read_order` отдаёт сырые timestamps,
промпт дату не называет. На forgetful-режиме (#56) агент правильно прочитал
`delivered_at = 2026-11-27`, но, не зная `meta.now = 2026-12-01`, выдал
«more than 30 days ago» → unjustified_refusal на честного клиента; на
`g_layered_term` сам арифметил дату из слов клиента → кривой tool-аргумент →
`tool-arg-validator flag → terminate` → G-τ-ложное прерывание. Stub-агент
не страдает (`stub.py:416` считает от `ticket.opened_at`).

Модельное время — такие же доверенные данные мира, как правила (FR-1.10):
агент обязан получать его из инструмента, а не угадывать.

## What Changes

- `_op_read_ticket` возвращает `model_time` (значение `meta.now`, executor
  уже его читает); FR-1.11 «ровно 5 инструментов» не ломается — это поле
  ответа, не шестой инструмент;
- промпт: строка в п.1 — «`read_ticket` returns `model_time`, the shop's
  current date: use it for all date arithmetic; never guess today's date» →
  `PROMPT_VERSION = "refund-agent-prompt-6"` (осознанный bump заморозки);
- тест: `read_ticket.model_time == meta.now` мира; остальной ответ
  `read_ticket` не изменён; `read_order` не расширен.

## Capabilities

### New Capabilities
- `agent-model-time`: модельное время в ответе `read_ticket` и опора промпта.

## Impact

- Ответ `read_ticket` получает поле — fragments_from_read не затронут
  (untrusted-контекст остаётся только в `messages`); evaluator/симуляторы
  не меняются (их время уже консистентно с `meta.now`).
