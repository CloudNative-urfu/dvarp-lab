## Why

Репозиторий создаётся как единственное место исследования: код защиты
переносится из dvarp-prototype @ `d5828df`, вокруг него — сервисы полигона,
замороженные характеристики и общая мини-либа. Без зафиксированного каркаса
(структура каталогов, frozen-наборы, openspec-процесс, хуки коммита) каждая
следующая подсистема не имеет опоры: расползутся порты и имена, потеряются
инварианты, а трейс разработки останется в истории коммитов без спецификаций.

## What Changes

- Каркас репозитория: `services/` (пять сервисов FastAPI), `lab/` (общая
  мини-либа: chain, cassette, seeds, modelspec, nominal, db, svc_client),
  `frozen/` (конфигурации защиты с lock-хешем, корпус атак, ростер моделей,
  стили общения), `launcher/`, `tests/`;
- openspec-процесс обязателен с первого коммита: любое содержательное
  изменение сопровождается каталогом `openspec/changes/<change-id>/`
  (schema spec-driven, контекст проекта — `openspec/config.yaml`);
- хуки коммита: ruff из nixpkgs (check + format) и `openspec validate --all`
  (`.pre-commit-config.yaml`);
- README с порядком чтения и запуска.

## Capabilities

### New Capabilities
- `repo-baseline`: каркас репозитория, frozen-наборы, мини-либа `lab`,
  openspec-процесс и хуки коммита.

### Modified Capabilities
<!-- none: первый change репозитория -->

## Impact

- Новые файлы: каркас каталогов, `frozen/*`, `lab/*`, скелеты пяти сервисов,
  `openspec/*`, `.pre-commit-config.yaml`, `pyproject.toml`, `uv.lock`;
- все последующие changes опираются на этот каркас: порты 9410–9415, имена
  сервисов, `lab.chain`/`lab.cassette`, пин model_spec.
