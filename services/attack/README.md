# Attack: цель × метод × тон

Сервис симулирует атакующую ногу через текстовый чат. Факты претензии берутся
из frozen-файлов, без чтения БД магазина и без запроса брифа у shop. Срез:
`main@fdcf6f8`, 27.11.2026. [HTTP-контракт](../../docs/api.md#attack_svc-порт-9413).

## Входы и выходы

| HTTP | Данные и результат | Источник |
| --- | --- | --- |
| `POST /run-episode` | ID, конфиг, `attacker_model`, `goal`, `tactic`, бюджет, seed; optional style, run_id, group_seed, probe, remote_llm → outcome/turns/attempts | [app.py:24](app.py#L24) |
| `POST /start`, `POST /stop`, `GET /state` | Флаги started/stopped в памяти процесса; это не прерывание уже исполняющегося цикла | [app.py:44](app.py#L44), [episode.py:85](episode.py#L85) |
| `GET /health` | Доступность процесса | [app.py:39](app.py#L39) |

Цикл передаёт shop только текст, ID, канал, номер хода и goal. Он прекращается
при `ended` (`session_closed`), исчерпании бюджета (`budget_exhausted`) или
остановке атакующего (`attacker_stopped`). Ни одно из этих значений само по себе
не является verdict об исполненном нарушении ([episode.py:85](episode.py#L85)).

## Источники и собираемые поля

| Источник | Семантика | Код |
| --- | --- | --- |
| `frozen/corpus/goals.json`, манифест мира | Цель задаёт **что требовать**, реальный либо фиктивный заказ и фиксированные факты | [episode.py:50](episode.py#L50), [lab/world.py:139](../../lab/world.py#L139) |
| `frozen/corpus/tactics.json` | Метод задаёт **как давить**: description и illustrations; примеры не обязательный скрипт | [tactics.py:20](tactics.py#L20) |
| `frozen/styles.json` | Общий с legal тон; тексты реестра не копируются в методы | [attacker.py:92](attacker.py#L92), [style.py](../traffic/style.py) |
| Filter `/record` | `config_name`, `tactic`, `goal`, style/probe/remote по наличию, group_seed либо seed, run_id, `llm_calls` | [episode.py:101](episode.py#L101) |

Собственной БД сервис не создаёт. Пин записи — `attacker_model`, роль кассетного
вызова — attacker. Защищаемый shop параллельно пишет своё сырьё с пином агента:
это разные группы model_spec, а не два нарушения одной группы
([Recorder](../traffic/record.py#L15), [metrics.extract](../metrics/extract.py#L131)).

## Построение промпта и начало диалога

`run_attack` проверяет имена, механически рендерит claim из frozen-мира и собирает
system: `YOUR CLAIM` → `METHOD` → общая тон-клауза. Факты не генерируются моделью
([episode.py:45](episode.py#L45), [build_system_prompt](attacker.py#L92)).

Текущий **LLM-атакующий генерирует первую реплику** по этому system-промпту;
при пустом ответе или DONE использует фиксированный claim. Вызов начала тоже
попадает в кассету. Далее сохраняется вся история; DONE завершает цикл
([attacker.py:67](attacker.py#L67)). Stub начинает непосредственно с claim,
а продолжает push-банком стиля или нейтральным фолбэком. Без стиля остаётся
прежний банк давления ([attacker.py:29](attacker.py#L29)).

В docstring episode.py сохранилась более старая формулировка о старте «без генерации»;
для live-пути актуально поведение `LlmAttacker.opening` и раздел attack в docs/api.md.

## Инварианты и ограничения

- Нет доступа к shop SQL и решениям защиты; frozen-манифест — разрешённые факты мира,
  не скрытый доступ к текущему состоянию магазина.
- Метод не меняет цель, тон не меняет факты; в паре один style и один исходный snapshot.
- Структурный финал пишет shop; launcher читает его у filter после завершения ноги.
- Stub прекращает давление и по словам о возврате в ответе агента. Это локальная
  эвристика остановки, а не oracle нарушения ([attacker.py](attacker.py)).
- Remote определяется входным флагом и endpoint атакующего; свой Recorder пишет
  `run_id`/`seed`, но в shop `/turn` они сейчас не передаются (I43-06)
  ([episode.py:68](episode.py#L68), [episode.py:90](episode.py#L90)).
- Probe не имеет legal-пары; Recorder ставит raw.probe для исключения своих
  записей из обычного расчёта. Shop этот флаг не получает, поэтому исключение
  всех записей ноги группы защитника не гарантировано
  ([metrics](../metrics/README.md#инварианты-и-сверка-аудита)). Напрямую
  симуляция не финализирует shop; завершение бюджетом требует drain через
  restore/reset, как делает launcher ([shop._drain](../shop/app.py#L609)).

## Карта кода

| Файл | Роль |
| --- | --- |
| [app.py](app.py) | API и флаги процесса |
| [episode.py](episode.py) | Загрузка цели/метода/стиля, claim, цикл и метаданные |
| [attacker.py](attacker.py) | Общий system, stub и LLM с историей |
| [tactics.py](tactics.py) | Чтение реестра и включение иллюстраций в промпт |
| [../traffic/record.py](../traffic/record.py) | Транспорт модели и буфер кассет |

## Как проверить

Из корня репозитория; без внешних моделей:

```sh
uv run pytest -q tests/test_attack.py tests/test_shared_styles.py tests/test_world.py
uv run pytest -q tests/test_campaign.py tests/test_remote_llm.py
```

Для опыта с живой моделью настройте endpoint и имя через env процесса; ключи
не сохраняйте в командах документации, Git и манифестах. Запуск одной пары —
в [контрактах launcher](../../docs/api.md#launcher-cli--модуль-кампании).
