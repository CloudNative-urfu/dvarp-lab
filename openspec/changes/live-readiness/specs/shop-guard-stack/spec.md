# Shop Guard Stack — Specification (delta: live-readiness)

## MODIFIED Requirements

### Requirement: Local LLM client
LLM-клиент SHALL работать в локальном контуре (NFR-2.5): settings с
закреплённой версией, backends (stub по умолчанию, локальный OpenAI-
совместимый), limits и usage_estimate (NFR-2.6, ревизия 2026-11-12: модели
≤ 16B, единый предел, без двухуровневых исключений 8B/12B); ключи —
только в env процесса, в журнал и манифесты не попадают.

#### Scenario: Local endpoints only
- **WHEN** клиент настроен по умолчанию
- **THEN** эндпоинты на 127.0.0.1, ключи не попадают в журнал
