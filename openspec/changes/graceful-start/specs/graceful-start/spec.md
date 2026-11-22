## ADDED Requirements

### Requirement: Raw DB exists at boot
filter_svc SHALL создавать сырую БД при старте сервиса (lifespan), до
первой записи; БД остаётся append-only и не пересоздаётся.

#### Scenario: Boot on empty env
- **WHEN** filter_svc поднимается с чистым окружением
- **THEN** файл сырой БД существует сразу после старта

### Requirement: No-data metrics degrade to 200
metrics_svc SHALL отвечать на `/compute` и `GET /metrics/{config_name}` кодом
200, когда сырой БД ещё не существует: `{computed: 0}` и пустой результат с
note «нет прогонов» соответственно; ошибки 500 на пустом старте нет.

#### Scenario: Empty start metrics
- **WHEN** метрики запрошены до первых прогонов
- **THEN** ответ 200 с пустым результатом и note, консоль открывается

### Requirement: Journal sequence resume
Нумерация файлов журналов shop SHALL возобновляться после рестартов
(`max(existing) + 1`): рестарты dev-стека добавляют журналы, а не требуют
ручной чистки; коллизия имени с непустым файлом SHALL фейл-клозиться
(EventLogError) — молчаливой перезаписи не бывает.

#### Scenario: Restart keeps append-only
- **WHEN** сервис перезапущен рядом с journal-3.jsonl
- **THEN** следующая ячейка пишет в journal-4.jsonl; существующие журналы
  не переписываются
