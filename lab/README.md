# Lab: общие примитивы полигона

Это библиотека, а не HTTP-сервис. Она задаёт общий формат пинов, seed, файлов
свидетельств и доступ к манифесту мира. Срез: `main@fdcf6f8`, 27.11.2026.
Взаимодействия сервисов — [API](../docs/api.md), владельцы данных —
[shop](../services/shop/README.md), [filter](../services/filter/README.md).

## Входы и выходы

| Примитив | Вход → выход | Реализация |
| --- | --- | --- |
| `ModelSpec` | name, role, params_b, revision → JSON-пин | [modelspec.py:13](modelspec.py#L13) |
| `load_roster`, `resolve` | frozen/llm.json и имя → закреплённая модель; resolve неизвестного имени выбрасывает KeyError | [modelspec.py:24](modelspec.py#L24) |
| `check_config` | Имя конфига → список замечаний о наличии frozen-файла | [nominal.py:47](nominal.py#L47) |
| `is_local_url`, `remote_endpoints` | URL/окружение → loopback-признак / список имён remote-переменных | [nominal.py:26](nominal.py#L26) |
| `derive_seed` | Базовый seed и последовательность частей → SHA256-производный int `<2**31` | [seeds.py:8](seeds.py#L8) |
| `load_manifest`, `load_goals`, `goal_binding`, `claim_facts`, `render_claim` | Frozen-файлы → проверенный мир, цели и фиксированная претензия | [world.py:42](world.py#L42), [world.py:139](world.py#L139) |
| `Chain` | JSON payload → append-only строка; verify → список дефектов | [chain.py:26](chain.py#L26) |
| `Cassette` | role, model, request, response → JSONL-строка вызова | [cassette.py:9](cassette.py#L9) |
| `make_engine`, `is_postgres` | URL → SQLAlchemy engine, определение диалекта | [db.py:11](db.py#L11) |
| `Svc.get/post` | base URL + путь/JSON → HTTP-запрос, raise_for_status, decoded JSON | [svc_client.py:8](svc_client.py#L8) |

## Данные и схемы

Lab не создаёт собственных SQL-таблиц. `modelspec.py` читает ростер, `world.py` —
манифесты и цели, а пути файлов Chain/Cassette выбирает вызывающий модуль.
Формат цепочки: `seq`, `prev`, `payload`, `hash`; GENESIS — 64 нуля, seq начинается
с 1. Хеш — SHA256 канонического JSON из seq/prev/payload
([chain.py:10](chain.py#L10)). Кассета хранит `role`, `model`, `request`, `response`;
сама не содержит цепочки хешей ([cassette.py:13](cassette.py#L13)).

Манифест мира содержит клиентов и роли, orders facts, legal_case, fictive_order и
замороженное now. Проверяются schema, ссылки, соответствие клиента заказам,
фиктивность отдельного заказа и состав фактов. CSV→БД и dataset_hash реализованы
в shop, не в lab ([world.py:42](world.py#L42), [shop.db:1136](../services/shop/db.py#L1136)).

## Что именно пинится и зависит от seed

ModelSpec — пин **описания** модели, а не копия весов и не подтверждение, что
удалённый endpoint действительно обслуживает нужную ревизию. Launcher допускает
имя вне ростера отдельной обёрткой `_model_spec`; строгий lab.resolve этого не делает
([campaign.py:58](../launcher/campaign.py#L58)).

`lab.seeds.derive_seed` используется для раскладки реплик и ячеек. Он не меняет
мир магазина и не обещает воспроизводимость LLM. В shop есть другой,
63-битный `repro.derive_seed` и `check_seed`: их нельзя считать тем же алгоритмом
([seeds.py:8](seeds.py#L8), [shop.repro:91](../services/shop/repro.py#L91)).

## Инварианты и ограничения

- Loopback — `127.0.0.0/8`, `::1`, localhost и `.localhost`; частная сеть сама по себе
  не local. Проверяются endpoints агента/customer/attacker/guard. Наружу возвращаются
  только имена переменных, а не их значения ([nominal.py:18](nominal.py#L18)).
- check_config не проверяет соответствие config-объекта lock-файлу; agents и
  allow_remote приняты для совместимости, но не гейтят. I43-02 остаётся открытым
  ограничением ([nominal.py:47](nominal.py#L47)).
- Chain выявляет изменение содержимого и внутренних связей, но без внешнего
  пина не обнаруживает удаление хвоста. Дописывание не является межпроцессной
  транзакцией или блокировкой нескольких писателей ([chain.py:32](chain.py#L32)).
- Svc — тонкий клиент с таймаутом, без собственной очереди надёжной доставки;
  outbox реализует shop ([svc_client.py:8](svc_client.py#L8)).
- Фабрика db не задаёт read-only автоматически; ограничения чтения принадлежат
  сервису-потребителю. PostgreSQL-read-only finding относится к metrics, не к Svc.

## Карта кода

Файлы в таблице входов одновременно образуют карту модуля: `modelspec` — пины,
`nominal` — проверка/remote, `seeds` — производные seed, `world` — факты мира,
`chain/cassette` — файловые свидетельства, `db` — engine, `svc_client` — HTTP.
Бизнес-правила возвратов и формулы метрик сюда не перенесены.

## Как проверить

Из корня, без реальных моделей:

```sh
uv run pytest -q tests/test_chain_seeds.py tests/test_nominal.py tests/test_world.py
uv run pytest -q tests/test_remote_llm.py tests/test_reference_endpoints.py
```

У этих тестов разные предметы: целостность цепочки не доказывает правильные
знаменатели метрик, а корректный ModelSpec не доказывает качество модели.
