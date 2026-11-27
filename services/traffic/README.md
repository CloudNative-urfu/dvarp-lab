# Traffic: легальная нога пары

Сервис воспроизводит правдивое обращение клиента к защищаемому магазину. Заказ
фиксирован в манифесте мира; меняется тон, а не законность претензии. Срез:
`main@fdcf6f8`, 27.11.2026. [HTTP-контракт](../../docs/api.md#traffic_svc-порт-9412).

## Входы и выходы

`POST /run-episode` принимает `episode_id`, `config_name`, `agent_model`, `style`,
`seed`, необязательные `group_seed`, `run_id`, `remote_llm`. Возвращает `outcome`,
`turns`, `transcript_ids`. `GET /health` проверяет процесс
([app.py:21](app.py#L21), [episode.py:59](episode.py#L59)).

На каждом ходе вызывается shop `/turn` с `channel=legal`; сервис читает только
`text` и `ended`. Цикл заканчивается `session_closed` либо `turn_limit` после
12 ходов. Это причина остановки, **не** структурный исход возврата. Launcher
забирает окончательный outcome из filter после restore
([episode.py:109](episode.py#L109), [campaign.py:249](../../launcher/campaign.py#L249)).

## Данные и хранилища

| Источник / выход | Состав и назначение | Код |
| --- | --- | --- |
| `LAB_SHOP_DB_URL` | Общая с shop БД; URL обязателен в env, по HTTP его не запрашивают | [app.py:58](app.py#L58) |
| `world_a/manifest.json` → legal_case | Фиксированные customer/order/item; случайного выбора заказа по seed нет | [episode.py:80](episode.py#L80), [case.py:51](case.py#L51) |
| Таблицы магазина | SELECT order_items/orders/refund_requests/meta; товар, сумма, количество, доставка, reason_code берутся из БД | [case.py:51](case.py#L51) |
| `frozen/styles.json` | Роль, описания, openings; optional confirm/answers/push → нейтральные банки | [style.py](style.py) |
| Filter `/record` | Recorder пишет ответы агента и `llm_calls`; `snapshot={}`, а полноценные снимки пишет shop | [record.py:15](record.py#L15) |

Собственной SQL-схемы у traffic нет. Контракт — чтение БД без записей; в case.py
выполняются SELECT, но URI `mode=ro`, как у metrics, здесь явно не устанавливается.
Это ограничение реализации прав доступа, а не разрешение писать в магазин.

## Как рождается реплика и сырьё

Stub выбирает opening от производного seed и рендерит факты кейса; дальше
подтверждает, отвечает фактами или берёт push. При отсутствии банков используется
нейтральный набор ([style.py](style.py), [case.render](case.py#L89)).
В live-режиме opening тоже шаблонный; последующие реплики генерируются по истории,
общей тон-клаузе и фактам. Они не должны выдумывать заказы или менять цель
([episode.py:23](episode.py#L23)).

Каждый `ChatModel.reply` добавляет в Recorder `role`, `model`, `request`, `response`.
`flush` отправляет весь буфер и очищает его **после успешного HTTP-вызова**.
Ключ идемпотентности record_id заранее Recorder не назначает; outbox shop и этот
Recorder — разные механизмы ([record.py:27](record.py#L27), [record.py:76](record.py#L76)).

`raw_extra` содержит `config_name`, `style`, `seed` (group_seed, если задан),
необязательные `run_id`/`remote_llm`. Модель в записи — переданный `agent_model`,
тогда как `llm_calls.role=customer`: роль вызова и пин группы различаются
([episode.py:87](episode.py#L87), [record.py:27](record.py#L27)).
Ключ API участвует только в HTTP-заголовке модели, не в кассетном request
([record.py:82](record.py#L82)).

## Инварианты и ограничения

- Стиль legal совпадает со стилем attack ячейки; сами реплики двух ног не обязаны совпадать.
- Truth/verdict строит shop. Traffic не вычисляет V/R/E/L* и не объявляет текст успешным возвратом.
- Remote-маркировка объединяет входной флаг с проверкой endpoint customer;
  loopback отличается от удалённого адреса ([episode.py:85](episode.py#L85)).
- Seed — детерминизм stub, не гарантия повторения живой LLM; group_seed — метка
  группы кампании, а не отдельный мир.
- Сейчас `/turn` не получает run_id/seed от traffic: собственная запись их имеет,
  но метаданные shop могут быть неполными (I43-06; [episode.py:112](episode.py#L112)).

## Карта кода

| Файл | Роль |
| --- | --- |
| [app.py](app.py) | HTTP, URL сервисов и обязательный URL БД |
| [case.py](case.py) | Правдивый фиксированный кейс и подстановка фактов |
| [style.py](style.py) | Общий с attack реестр, тон-клауза и stub-фолбэки |
| [episode.py](episode.py) | Цикл legal и LLM-клиент с историей |
| [record.py](record.py) | Общие с attack Recorder и OpenAI-совместимый транспорт |

## Как проверить

Из корня; живые модели заменены транспортом тестов:

```sh
uv run pytest -q tests/test_traffic.py tests/test_shared_styles.py tests/test_remote_llm.py
```

На работающем стеке `GET http://127.0.0.1:9412/health` проверяет процесс;
для полного опыта используйте одну [кампанию](../../docs/api.md#launcher-cli--модуль-кампании), чтобы
reset/configure/snapshot/restore и финалы выполнялись в правильном порядке.
