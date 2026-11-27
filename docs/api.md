# Контракты API сервисов dvarp-lab

Все сервисы — FastAPI, обмен JSON по HTTP на локальных портах. Поля `model_spec`
везде — `lab.modelspec.ModelSpec.as_dict()` (name, role, params_b, revision).
Внешний барьер: наружу от СС выходит **только текст**; сырьё уходит напрямую в
`filter_svc` (изнутри shop_svc, не через ответ /turn).

## shop_svc (порт 9411)

- `POST /reset` `{seed: int}` → `{ok: true, db_version: str, world: str, dataset_hash: str}` —
  сброс БД к единственному замороженному миру (`frozen/seed_worlds/world_a`); сид
  детерминирует прогон, данные не меняет; `dataset_hash` — пин версии мира.
- `POST /configure` `{config_name: str, agent_model: model_spec}` → `{ok: true, applied: {...}}` —
  загрузка конфигурации защиты из frozen/configs (гвардрейлы, политика, права, эскалация);
  конфиг не проходит номинальную проверку → 400.
- `POST /turn` `{episode_id: str, channel: "legal"|"attack", text: str, turn: int, goal: str?}` →
  `{text: str, ended: bool, session_status: str}` — ход агента поддержки. Для
  attack-эпизода `goal` обязателен: тикет привязывается к заказу претензии цели
  (фиктивный заказ → тикет без заказа); для legal — к фиксированному
  всегда-возвратному заказу легального кейса мира.
  Ответ возвращает только текст; сырьё (решения гвардрейлов, вызовы инструментов,
  журнал) доставляется в `filter_svc` POST /record изнутри shop_svc. Если filter недоступен,
  запись хода ждёт в очереди эпизода и уходит первой при следующей доставке; /reset и
  /snapshot/restore сначала дожимают очередь и при недоступном filter отвечают 503.
- `GET /snapshot/{snapshot_id}` → снимок состояния (JSON).
- `POST /snapshot/restore` `{snapshot_id: str}` → `{ok: true}`.
- Строка подключения к БД магазина по HTTP не отдаётся: traffic_svc (прямой читающий
  доступ разрешён схемой) берёт её только из env `LAB_SHOP_DB_URL`.

## traffic_svc (порт 9412)

- `POST /run-episode` `{episode_id, config_name, agent_model, style: str, seed: int}`
  → `{outcome: str, turns: int, transcript_ids: [...]}` — правдивые возвраты на основе
  БД магазина (читает напрямую), стиль из frozen/styles.json; легальный кейс
  фиксирован (всегда-возвратный заказ мира), причина возврата — из данных БД.
  Каждый ход — через shop_svc /turn (channel="legal").

## attack_svc (порт 9413)

- `POST /run-episode` `{episode_id, config_name, agent_model, attacker_model, goal: str,
  tactic: str, budget: int, seed: int, style: str?}` → `{outcome, turns, attempts}` —
  промпт атакующего собирается attack-сервисом сам, без обращений к shop (бриф
  исключён): претензия — из цели (`frozen/corpus/goals.json`) и манифеста мира
  (`frozen/seed_worlds`), метод давления — из `frozen/corpus/tactics.json`, тон —
  из оси стиля (`frozen/styles.json`, общий с легальной ногой пары). Первую реплику
  LLM-атакующий пишет сам по методу (пусто/DONE → претензия цели), stub начинает с
  отрендеренной претензии; рандом-плейсхолдеров нет. Ходы через
  shop_svc /turn (channel="attack"), видит только текст; без доступа к БД магазина
  и защите. Записи filter пинят `raw.goal`, `raw.tactic`, `raw.style`.
- `POST /start` / `POST /stop` — сигналы начала/конца атаки для launcher.

## filter_svc (порт 9414)

- `POST /record` `{episode_id, channel, turn, text, model_spec, raw: {...}, snapshot: {...},
  record_id?}` → `{record_id}` — сырьё и снимок в свою БД (хеш-цепочка lab.chain), кассетная
  строка формируется из raw.llm_calls (запрос→ответ). `record_id` — ключ идемпотентности:
  повтор с уже записанным ключом отвечает `{record_id, duplicate: true}` и в цепочку не пишет.
  `raw.events` записи shop — события журнала только этого хода (дельта); история эпизода —
  все его записи по порядку.
- `POST /finalize` `{episode_id, config_name, channel, model_spec, verdict, guard_signals,
  leak, leak_turns, run_id?, seed?, remote_llm?}` → `{ok}` — финальная строка эпизода в `episode_finals`
  (одна на episode_id × config × model_spec, повтор заменяет); пишет shop_svc при закрытии
  эпизода или перед /reset и /snapshot/restore. Restore снапшота её не трогает.
- `GET /finals/{episode_id}` → `{episode_id, outcome, violation, task_status, escalated, leak}` —
  структурный исход завершённой ноги для манифеста launcher'а (без трейса и сырья).
- `GET /text/{episode_id}` → `{turns: [{turn, channel, text}]}` — только тексты;
- `GET /dialog/{episode_id}` → `{lines: [{turn, channel, author: customer|agent, text}]}` —
  эпизод диалогом из сообщений канала (реплика клиента/атакующего → ответ агента),
  повторные доставки схлопнуты; только тексты, сырьё не выходит;
- `GET /episodes` → `{episodes: [{episode_id, config_name, channels, n_turns}]}` —
  список эпизодов сырой БД без текстов (для выбора в консоли).
- `GET /chain/verify` → `{defects: []}`.

## metrics_svc (порт 9415)

- `POST /compute` `{config_name?: str, model_spec?: model_spec, include_probe?: bool,
  include_remote?: bool}` → `{computed: n}` —
   пересчёт метрик (L*, break-even, detection) из read-only доступа к сырой БД
   filter_svc; результат — в свою БД; правка формул не требует перезапуска прогонов.
   По умолчанию только `mode=local`; с `include_remote=true` локальные и удалённые
   группы считаются раздельно, а `mode=all` явно помечает общий расчёт. Каждая
   группа содержит `n_remote` и `seed_spread` по `(run_id, seed)` с L* относительно
   g0 того же сида и режима.
- `POST /preview` (тело как у `/compute`) → `{groups: [{config_name, model_spec, mode,
  final, seed_spread, raw}]}` —
  одноразовый расчёт по фильтрам: вычислить и вернуть, **ничего не пишет** в
  metric_results; `raw` — собранные агрегаты (n_attack, n_legal, V_k, V_n, w_A, w_L, V, R, E,
  C_ep, C_guard, E_attack, E_legal, ql_abandon + состояние аналитической очереди);
- `GET /models` → `{models: [model_spec]}` — пины моделей, по которым есть записи;
- `GET /metrics/{config_name}` → строки по config × model × mode (local/remote/all);
- `GET /configs` → `{configs: [...]}` — конфигурации, по которым есть прогоны
  (для оглавления-чекпоинтов в консоли).

## launcher (CLI + модуль кампании)

Спецификация осей (JSON): каждая ось — `{"mode": "point|range|all|all_limited"}`:
- перечислимые оси (frozen-наборы, отсортированные): `configs`, `goals`
  (`frozen/corpus/goals.json` — замороженные претензии поверх данных мира),
  `styles`, `tactics` (+ фильтр `split: dev|holdout`), `agent_models`,
  `attacker_models` — range = непрерывный срез отсортированного списка;
  технический режим `set` (явный список) — для CLI и пресетов;
- числовые оси: `episodes` (point = N эпизодов с 1-го), `seeds` (point = один
  сид; диапазон — повторение ячеек для детерминизма прогона: мир один и от
  сида не зависит); режим `all` на них запрещён (неограничены);
- глобально: `budget`, `compute`, `include_remote`, `include_probe`, `confirm` (подтверждение объёма сверх guard
  1000), `scenario_pairs` (явные пары style=tactic; ось целей перемножается
  независимо); `allow_remote_llm` устарел и игнорируется — не-локальный
  LLM-эндпоинт маркируется автоматически (пин в манифесте и записях, метрики
  пропускают, `include_remote` в `/compute`). CLI `--include-remote` /
  `--include-probe` передаёт флаги в расчёт без изменения процедуры кампании.
  Прогон пиннит версию мира
  (`world` + `dataset_hash`) в манифесте; снапшот пары — от мира. Конфигурации с
  LLM-гвардами (`g_in_qwen`/`g_in_granite`/`g_in_llama`, #21) требуют
  `LAB_GUARD_LLM_BASE_URL` и дают в манифесте `guard_budget` (вызовы на эпизод,
  потолок выходных токенов и его цена по `guard_tariff`).
CLI: `python -m launcher --config g0 --goals refund_expired --episodes 2 --seed 0
--compute` (флаги → та же спецификация). Каждая ячейка: `/reset` → `/configure`
(номинальная проверка + пин model_spec) → `/snapshot` → парные прогоны →
`/snapshot/restore`.
Probe: одна атака без парной ноги — требует `goal`; `raw.probe=true`, манифест
не пишется, метрики по умолчанию probe-записи пропускают (`include_probe` в
`/compute`).

## ui_svc (порт 9410)

Консоль полигона: статическая страница на vendored Vue (`static/vendor/vue.global.prod.js`,
MIT, без node/билда) + `/api/*`. **Фронт только рисует**: оси, режимы, поля, пресеты
и словарь терминов описаны данными (`services/ui/describe.py`) — новая ось/пресет/термин
без правки JS. **Инвариант: только читатель/вызыватель — ноль расчётов и ноль
оркестрации**: запуск идёт через те же `launcher.campaign.run_campaign/probe`, расчёт —
через `metrics /compute` и `/preview`.

- `GET /` — страница (Запуск / Прогоны / Трейс / Метрики / Система);
- `GET /api/meta` — описание формы: `axes` (name, label, kind enum|numeric, modes
  point/range/set/all/all_limited, universe, default, free — имена вне ростера),
  `run_fields`, `probe_fields`, `presets` (полные спецификации осей), `terms` (словарь
  тултипов), `guard`, `remote_models`, `remote_endpoints` (имена env-переменных, без
  URL), `health` 5 сервисов;
- `POST /api/volume` — объём кампании до запуска (cells, episodes);
- `POST /api/run` — спецификация осей; фоновый поток, один прогон за раз
  (409, если уже идёт); объём сверх guard требует `confirm: true`;
- `GET /api/run/status` — живой прогресс (стадия, ячейки, текущая ячейка);
- `POST /api/probe` — одна атака (probe);
- `GET /api/runs` — сводка манифестов (run_id, remote_llm, cells, episodes, axes);
  `GET /api/runs/{run_id}` — манифест целиком (ячейки, id эпизодов, исходы);
- `POST /api/compute` / `POST /api/preview` — фильтры `{config_name, model_spec,
  include_probe, include_remote}` → metrics `/compute` (с сохранением) / `/preview`
  (без); `GET /api/metrics/{config}` — сохранённые строки, разложенные по model_spec
  (`groups[].final`); `GET /api/metric-models`, `/api/metric-configs`;
- `GET /api/dialog/{episode}`, `/api/text/{episode}`, `/api/episodes`, `/api/chain` —
  прокси read-only.
