## ADDED Requirements

### Requirement: Task-issue linkage
Каждая задача SHALL вестись как issue в репозитории
`CloudNative-urfu/dvarp-lab`, привязанном к доске DVARP Board
(`CloudNative-urfu/projects/1`), с исполнителем из команды. Коммиты SHALL
выполняться только в контексте issue; задача без issue не ведётся.

#### Scenario: Task without issue
- **WHEN** предлагаемая работа не имеет issue
- **THEN** она не берётся в работу; сначала создаётся issue с ассайни

#### Scenario: Commits reference the issue
- **WHEN** коммиты задачи делаются
- **THEN** они относятся к контексту issue (в описании change/message видна
  задача)

### Requirement: Spec delta per issue
Каждый openspec change SHALL быть привязан к своему issue (ссылка на issue
в proposal). Каждое содержательное изменение SHALL коммититься вместе с
дельтой `openspec/changes/<change-id>/` (proposal, design, tasks, спеки);
изменение без дельты спеки не принимается. Технические правки (style,
chore, мелкие docs) отмечаются в tasks.md своего change.

#### Scenario: Substantial change without delta
- **WHEN** содержательное изменение коммитится без дельты спеки
- **THEN** pre-commit `openspec validate` не пройдёт либо PR не
  принимается до появления change

#### Scenario: Technical fix folded
- **WHEN** в рамках change делается техническая правка
- **THEN** она отмечается в tasks.md этого change

### Requirement: PR-only integration
Изменения `main` SHALL попадать только через PR из ветки задачи
`issue/<N>-<slug>` (N — номер issue), от свежего `main`; прямые пуши в
`main` SHALL быть запрещены branch protection для всех, включая владельца.
PR участника SHALL ждать ревью тимлида (axstiz) или назначенного им
ревьюера; PR тимлида — саморевью (мержит сам). Мерж — squash; заголовок
PR — Conventional Commit, совпадающий с итоговым коммитом; история
`main` — линейная.

#### Scenario: Direct push rejected
- **WHEN** пуш напрямую в `main`
- **THEN** push отклонён branch protection; работа идёт в ветке задачи

#### Scenario: Team member PR review
- **WHEN** участник открыл PR
- **THEN** мерж доступен после аппрува тимлида или назначенного ревьюера

#### Scenario: Lead self-review
- **WHEN** тимлид открыл собственный PR
- **THEN** мерж выполняет сам (устное саморевью), по-прежнему через PR

### Requirement: Canon immutability and request flow
Канон исследования SHALL жить в репо `CloudNative-urfu/dvarp`
(`docs/guardrails_requirements.md`, FR-1.x/NFR-2.x) и не SHALL
редактироваться из задач dvarp-lab. При расхождении кода dvarp-lab с
каноном агент SHALL создавать заявку в `canon-requests/` (формат
`NNN-<slug>.md`, сквозная нумерация лаба с 001, `path:line` обязательны)
в том же коммите, что и вызвавшее её изменение, и SHALL сообщать владельцу
(issue/чат). Правка канона — отдельный PR в `dvarp` после решения
владельца; после мержа заявка переносится в `accepted/` со ссылкой на PR,
при отклонении остаётся в `pending/` со статусом `rejected` и причиной.

#### Scenario: Code diverges from canon
- **WHEN** реализация в лабе расходится с требованием канона
- **THEN** заявка создана в `pending/` в том же коммите, владелец
  уведомлен; канон не правится напрямую

#### Scenario: Request accepted upstream
- **WHEN** PR в `dvarp` смержен
- **THEN** файл заявки перенесён в `accepted/` со статусом accepted и
  ссылкой на PR
