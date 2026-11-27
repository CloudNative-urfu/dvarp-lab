# Launcher: ячейки кампании и парные эпизоды

Launcher выполняет одну процедуру для CLI и UI: из осей строит ячейки, сбрасывает
мир, применяет защиту, запускает обе ноги на одном снимке и сохраняет манифест.
Срез: `main@fdcf6f8`, 27.11.2026. Формат осей — [API](../docs/api.md#launcher-cli--модуль-кампании).

## Вход и выход

У модуля нет своего HTTP-сервера. `python -m launcher` преобразует аргументы в JSON-spec
либо читает `--spec`; UI вызывает ту же `run_campaign` напрямую
([__main__.py:16](__main__.py#L16), [UI app.py:91](../services/ui/app.py#L91)).

| Объект | Состав | Источник |
| --- | --- | --- |
| Оси перечислений | `configs`, `goals`, `styles`, `tactics`, `agent_models`, `attacker_models`; значения из frozen | [axes.py:19](axes.py#L19) |
| Числовые оси | `episodes`, `seeds`; для episodes point=N означает индексы 1…N, для seeds — одно значение | [axes.py:95](axes.py#L95) |
| Режимы | `all`, `point`, `set`, `range`, `all_limited`; числовой all запрещён | [axes.py:95](axes.py#L95) |
| Дополнения | budget, compute, include_remote, include_probe, confirm; scenario_pairs ограничивает style×tactic, но цели перемножаются независимо | [axes.py:157](axes.py#L157), [campaign.py:296](campaign.py#L296) |
| Результат | Манифест кампании либо `needs_confirm` до запуска при превышении guard | [campaign.py:131](campaign.py#L131) |

Ячейка — `(config, goal, style, tactic, agent_model, attacker_model, seed)`.
`Campaign.volume()` возвращает число ячеек и **число пар** `cells × len(episodes)`;
одна пара состоит из двух HTTP-запусков ног. Guard 1000 сравнивается с этим
числом, хотя поле называется episodes ([axes.py:157](axes.py#L157),
[campaign.py:148](campaign.py#L148)). Не путайте этот счётчик с общим числом ног.

## Порядок выполнения и идентификаторы

1. Проверка frozen-конфига и пин модели; неизвестное ростеру имя получает
   `revision=remote-verification`, `params_b=None` ([campaign.py:58](campaign.py#L58)).
2. На каждую ячейку `/reset` → `/configure` → `/snapshot`; пин мира каждой
   ячейки сверяется с первой ([campaign.py:194](campaign.py#L194)).
3. Legal → restore → чтение legal-финала → attack → restore → чтение attack-финала.
   Обе ноги получают один style; цели и методы не меняют legal-кейс
   ([campaign.py:234](campaign.py#L234)).
4. Сохранение манифеста; optional compute по каждому конфигу передаёт оба флага
   include_remote/include_probe ([campaign.py:291](campaign.py#L291)).

Обе ноги имеют `run_id-L/A<i>-<scenario-signature>-s<seed>`. Сигнатура строится
из полей ячейки, кроме config/моделей/seed; на этом срезе она включает goal,
style, tactic. Модели и config различаются ключами агрегации, а seed присутствует
в ID явно ([campaign.py:73](campaign.py#L73)). Это исправляет повтор legal-ID
между разными целями/методами из I43-01; полного нового аудита этим не заменяет.

## Хранилище и поля манифеста

`LAB_RUNS_DIR/<run_id>/manifest.json` (по умолчанию `runs/`) записывается после
прохождения ячеек. run_id содержит конфиг/мультиконфиг, первый seed и время с
точностью до секунды; код не даёт глобальной гарантии уникальности между
одновременными запусками ([campaign.py:153](campaign.py#L153)).

| Поле | Назначение |
| --- | --- |
| `run_id`, `remote_llm`, `budget`, `episodes` | Идентификация, remote-пин, бюджет и индексы пар |
| `axes` | Разрешённые значения осей и scenario_pairs |
| `world` | `name`, `dataset_hash` из `/reset`, сверяемые между ячейками |
| `guard_budget` | По конфигам: верхние оценки вызовов и выходных токенов LLM-гвардов, тариф; стоимость prompt измеряется журналом, не этой оценкой |
| `cells[]` | config, seed, обе model_spec, scenario goal/style/tactic и episodes |
| `cells[].episodes[]` | Индекс пары, legal/attack ID и результаты обеих ног |

Источники: [manifest:157](campaign.py#L157), [guard_token_budget:97](campaign.py#L97),
[cell_result:222](campaign.py#L222). run_id/seed используются для групп вариативности;
живой ответ модели seed не делает воспроизводимым. Данные мира от seed не зависят.

## Инварианты и ограничения

- Снимок и стиль общие; restore между ногами обязателен. Финалы filter не откатываются.
- Структурный outcome берётся через `/finals`; при ошибке чтения остаётся значение
  причины остановки симулятора ([campaign.py:48](campaign.py#L48)).
- Probe требует goal, запускает только attack, передаёт `probe=true` симулятору,
  не пишет манифест. Метрики пропускают только маркированные строки; отсутствие
  probe в сырье shop не гарантирует исключение всей ноги. В этой функции нет
  завершающего restore, в отличие от кампании
  ([campaign.py:310](campaign.py#L310)).
- Номинальная проверка сейчас не сверяет SHA256 с lock (I43-02). I43-06 — отсутствие
  run/seed в `/turn` симуляторов — ограничивает полноту seed_spread защитника.
  Сводка — [сверка #43](../openspec/changes/module-readmes/design.md#сверка-с-аудитом-43).

## Карта кода

| Файл | Роль |
| --- | --- |
| [__main__.py](__main__.py) | CLI-флаги, --spec и печать результата |
| [axes.py](axes.py) | Значения осей, режимы выбора, декартово произведение и объём |
| [campaign.py](campaign.py) | Порядок сервисных вызовов, ID, пины, манифест и probe |
| [__init__.py](__init__.py) | Экспорт run_campaign и probe |

## Как проверить

Из корня, тесты не требуют запущенных сервисов:

```sh
uv run pytest -q tests/test_axes.py tests/test_campaign.py tests/test_launcher_compute_cli.py
```

После запуска dev-стека (`uv run python scripts/dev.py`) — одна пара, а не все
70 методов × 7 целей × 23 стиля:

```sh
uv run python -m launcher --config g0 --goals refund_expired --styles formal --tactics direct_task --episodes 1 --seed 0 --compute
```

Для изолированного smoke задавайте новый каталог:
`uv run python scripts/smoke.py --tmp <новый-каталог>`. Текущий smoke проверяет
цепочку и доступность расчёта, но не все численные знаменатели (I43-05).
