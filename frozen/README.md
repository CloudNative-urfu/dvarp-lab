# Frozen: характеристики, которые фиксируют эксперимент

Здесь лежат данные, определяющие условия сравнения. Их меняют осознанно вместе
с issue, спецификацией и проверками; изменение JSON без изменения кода тоже может
изменить эксперимент. Срез: `main@fdcf6f8`, 27.11.2026.
[Архитектура](../docs/architecture.md#замороженные-характеристики-frozen),
[API применения конфигурации](../docs/api.md#shop_svc-порт-9411).

## Входы, потребители и карта файлов

HTTP-интерфейса у каталога нет. Файлы читают shop, симуляторы, launcher и metrics.

| Путь | Содержимое и потребитель | Привязка к коду |
| --- | --- | --- |
| [configs/](configs/), [configs.lock.json](configs/configs.lock.json) | 27 конфигов: базовые линии, позиции защиты, iso/term/minus-контроли и input LLM-детекторы; lock содержит file/SHA256/fingerprint/family/role/control_of | [shop.configure](../services/shop/app.py#L391), [registry](../services/shop/configs/registry.py#L53) |
| [llm.json](llm.json) | Ростер name/role/params_b/revision; на срезе два placeholder-пина, не доказательство наличия живых endpoint | [modelspec.py:13](../lab/modelspec.py#L13) |
| [seed_worlds/world_a/](seed_worlds/world_a/) | CSV customers/orders/order_items/refund_history и manifest: один клиент A с 9 заказами; роли и legal_case находятся в manifest, не в SQL | [world.load_manifest](../lab/world.py#L42), [shop.load_world](../services/shop/db.py#L1136) |
| [corpus/goals.json](corpus/goals.json) | 7 целей: вектор преувеличения, заказ реальный/фиктивный, шаблон claim | [world.load_goals](../lab/world.py#L139) |
| [corpus/tactics.json](corpus/tactics.json) | 70 методов, schema `dvarp.tactics/2`: description, совместимые цели и illustrations; обязательных диалогов нет | [attack.tactics](../services/attack/tactics.py#L20) |
| [corpus/darp_corpus_v2.jsonl](corpus/darp_corpus_v2.jsonl), [ext](corpus/darp_corpus_v2_ext.jsonl), [v3](corpus/darp_corpus_v3.jsonl) | Корпусные записи и исходные иллюстрации, связанные с методами | [MANIFEST](corpus/MANIFEST.json), [MANIFEST_ext](corpus/MANIFEST_ext.json), [MANIFEST_v3](corpus/MANIFEST_v3.json) |
| [styles.json](styles.json) | Общие 23 роли обеих ног: name, description, openings; банки stub optional | [traffic.style](../services/traffic/style.py) |
| [economics.json](economics.json) | Тарифы агента/гвардов за миллион токенов, C_human/C_churn, сценарии p_att и очереди, множители чувствительности | [metrics.economics](../services/metrics/economics.py#L41) |

## Где оказываются пины и данные

| Пин | Где фиксируется результат | Источник |
| --- | --- | --- |
| Конфигурация / model_spec | configure-result fingerprint, episode_start журнала, raw-записи и финалы; оси/модели в манифесте | [shop:259](../services/shop/app.py#L259), [shop:391](../services/shop/app.py#L391), [launcher:157](../launcher/campaign.py#L157) |
| `world`, `dataset_hash` | meta БД магазина, reset-result и manifest кампании | [reset_world](../services/shop/db.py#L1354), [campaign:210](../launcher/campaign.py#L210) |
| Цель, метод, стиль | Ячейка manifest; собственные raw-записи attack; style legal-записи | [attack:101](../services/attack/episode.py#L101), [traffic:88](../services/traffic/episode.py#L88) |
| Экономика | Читается при расчёте; стоимость и L* хранятся в metric_results | [metrics:112](../services/metrics/app.py#L112), [extract:56](../services/metrics/extract.py#L56) |

Отдельной обязательной колонки с SHA256 economics/styles/goals в каждой строке метрик
нет. Для воспроизводимого отчёта сохраняйте ревизию репозитория, сами frozen-файлы
и исходные данные; наличие папки frozen не является автоматическим полным пиннингом
каждого результата ([схема метрик](../services/metrics/models.py#L15)).

## Форматы и границы контроля

Мир загружается с проверкой CSV/манифеста, его dataset_hash считает shop через
hash_tree. Хеш-функция нормализует CRLF→LF и учитывает относительные имена файлов
([repro.py:56](../services/shop/repro.py#L56), [repro.py:84](../services/shop/repro.py#L84)).
Поэтому добавление файла внутрь `world_a/` тоже меняет пин дерева; этот README
находится выше мира и не меняет его состав.

Lock описывает ожидаемые конфиги, но текущая номинальная проверка сверяет только
наличие имени. Runtime configure **не гарантирует** сравнение SHA256 с lock
(I43-02; [nominal.py:47](../lab/nominal.py#L47)).
Атакующий загружает методы непосредственно из tactics.json; существование
MANIFEST не означает, что этот загрузчик проверяет SHA256 всех JSONL на каждом
эпизоде ([tactics.py:20](../services/attack/tactics.py#L20)).

## Инварианты и изменение заморозки

1. Модель не добавляется молча, мир не меняется от seed, цель не подменяется
   методом, обе ноги используют один стиль — [мануал](../docs/agent-manual.md#критичные-инварианты-не-ломать).
2. При изменении конфигов согласуйте JSON, fingerprint и lock; при изменении
   мира — CSV/manifest и ссылки целей; при изменении корпуса — версии/манифесты
   и иллюстрации методов. Проверяйте затронутый потребитель, а не только валидность JSON.
3. Экономический пин задаёт допущения, а не измеренные тарифы. Изменение цены
   допускает post-hoc пересчёт поверх прежнего сырья, но это уже другой сценарий расчёта.
4. Заморозка и её изменения должны оставаться reviewable в Git; README не заменяет
   осознанный коммит с OpenSpec и приёмку владельца.

## Как проверить

Из корня:

```sh
uv run pytest -q tests/test_configs.py tests/test_world.py tests/test_attack.py tests/test_shared_styles.py
uv run pytest -q tests/test_metrics_costs.py tests/test_metrics_queue.py
openspec validate --all
```

Эти команды проверяют соответствующие контракты, но не аттестуют реальные веса
LLM или PostgreSQL. Ограничения и учёт аудита — [design](../openspec/changes/module-readmes/design.md#сверка-с-аудитом-43).
