# dvarp-lab

Полигон проверки гипотез исследования (статья): СС «магазин возвратов» с защитой,
легальный трафик, атака, сбор сырых данных, метрики — пять сервисов + запускатель.

Принципы: `docs/architecture.md`; мануал агента: `docs/agent-manual.md`; схема полигона: `docs/scheme.svg`.

Ключевые принципы:

- **сбор ≠ расчёт**: в прогоне только собираются сырые данные; метрики считаются
  когда угодно отдельным сервисом поверх сохранённого;
- замороженные характеристики: конфигурации защиты, выбор LLM, корпус атак,
  стили общения, набор гвардрейлов;
- каждый прогон пинит `model_spec` во всех хранилищах;
- seeds — для детерминированных частей; живая модель недетерминирована, реален трейс;
- внутренний журнал — хеш-цепочка; кассеты запросов к моделям — по строке на пару
  запрос→ответ;
- сеть: без охраны; номинальная проверка конфигурации перед каждым прогоном
  (гвардрейлы соответствуют замороженным, не-локальные LLM-эндпоинты маркируются remote и не идут в метрики статьи).

## Быстрый старт

```sh
uv sync
uv run python scripts/dev.py            # все 6 сервисов + консоль: http://127.0.0.1:9410
# (или по одному: uvicorn services.shop.app:app --port 9411 и т.д.)
uv run python -m launcher --config g0 --episodes 2    # CLI: та же кампания
```

Тесты: `uv run pytest`.

## Карта репозитория

### Верхний уровень

| Путь | Что здесь искать |
| --- | --- |
| [`lab/`](lab) | Общая мини-библиотека: хеш-цепочка (`chain.py`), кассеты вызовов моделей (`cassette.py`), `model_spec` и ростер (`modelspec.py`), номинальная проверка (`nominal.py`), работа с БД, сидами и клиентами сервисов. |
| [`services/shop/`](services/shop) | Магазин возвратов: состояние БД, агент, защита, инструменты, журнал и оценка результата. Подробная навигация — ниже. |
| [`services/traffic/`](services/traffic) | Генерация легальных обращений и запуск легальных эпизодов. |
| [`services/attack/`](services/attack) | Атакующий агент, тактики и запуск атакующих эпизодов. |
| [`services/filter/`](services/filter) | Сбор и хранение сырых данных прогонов. Конфиги гвардрейлов ищите в `frozen/configs/`, реализацию — в `services/shop/guards/`. |
| [`services/metrics/`](services/metrics) | Извлечение данных и расчёт метрик поверх сохранённых результатов. |
| [`services/ui/`](services/ui) | Веб-консоль: сервер и статические файлы интерфейса (Vue вендорится в `static/vendor/`); описания осей, пресетов и терминов — данными в `describe.py`, фронт только рисует. |
| [`launcher/`](launcher) | CLI, оси кампании и перебор сочетаний модели, конфигурации и сценария; сохранение манифестов. |
| [`frozen/`](frozen) | Замороженные характеристики экспериментов: конфиги защиты, модели, корпус атак и стили общения. |
| [`scripts/`](scripts) | `dev.py` запускает шесть сервисов; `smoke.py` выполняет сквозную проверку. |
| [`openspec/`](openspec) | Контекст проекта в `config.yaml`, предложения, дизайн, задачи и дельты спецификаций в `changes/`. |
| [`tests/`](tests) | Тесты сервисов, защиты, моделей, кампаний и метрик. |
| [`docs/`](docs) | Архитектура, API, инварианты исследования, схема и происхождение реализации. |
| [`canon-requests/`](canon-requests) | Заявки на изменение канона исследования: ожидающие и принятые. |
| [`.env.example`](.env.example) | Публичный шаблон настроек сервисов и хранилищ; назначения переменных — ниже. |
| [`pyproject.toml`](pyproject.toml), [`uv.lock`](uv.lock) | Зависимости, настройки Python-проекта и закреплённые версии. |

### Внутри магазина

Все пути в этой таблице относятся к `services/shop/`.

| Путь | Что здесь искать |
| --- | --- |
| [`db.py`](services/shop/db.py) | Реализация БД магазина; путь к рабочей БД задаёт `LAB_SHOP_DB_URL`. |
| [`seed/catalog.csv`](services/shop/seed/catalog.csv) | CSV-каталог товаров для начального наполнения магазина. |
| [`seed/benign_notes.csv`](services/shop/seed/benign_notes.csv) | Безвредные заметки для начального наполнения. |
| [`guards/contract/`](services/shop/guards/contract) | Контракт, типы, контекст, хост и реестр плагинов защиты. |
| [`guards/plugins/`](services/shop/guards/plugins) | Реализации правил и адаптеров гвардрейлов, включая OSS DeBERTa. |
| [`guards/policy/`](services/shop/guards/policy) | Политика защиты и конвейер её применения. |
| [`guards/boundary.py`](services/shop/guards/boundary.py), [`guards/boundary_contract.py`](services/shop/guards/boundary_contract.py) | Граница исполнения и её контракт. |
| [`guards/executor.py`](services/shop/guards/executor.py) | Исполнитель действий агента. |
| [`guards/tools/`](services/shop/guards/tools) | Спецификации и реализация доступных инструментов. |
| [`agent/`](services/shop/agent) | Агент магазина: фабрика, профили, промпт, проверки утверждений и stub. |
| [`agent_demo/`](services/shop/agent_demo) | Демонстрационный запуск агента и набор легальных сценариев. |
| [`llm/`](services/shop/llm) | Клиенты и бэкенды моделей, настройки, лимиты и учёт использования. |
| [`journal/`](services/shop/journal) | Внутренний журнал магазина, схема событий и учёт затрат. |
| [`channel/`](services/shop/channel) | Текстовый канал, его эндпоинты и типы сообщений, реализации пользователя. |
| [`configs/`](services/shop/configs) | Сборка конфигураций, их спецификация и реестр. Готовые замороженные JSON находятся в `frozen/configs/`. |
| [`corpus/`](services/shop/corpus) | Схема, загрузка и привязка элементов корпуса к сценарию; сами наборы атак — в `frozen/corpus/`. |
| [`evaluator/`](services/shop/evaluator) | Определение исхода по состоянию и свидетельствам, включая проверку утечки промпта. |
| [`manual_queue/`](services/shop/manual_queue) | Модель ручной очереди, потока поступлений и аналитический расчёт. |

### Замороженные характеристики

[`frozen/`](frozen) содержит характеристики,
которые меняются редко и осознанно: их изменение меняет условия сравнения прогонов.

| Путь | Содержимое |
| --- | --- |
| [`frozen/configs/`](frozen/configs) | Базовые линии `g0`, `g_proc`; конфигурации `g_in`, `g_out`, `g_tool`, `g_ctx`, `g_layered`; варианты `_iso`, `_term`, абляции `g_layered_minus_*`, а также отдельные seed/detect-only/OSS-варианты. |
| [`frozen/configs/configs.lock.json`](frozen/configs/configs.lock.json) | Lock-файл набора конфигураций для проверки заморозки. |
| [`frozen/llm.json`](frozen/llm.json) | Ростер моделей и их закреплённые характеристики. Новые модели добавляются осознанным изменением заморозки. |
| [`frozen/corpus/darp_corpus_v2.jsonl`](frozen/corpus/darp_corpus_v2.jsonl), [`darp_corpus_v2_ext.jsonl`](frozen/corpus/darp_corpus_v2_ext.jsonl) | Основной и дополнительный наборы корпуса атак. |
| [`frozen/corpus/MANIFEST.json`](frozen/corpus/MANIFEST.json), [`MANIFEST_ext.json`](frozen/corpus/MANIFEST_ext.json) | Манифесты соответствующих наборов корпуса. |
| [`frozen/corpus/tactics.json`](frozen/corpus/tactics.json) | Каталог тактик атак. |
| [`frozen/styles.json`](frozen/styles.json) | Зафиксированные стили общения. |

### Данные прогонов

Эти файлы создаются при работе стенда. Пути ниже — значения по умолчанию для отдельных сервисов;
`scripts/dev.py` использует отдельное дерево `runs/dev/`.

| Путь / настройка | Что хранится и где искать реализацию |
| --- | --- |
| `runs/<run_id>/manifest.json` — `LAB_RUNS_DIR` | Манифест кампании: оси, модели, конфигурации и результаты эпизодов. Записывает [`launcher/campaign.py`](launcher/campaign.py). |
| `runs/raw.db` — `LAB_RAW_DB_URL` | Сырая БД: записывает filter, читает metrics. Реализация — [`services/filter/`](services/filter). |
| `runs/raw/` — `LAB_RAW_DIR` | Каталог JSONL-хеш-цепочки (`chain.jsonl`) и кассет вызовов моделей (`cassette_<episode_id>.jsonl`). Пути задаёт [`services/filter/store.py`](services/filter/store.py). Форматы — [`lab/chain.py`](lab/chain.py) и [`lab/cassette.py`](lab/cassette.py). |
| `runs/metrics.db` — `LAB_METRICS_DB_URL` | БД рассчитанных метрик; код — [`services/metrics/`](services/metrics). |
| `var/shop/shop.db`, `var/shop/` — `LAB_SHOP_DB_URL`, `LAB_SHOP_RUNTIME` | Рабочее состояние магазина и runtime-файлы: журналы, снапшоты. |
| `runs/dev/` | Данные [`scripts/dev.py`](scripts/dev.py): `shop.db`, `raw.db`, `metrics.db`, `shop_runtime/`, `raw/`, `runs/<run_id>/manifest.json`. Каталог можно изменить через `--tmp`. |

### Настройки окружения

Отправная точка — [`.env.example`](.env.example).
`dev.py` сам читает `.env` в корне репозитория; уже заданные переменные процесса имеют приоритет
при чтении файла. Затем dev-запуск задаёт собственные пути БД, runtime и манифестов, а также
`LAB_SHOP_URL` и `LAB_FILTER_URL`. Для ручного запуска сервисов и launcher окружение задаётся отдельно.
Ключи передавайте только через env процесса: их значения не должны попадать в README, Git,
журналы, кассеты или манифесты.

| Переменная | Значение из шаблона / назначение |
| --- | --- |
| `LAB_SHOP_URL` | `http://127.0.0.1:9411` — API магазина. |
| `LAB_TRAFFIC_URL` | `http://127.0.0.1:9412` — API легального трафика. |
| `LAB_ATTACK_URL` | `http://127.0.0.1:9413` — API атакующего сервиса. |
| `LAB_FILTER_URL` | `http://127.0.0.1:9414` — API сборщика сырых данных. |
| `LAB_METRICS_URL` | `http://127.0.0.1:9415` — API расчёта метрик. |
| `LAB_SHOP_DB_URL` | `sqlite:///var/shop/shop.db` — подключение к БД магазина; traffic_svc читает его же, по HTTP строка не отдаётся. |
| `LAB_SHOP_RUNTIME` | `var/shop` — каталог runtime-файлов магазина. |
| `LAB_RAW_DB_URL` | `sqlite:///./runs/raw.db` — подключение к сырой БД. |
| `LAB_RAW_DIR` | `./runs/raw` — каталог цепочки событий и кассет. |
| `LAB_METRICS_DB_URL` | `sqlite:///./runs/metrics.db` — подключение к БД метрик. |
| `LAB_RUNS_DIR` | `runs` — корень каталогов манифестов кампаний. |

Консоль UI при dev-запуске доступна на `http://127.0.0.1:9410`; отдельной переменной URL для неё
в шаблоне нет. Для SQLite используется форма `sqlite:///<путь>/<файл>.db`, для PostgreSQL —
`postgresql+asyncpg://<user>:<pass>@127.0.0.1:5432/<db>`.

В секции Live-LLM шаблона настройки закомментированы. Без настройки живой модели используется
stub-режим. Ростер `frozen/llm.json` — справочник заморозки для статьи, а не гейт: имена моделей
вне ростера допускаются с пином `remote-verification`. Любой http(s)-эндпоинт принимается без
флагов; не-локальный прогон маркируется remote автоматически (инвариант 8c) и не идёт в метрики
статьи — их включают явно галочкой `include_remote` при пересчёте. Флаги `allow_remote_llm` /
`LAB_ALLOW_REMOTE_LLM` устарели: принимаются и игнорируются.

| Переменная | Назначение |
| --- | --- |
| `LAB_CUSTOMER_LLM_BASE_URL` | Базовый URL OpenAI-совместимого API модели легального пользователя. |
| `LAB_CUSTOMER_LLM_MODEL` | Имя модели легального пользователя у провайдера. |
| `LAB_CUSTOMER_LLM_API_KEY` | Ключ модели легального пользователя; только env процесса. |
| `LAB_ATTACKER_LLM_BASE_URL` | Базовый URL API модели атакующего. |
| `LAB_ATTACKER_LLM_MODEL` | Имя модели атакующего у провайдера. |
| `LAB_ATTACKER_LLM_API_KEY` | Ключ модели атакующего; только env процесса. |
| `LAB_AGENT_LLM_BASE_URL` | Упомянут в шаблоне, но текущий код его не читает. Для shop-агента задавайте `RESEARCH_LLM_BASE_URL`. |
| `RESEARCH_LLM_BASE_URL` | Базовый URL API модели shop-агента. |
| `RESEARCH_LLM_MODEL` | Закреплённое имя модели shop-агента. |
| `RESEARCH_LLM_API_KEY` | Ключ модели shop-агента; только env процесса. |

Устаревшие флаги `allow_remote_llm` (оси кампании/CLI) и `LAB_ALLOW_REMOTE_LLM` (env)
из шаблона удалены: принимаются и игнорируются, маркировка remote — автоматическая.

Дополнительно [`services/shop/llm/settings.py`](services/shop/llm/settings.py)
поддерживает настройки, не перечисленные в шаблоне:

| Переменная | Назначение |
| --- | --- |
| `RESEARCH_LLM_PARAMS_B` | Размер shop-модели в миллиардах параметров; нужен явно, если размер нельзя определить по имени. |
| `RESEARCH_LLM_EXTRA_BODY` | JSON-объект дополнительных полей запроса к модели; закреплённые поля генерации переопределять нельзя. |

### Читать дальше

| Документ | Когда открывать |
| --- | --- |
| [`docs/architecture.md`](docs/architecture.md) | Чтобы понять компоненты и потоки данных. |
| [`docs/api.md`](docs/api.md) | Для контрактов эндпоинтов и формата осей кампании. |
| [`docs/agent-manual.md`](docs/agent-manual.md) | Для критических инвариантов, ограничений и правил исследования. |
| [`docs/scheme.svg`](docs/scheme.svg) | Для визуальной схемы полигона. |
| [`openspec/`](openspec) | Для истории предложений и спецификаций изменений. |
