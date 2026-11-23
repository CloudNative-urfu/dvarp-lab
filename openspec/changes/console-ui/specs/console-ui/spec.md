## ADDED Requirements

### Requirement: Console UI as reader/invoker only
Консоль полигона SHALL работать на :9410 как статическая страница с
`/api/*` и быть только читателем/вызывателем: ноль расчётов и ноль
оркестрации — запуск через те же `launcher.campaign.run_campaign/probe`,
расчёт через `metrics /compute` (инвариант 8a).

#### Scenario: No logic duplication
- **WHEN** консоль запускает кампанию или пересчитывает метрики
- **THEN** вызываются те же функции launcher/metrics, что и у CLI; новых
  расчётов в ui_svc нет

### Requirement: UI endpoints
`/api/*` SHALL предоставлять: `GET /api/meta` (свод frozen + health
сервисов), `POST /api/volume` (объём до запуска), `POST /api/run`
(спецификация осей; фоновый поток; 409, если прогон уже идёт; объём сверх
guard требует `confirm: true`), `GET /api/run/status` (живой прогресс),
`POST /api/probe` (одна атака) и read-only прокси
(`/api/metrics/{config}`, `/api/compute`, `/api/text/{episode}`,
`/api/chain`, `/api/runs`).

#### Scenario: Single run at a time
- **WHEN** второй `/api/run` при активном прогоне
- **THEN** ответ 409, состояние текущего прогона не нарушено

#### Scenario: Progress visible
- **WHEN** прогон идёт
- **THEN** `/api/run/status` отдаёт стадию, число ячеек и текущую ячейку

## ADDED Requirements

### Requirement: Roster-driven UI defaults
Консоль SHALL брать модели из ростера `frozen/llm.json` (атакующая модель —
из роли attacker), числовые оси получать осмысленные дефолты (point-режим)
и деградировать при пустом ростере: фолбэк на ручной ввод вместо
пустого/битого списка.

#### Scenario: Attacker from roster
- **WHEN** форма запуска открывается
- **THEN** атакующая модель выбирается из ростера; пустой ростер даёт
  работающий ручной ввод, а не пустой список

#### Scenario: Numeric defaults
- **WHEN** числовые оси (episodes, seeds) показаны без явных значений
- **THEN** подставлены point-дефолты осей

## ADDED Requirements

### Requirement: Reference endpoints
Справочные read-only эндпоинты SHALL обслуживать консоль: `filter
GET /episodes` (список эпизодов сырой БД без текстов: episode_id,
config_name, channels, n_turns) и `metrics GET /configs` (конфигурации, по
которым есть прогоны); тесты покрывают их контракт.

#### Scenario: Episodes without texts
- **WHEN** `filter /episodes` вызван
- **THEN** возвращены метаданные эпизодов без текстов ходов

#### Scenario: Configs with runs
- **WHEN** `metrics /configs` вызван
- **THEN** возвращены только конфигурации с существующими прогонами

### Requirement: Metric checkpoints and term tooltips
Консоль SHALL показывать метрики оглавлением-чекпоинтами: оглавление
кликабельно к карточке конфига, карточки — по конфигурациям, выбор эпизода
— из справочного списка; русские сноски терминов — тултипы при наведении
(инвариант 8a).

#### Scenario: Checkpoint navigation
- **WHEN** пользователь кликает чекпоинт оглавления
- **THEN** открыт карточка соответствующего конфига

#### Scenario: Term tooltips
- **WHEN** пользователь наводит на термин метрик
- **THEN** показана русская сноска термина
