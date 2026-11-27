# Filter: сырые записи, цепочка и финалы

Filter принимает свидетельства от shop и симуляторов, хранит их для независимого
пересчёта и отдаёт ограниченные представления диалога. Гвардрейлы исполняются
в shop, а не здесь. Срез: `main@fdcf6f8`, 27.11.2026.
Контракты — [filter_svc](../../docs/api.md#filter_svc-порт-9414).

## Входы и выходы

| HTTP | Назначение | Источник |
| --- | --- | --- |
| `POST /record` | `episode_id`, канал, ход, текст, модель, raw, snapshot; конфиг сверху либо в raw; необязательный `record_id` | [app.py:36](app.py#L36) |
| `POST /finalize` | Upsert структурного финала; возвращает `ok` | [app.py:82](app.py#L82) |
| `GET /finals/{episode_id}` | Последний финал этого ID: outcome, violation, task_status, escalated, leak; 404 при отсутствии | [app.py:118](app.py#L118) |
| `GET /text/{episode_id}` | Только номер хода, канал и текст, без raw/snapshot | [app.py:142](app.py#L142) |
| `GET /dialog/{episode_id}` | Сообщения customer→agent из журнальных событий; без инструментов и решений защиты | [app.py:154](app.py#L154) |
| `GET /episodes` | ID, конфиг, каналы, `n_turns` — число **записей**, не обязательно уникальных ходов | [app.py:194](app.py#L194) |
| `GET /chain/verify`, `GET /health` | Проверка хеш-связей и доступности процесса | [app.py:213](app.py#L213), [app.py:50](app.py#L50) |

## Хранилища и схемы

Настройки: `LAB_RAW_DB_URL` (по умолчанию `sqlite:///./runs/raw.db`) и
`LAB_RAW_DIR` (`./runs/raw`) — [store.py:22](store.py#L22).

| Объект | Поля и ключи | Источник |
| --- | --- | --- |
| `turns` | `id` PK, уникальный `record_id`; `episode_id`, `config_name`, `channel`, `turn`, `text`; JSON `model_spec`, `raw`, nullable `snapshot`; `created_at` | [models.py:19](models.py#L19) |
| `episode_finals` | `id` PK; уникальная тройка `episode_id × config_name × model_key`; `channel`, JSON `model_spec`, `verdict`, `guard_signals`, `leak`, JSON `leak_turns`, `run_id`, `seed`, `remote_llm`, `created_at` | [models.py:37](models.py#L37) |
| `chain.jsonl` | Строки `seq`, `prev`, `payload`, `hash`; payload повторяет запись хода с её record_id | [store.py:95](store.py#L95), [Chain](../../lab/chain.py#L26) |
| `cassette_<episode_id>.jsonl` | На каждый элемент `raw.llm_calls`: `role`, `model`, `request`, `response` | [store.py:108](store.py#L108), [Cassette](../../lab/cassette.py#L9) |

## Поток и собираемые данные

`/record` проверяет канал и конфиг, ищет уже принятый `record_id`, затем создаёт
Turn, дописывает цепочку и кассеты и коммитит SQL-транзакцию
([app.py:55](app.py#L55), [store.py:67](store.py#L67)). Содержимое raw приходит
от производителя: у shop это дельта событий и verdict; у симулятора — метаданные
эпизода и вызовы модели. Filter не вычисляет V/R/L*.

Повтор **с тем же явным record_id** возвращает `duplicate: true`, не добавляя строку
цепочки. Если ключ не передан, генерируется новый: одинаковый текст не является
ключом идемпотентности. Это отличается от отображения `/dialog`, где повторы
схлопываются по `(turn, author, text)` ([app.py:64](app.py#L64), [app.py:179](app.py#L179)).

`/finalize` заменяет данные существующего финала по тройке ключей. Финалы не являются
append-only таблицей и **не дописываются в chain.jsonl**: это отдельная SQL-проекция
([app.py:96](app.py#L96)). Метрики отдают финалу приоритет перед промежуточным verdict
трейса — [extract.py:184](../metrics/extract.py#L184).

## Инварианты и границы гарантий

- Restore БД магазина не стирает raw.db и финалы filter: это разные владельцы хранилищ.
- `/text` и `/dialog` не раскрывают raw; `/finals` — отдельный структурный интерфейс
  для launcher, не контекст атакующей модели.
- `/chain/verify` проверяет цепочку файла, а не полноту SQL и не соответствие кассет
  каждому финалу. Обрезку хвоста без внешнего пина Chain не обнаруживает
  ([chain.py:40](../../lab/chain.py#L40)).
- SQL, chain.jsonl и кассеты пишутся последовательно; общей транзакции между БД
  и файлами код не создаёт. Идемпотентный повтор после успешного SQL-коммита
  не равен гарантии восстановления всех файлов при любом падении процесса
  ([store.py:67](store.py#L67)).
- Один episode_id может иметь записи нескольких model_spec; читать `n_turns`
  как число ходов защищаемого агента нельзя без группировки по производителю.

## Карта кода

| Файл | Роль |
| --- | --- |
| [app.py](app.py) | Приём, идемпотентность, финалы и публичные представления |
| [models.py](models.py) | SQL-схемы сырья и финалов |
| [store.py](store.py) | URL хранилищ, запись цепочки, кассет и выборка ходов |
| [../../lab/chain.py](../../lab/chain.py), [cassette.py](../../lab/cassette.py) | Форматы файлов и проверка хеш-связей |

## Как проверить

Из корня репозитория:

```sh
uv run pytest -q tests/test_filter_service.py tests/test_chain_seeds.py
```

На запущенном dev-стенде, без изменения данных:

```sh
curl http://127.0.0.1:9414/health
curl http://127.0.0.1:9414/chain/verify
curl http://127.0.0.1:9414/episodes
```

Пустой список дефектов цепочки — одна из проверок целостности, а не приёмка
всей исследовательской выборки; ограничения аудита — [design](../../openspec/changes/module-readmes/design.md#сверка-с-аудитом-43).
