# Контракты API сервисов dvarp-lab

Все сервисы — FastAPI, обмен JSON по HTTP на локальных портах. Поля `model_spec`
везде — `lab.modelspec.ModelSpec.as_dict()` (name, role, params_b, revision).
Внешний барьер: наружу от СС выходит **только текст**; сырьё уходит напрямую в
`filter_svc` (изнутри shop_svc, не через ответ /turn).

## shop_svc (порт 9411)

- `POST /reset` `{seed: int}` → `{ok: true, db_version: str}` — сброс БД к исходному
  состоянию; генерация начальных данных детерминирована от seed.
- `POST /configure` `{config_name: str, agent_model: model_spec}` → `{ok: true, applied: {...}}` —
  загрузка конфигурации защиты из frozen/configs (гвардрейлы, политика, права, эскалация);
  конфиг не проходит номинальную проверку → 400.
- `POST /turn` `{episode_id: str, channel: "legal"|"attack", text: str, turn: int}` →
  `{text: str, ended: bool, session_status: str}` — ход агента поддержки.
  Ответ возвращает только текст; сырьё (решения гвардрейлов, вызовы инструментов,
  журнал) доставляется в `filter_svc` POST /record изнутри shop_svc.
- `GET /snapshot/{snapshot_id}` → снимок состояния (JSON).
- `POST /snapshot/restore` `{snapshot_id: str}` → `{ok: true}`.
- `GET /db/readonly` — описание подключения read-only к БД магазина для traffic_svc
  (в dev — строка SQLAlchemy; у traffic_svc прямой читающий доступ разрешён схемой).

## traffic_svc (порт 9412)

- `POST /run-episode` `{episode_id, config_name, agent_model, style: str, seed: int}`
  → `{outcome: str, turns: int, transcript_ids: [...]}` — правдивые возвраты на основе
  БД магазина (читает напрямую), стиль из frozen/styles.json; каждый ход — через
  shop_svc /turn (channel="legal").

## attack_svc (порт 9413)

- `POST /run-episode` `{episode_id, config_name, agent_model, attacker_model, tactic: str,
  budget: int, seed: int, style: str?}` → `{outcome, turns, attempts}` — размеченный
  стартовый промпт тактики из frozen/corpus, ходы через shop_svc /turn (channel="attack"),
  видит только текст; без доступа к БД магазина и защите. `style` — общий с легальным
  трафиком тон парного прогона (frozen/styles.json): тон-клауза в system-промпт
  атакующего, стартовая реплика остаётся корпусной (тактика — механизм, стиль — тон).
  Записи filter пинят `raw.style`.
- `POST /start` / `POST /stop` — сигналы начала/конца атаки для launcher.

## filter_svc (порт 9414)

- `POST /record` `{episode_id, channel, turn, text, model_spec, raw: {...}, snapshot: {...}}`
  → `{record_id}` — сырьё и снимок в свою БД (хеш-цепочка lab.chain), кассетная строка
  формируется из raw.llm_calls (запрос→ответ).
- `GET /text/{episode_id}` → `{turns: [{turn, channel, text}]}` — только тексты.
- `GET /chain/verify` → `{defects: []}`.

## metrics_svc (порт 9415)

- `POST /compute` `{config_name: str, model_spec?: model_spec}` → `{computed: n}` —
  пересчёт метрик (L*, break-even, detection) из read-only доступа к сырой БД
  filter_svc; результат — в свою БД; правка формул не требует перезапуска прогонов.
- `GET /metrics/{config_name}` → агрегаты по config × model.

## launcher (CLI, без порта)

- `python -m launcher run --config g0 --episodes N --tactics t1,t2 --styles s1
  --seed S [--compute]` — перебор сетки «модель × конфигурация × сценарий»:
  на каждую ячейку — номинальная проверка, /reset, парные прогоны (legal + attack
  на одном исходном состоянии), манифест прогона в runs/ (config × scenario ×
  model_spec × seed).
- Номинальные проверки — `lab.nominal.check_config` перед каждым прогоном.
