# UI: консоль поверх launcher, filter и metrics

Консоль отображает данные и вызывает существующие операции; сама не считает
метрики и не воспроизводит оркестрацию кампании. Срез: `main@fdcf6f8`, 27.11.2026.
[HTTP-контракты](../../docs/api.md#ui_svc-порт-9410),
[процедура кампании](../../launcher/README.md).

## Входы и выходы

| HTTP | Владелец поведения / данные | Источник |
| --- | --- | --- |
| `GET /`, `/static/*`, `/health` | HTML, vendored Vue и файлы интерфейса; проверка процесса | [app.py:36](app.py#L36), [app.py:48](app.py#L48) |
| `GET /api/meta` | axes, run_fields, probe_fields, presets, terms, guard, имена remote endpoints, remote_models и health пяти сервисов | [app.py:58](app.py#L58), [describe.py:210](describe.py#L210) |
| `POST /api/volume` | `{spec: ...}` → объём по `resolve_campaign` | [app.py:77](app.py#L77) |
| `POST /api/run`, `GET /api/run/status` | Фоновый run_campaign; status/stage/current/error либо итоговый manifest | [app.py:91](app.py#L91) |
| `POST /api/probe` | Вызов launcher.probe; текущее ограничение цели описано ниже | [app.py:240](app.py#L240) |
| `GET /api/runs`, `/api/runs/{run_id}` | Сводки/полные файловые манифесты | [app.py:202](app.py#L202) |
| `POST /api/compute`, `/api/preview` | Прокси к расчёту с сохранением / без сохранения | [app.py:132](app.py#L132) |
| `GET /api/metric-models`, `/api/metric-configs`, `/api/metrics/{config_name}` | Модели, конфиги и строки, разложенные по model_spec×mode | [app.py:151](app.py#L151), [app.py:192](app.py#L192) |
| `GET /api/text/{episode_id}`, `/api/dialog/{episode_id}`, `/api/episodes`, `/api/chain` | Read-only прокси filter | [app.py:177](app.py#L177) |

## Хранилища и схемы представлений

Своей БД нет. История читается из общего с launcher `LAB_RUNS_DIR/*/manifest.json`;
при некорректном JSON файл пропускается ([app.py:202](app.py#L202)). Raw и метрики
живут у сервисов-владельцев. Текущее состояние запуска находится в памяти `_STATE`,
а не в устойчивой очереди заданий ([app.py:41](app.py#L41)).

`axes[]` содержит `name`, `label`, `kind`, `modes`, `universe`, `default`, а для
модельных осей — возможность свободного ввода. Массивы строятся из frozen через
launcher.axes; новой записи реестра не нужен отдельный список во фронте
([describe.py:49](describe.py#L49)). `groups[].final` в представлении метрик — словарь
metric→value; значения берутся из metrics, UI лишь меняет форму ответа
([app.py:156](app.py#L156)).

## Поля прогресса и управление запуском

Под lock проверяется отсутствие другого running-запуска. Если объём выше guard
и confirm не задан, возвращается needs_confirm; иначе daemon-thread вызывает
run_campaign и обновляет `_STATE` callback-прогрессом. Ошибки переходят в status=error,
успех — done с manifest ([app.py:91](app.py#L91)). Единственность запуска относится
к этому процессу UI, а не ко всем CLI/экземплярам сервиса.

Сводка истории сообщает run_id, remote_llm, число cells, число episodes-пар и axes
([app.py:214](app.py#L214)). «Зелёный health» означает доступность процесса,
а не прохождение инвариантов данных или готовность реальной модели.

## Инварианты и текущие ограничения

- Фронт рисует описания из describe.py, не задаёт собственные формулы, оси и циклы.
- `/preview` не сохраняет метрики; `/compute` сохраняет их через metrics-сервис.
- Метаданные remote_endpoints — имена env-переменных, не URL или ключи.
- **I43-03 подтверждается кодом**: форма описывает goal, но `ProbeIn` и вызов
  launcher не передают его. Поэтому UI probe получает ошибку «probe требует цель»;
  обещать рабочую отправку цели через UI на этом срезе нельзя
  ([describe.py:68](describe.py#L68), [app.py:240](app.py#L240)).
  Это finding, не исправление в рамках документации; [статус аудита](../../openspec/changes/module-readmes/design.md#сверка-с-аудитом-43).

## Карта кода

| Путь | Роль |
| --- | --- |
| [app.py](app.py) | Маршруты, запуск потока, прокси и файловые манифесты |
| [describe.py](describe.py) | Оси/поля/пресеты/словарь как данные |
| [static/index.html](static/index.html) | Точка входа страницы |
| [static/app.js](static/app.js), [static/style.css](static/style.css) | Компоненты отображения и стили |
| [static/vendor/](static/vendor/) | Локальная копия Vue; node-build для запуска не требуется |

## Как проверить

Из корня:

```sh
uv run pytest -q tests/test_ui.py tests/test_axes.py
uv run python scripts/dev.py
```

Откройте `http://127.0.0.1:9410`, проверьте `/api/meta`, объём одной ячейки,
историю и read-only просмотр цепочки. Для запуска выбирайте конкретные goal/style/tactic;
все значения реестров дают большой объём. UI probe не используйте как доказательство
работоспособности оси целей, пока I43-03 не исправлен.
