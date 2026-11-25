# Research Validity — Specification

## ADDED Requirements

### Requirement: Validity and deliverables documentation

Репозиторий SHALL содержать `docs/validity.md` с разделами: разделение
эмпирики и модели, Threats to Validity (внешняя валидность, симуляция
экономики, stub vs live, корпус атак, кейсы), деливерабл «параметрическая
модель цены гвардов» (механизм-компонент / контекст-компонент /
структурные формы / протокол переноса), граница претензий.

#### Scenario: Document exists with required sections

- **WHEN** исследуется состояние документации валидности
- **THEN** `docs/validity.md` присутствует и содержит все перечисленные
  разделы

#### Scenario: Validity fixes before pre-registration

- **WHEN** меняется постановка исследования (мир, оси, экономика)
- **THEN** соответствующие разделы `docs/validity.md` ревизуются в том
  же change; пост-хок правки границы претензий после пре-регистрации
  запрещены
