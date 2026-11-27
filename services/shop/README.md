# Магазин: состояние, защита и свидетельства эпизода

Магазин — измеряемая защищаемая система. Он принимает текст обеих ног пары,
исполняет действия через инструменты и сам строит ground truth и verdict.
Симуляторы не назначают себе исход. Срез описания: `main@fdcf6f8`, 27.11.2026.
Общий контекст — [архитектура](../../docs/architecture.md),
HTTP-контракты — [shop_svc](../../docs/api.md#shop_svc-порт-9411).

## Входы и выходы

| HTTP | Назначение и результат | Реализация |
| --- | --- | --- |
| `GET /health` | Доступность процесса, не проверка корректности эксперимента | [app.py:343](app.py#L343) |
| `POST /reset` | Проверяет seed, восстанавливает один мир `world_a`; возвращает `world`, `dataset_hash`, `db_version` | [app.py:348](app.py#L348) |
| `POST /configure` | Имя frozen-конфига и `agent_model` → применённая защита и её fingerprint | [app.py:391](app.py#L391) |
| `POST /turn` | `episode_id`, `channel`, `text`, `turn`; для attack нужен `goal`; также принимаются `run_id`, `seed` | [TurnRequest:322](app.py#L322) |
| Ответ `/turn` | Только `text`, `ended`, `session_status`; ни verdict, ни инструменты, ни снимок в ответ не включаются | [app.py:516](app.py#L516) |
| `POST /snapshot`, `GET /snapshot/{snapshot_id}` | Создание и проверенное чтение снимка состояния БД | [app.py:619](app.py#L619) |
| `POST /snapshot/restore` | Сначала доставляет накопленные записи и финалы, затем восстанавливает БД | [app.py:645](app.py#L645) |

`GET /db/readonly` отсутствует: URL БД задаётся окружением, а не выдаётся по HTTP.
Уточнения `/snapshot` и `/health`, отсутствующие в старом API-обзоре, приведены здесь
по обработчикам. У магазина нет публичного `/finalize`: он вызывает этот метод у filter.

## Конвейер одного хода

1. При первом `/turn` открывается тикет. Манифест мира связывает канал с клиентом,
   legal — с фиксированным возвратным заказом, attack — с заказом цели; фиктивный
   заказ даёт тикет без заказа. Затем строятся truth, исходное состояние и defender
   ([открытие эпизода](app.py#L196), [live_truth](evaluator/live.py#L149)).
2. Реплика клиента пишется в БД и журнал. `defender.respond` запускает агент,
   гвардрейлы, политику и исполнитель; ответ агента тоже фиксируется
   ([app.py:428](app.py#L428), [сборка защиты](configs/build.py)).
3. Из журнала выбираются события эпизода; `events[ep.sent_events:]` даёт **дельту хода**.
   `raw.guard_signals` — счётчики только этой дельты, а verdict и leak пересчитываются
   по всему состоянию/истории эпизода. Кумулятивные счётчики отдельно накапливаются
   в `Episode` ([app.py:470](app.py#L470), [сигналы и verdict](app.py#L523)).
4. Запись со стабильным `record_id`, raw и снимком ставится в outbox `/record`.
   При закрытии следом ставится `/finalize`; `_flush` отправляет очередь по порядку,
   до трёх попыток на элемент ([app.py:497](app.py#L497), [app.py:558](app.py#L558)).
5. `/turn` возвращает текст даже при неудаче доставки. Перед reset/restore `_drain`
   завершает также ноги, остановленные бюджетом, и требует пустой очереди;
   иначе отвечает 503 и сохраняет её для повтора ([app.py:585](app.py#L585)).

Outbox хранится **в памяти процесса**, в `Episode.outbox`, а не в отдельной надёжной БД.
Повтор доставки переживает потерю HTTP-ответа благодаря `record_id`; гарантии восстановления
очереди после аварийного завершения процесса здесь нет ([Episode:76](app.py#L76)).

## Хранилища и схемы

| Хранилище | Состав и жизненный цикл | Источник |
| --- | --- | --- |
| `LAB_SHOP_DB_URL`, по умолчанию `sqlite:///var/shop/shop.db` | Рабочая БД магазина | [settings](app.py#L57) |
| `meta`, `customers`, `orders`, `order_items`, `refund_policy`, `operators` | Мир, время, политика и исходные данные | [TABLES](db.py#L458), [загрузка CSV мира](db.py#L1136) |
| `tickets`, `ticket_messages` | Тикеты и текст диалога | [схема](db.py#L458) |
| `refund_requests`, `refusals`, `manual_reviews`, `info_requests`, `ops_ledger`, `payouts` | Следы операций и финансовых действий | [схема](db.py#L458) |
| `defect_evidence`, `refund_approvals`, `operator_decisions` | Доверенные доказательства и решения; обычный текст не превращает их в разрешение | [trusted-запись](db.py#L1543) |
| `LAB_SHOP_RUNTIME/journal-N.jsonl` | Новый номер после существующих файлов; непустой журнал не перезаписывается | [app.py:127](app.py#L127), [EventLog:143](journal/log.py#L143) |
| `baseline.snapshot.json`, `snapshots/<label>.json` в runtime | Снимки БД и её state hash; restore очищает runtime-эпизоды, но не raw.db filter | [reset](app.py#L374), [снимки](app.py#L619), [формат](db.py#L1641) |

Основные колонки таблиц ниже; суммы — целые центы, времена — текстовые UTC-метки.
PK — первичный ключ, FK — ссылка; точные CHECK/nullable ограничения находятся
в [DDL db.py:192](db.py#L192).

| Таблица | Колонки и существенные связи |
| --- | --- |
| `meta` | `key` PK, `value` |
| `customers` | `id` PK, `name`, уникальный синтетический `email`, `tier`, `created_at` |
| `orders` | `id` PK, `customer_id` FK, `placed_at`, `delivered_at`, `status`, `total_cents`, `note`, `note_provenance` |
| `order_items` | `id` PK, `order_id` FK, `sku`, `title`, `category`, `price_cents`, `qty`, `final_sale`, `reason_code` |
| `tickets` | `id` PK, `customer_id`/`order_id` FK, `status`, `opened_at`, `clarifications`, `closed_at` |
| `ticket_messages` | `id` PK, `ticket_id` FK, `seq`, `author`, `provenance`, `body`, `created_at`; уникален ticket×seq |
| `refund_policy` | `rule_id` PK, `version`, `text`, `params_json` |
| `refund_requests` | `id` PK, `ticket_id`/`order_item_id`/`customer_id` FK, `amount_cents`, `reason_code`, `status`, `created_by`, `created_at`; order_item_id уникален |
| `refusals` | `id` PK, `ticket_id` FK, `reason_code`, `created_at` |
| `manual_reviews` | `id` PK, уникальный `ticket_id` FK, `reason_code`, `enqueued_at`, `decided_at`, `decision`, `decided_by` |
| `info_requests` | `id` PK, `ticket_id` FK, `question_code`, `question_text`, `created_at` |
| `ops_ledger` | `op_key` PK, `ticket_id` FK, `kind`, `created_at`, `detail_json` |
| `defect_evidence` | `id` PK, `order_item_id` FK, `status`, `recorded_by`, `note`, `created_at` |
| `refund_approvals` | `id` PK, `order_item_id` FK, `max_amount_cents`, `approved_by`, `created_at` |
| `operators` | `id` PK, `display_name`, `active` |
| `operator_decisions` | `id` PK, `ticket_id`/`operator_id`/`order_item_id`/`refund_request_id` FK, `decision`, `amount_cents`, `defect_verified`, `reason_code`, `idempotency_key`, `request_hash`, `response_json`, `created_at`; ticket_id и idempotency_key уникальны |
| `payouts` | `id` PK, уникальный `refund_request_id` FK, уникальный `idempotency_key`, `charge_id`, `amount_cents`, `state`, `emu_refund_id`, `attempts`, `last_error`, `updated_at` |

Журнал события содержит `run_id`, `episode_id`, `traffic`, `component`, `side`, `kind`,
`t_sim`, `data`, `cost`, `wall_ms`, `seq`, `prev`, `h`. Дисковая оболочка `Chain` содержит
`seq`, `prev`, `payload`, `hash`; это отдельный уровень от `chain.jsonl` filter
([EventLog._append](journal/log.py#L182), [Chain](../../lab/chain.py#L26)).

## Собираемые поля и исходы

| Поле | Семантика | Источник |
| --- | --- | --- |
| `raw.events`, `raw.guard_signals`, `raw.llm_calls` | Дельта событий, сигналы дельты и пары вызов→ответ; это сырьё для post-hoc расчёта | [app.py:481](app.py#L481) |
| `raw.verdict` | Кумулятивные `violation`, `violations`, `outcome`, `task_status`, `escalated`, `version`; при `EvaluationError` — объект `error` | [app.py:532](app.py#L532) |
| `ticket_id`, `customer_id`, `model_spec`, `config_name` | Контекст и пины защищаемой системы | [app.py:481](app.py#L481) |
| `run_id`, `seed`, `remote_llm` | Метаданные, если они переданы; shop маркирует remote агента по его endpoint | [app.py:480](app.py#L480) |
| Финал `/finalize` | Verdict, **кумулятивные** guard_signals, leak/leak_turns, модель, канал, конфиг, run/seed/remote | [app.py:558](app.py#L558) |

Truth строится внутри магазина из мира и фактической БД. Evaluator сравнивает исходное
и текущее состояние; лексика ответа «refund completed» сама по себе не доказывает
исполненный возврат ([live.py:149](evaluator/live.py#L149), [evaluator.py](evaluator/evaluator.py)).
Канарейка задаётся `LAB_PROMPT_CANARY` либо синтетически при reset; её появление
в ответе — отдельный `leak`, не дополнительное значение outcome
([app.py:361](app.py#L361), [app.py:549](app.py#L549)).

## Инварианты и ограничения

- Барьер «только текст» соблюдается в ответе `/turn`; сырьё направляется сразу filter.
- Seed не меняет замороженный мир; роли находятся в файловом манифесте, не в БД
  ([reset](app.py#L348), [lab/world.py](../../lab/world.py#L42)).
- Финалы filter переживают restore магазина. Закрытие сессии и структурный verdict — разные вещи.
- По [I43-02](https://github.com/CloudNative-urfu/dvarp-lab/issues/43#issuecomment-7211830344)
  при configure проверяется наличие frozen-файла, но не его SHA256 по lock;
  это видно в [app.py:391](app.py#L391) и [nominal.py:47](../../lab/nominal.py#L47).
  Наличие `configs.lock.json` не означает автоматический контроль drift при запуске.
- `run_id`/`seed` принимаются shop, но текущие симуляторы их в `/turn` не передают;
  ограничение I43-06 описано в [сверке аудита](../../openspec/changes/module-readmes/design.md#сверка-с-аудитом-43)
  и видно в [извлечении seed-групп](../metrics/app.py#L201).

## Карта кода

| Путь | Роль |
| --- | --- |
| [app.py](app.py) | HTTP, эпизоды, журнал, outbox, финализация и snapshot/restore |
| [db.py](db.py) | Таблицы, загрузка одного мира, синтетические данные, снимки |
| [guards/](guards/), [configs/](configs/) | Контракты плагинов, политика, executor, инструменты и сборка защиты |
| [agent/](agent/), [llm/](llm/) | Агент и stub/live-модели с лимитами и учётом использования |
| [journal/](journal/) | Схема событий, append-only журнал и затраты |
| [evaluator/](evaluator/) | Truth, доказательства и структурная оценка состояния |
| [channel/](channel/), [corpus/](corpus/), [manual_queue/](manual_queue/) | Внутренний канал, привязка корпуса и модели ручной очереди; расчёт кампании — в metrics |

## Как проверить

Команды из корня репозитория; тесты используют изолированные данные:

```sh
uv run pytest -q tests/test_shop_service.py tests/test_world.py tests/test_evaluator.py
uv run pytest -q tests/test_filter_service.py tests/test_remote_llm.py
```

Проверяются reset/restore, truth и финалы, доставка, барьер и пины. Полная сверка
с аудитом — [план change](../../openspec/changes/module-readmes/design.md#сверка-с-аудитом-43).
