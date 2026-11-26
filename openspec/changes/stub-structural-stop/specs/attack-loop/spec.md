## ADDED Requirements

### Requirement: Structural attacker stop
Атакующий SHALL останавливаться только по структурным сигналам: сессия
закрыта shop (`ended` в цикле эпизода), бюджет исчерпан, либо живая модель
объявила остановку явным протоколом (DONE). Stub-атакующий SHALL не принимать
решений по подстрокам текста агента.

#### Scenario: Session stays open
- **WHEN** ответ агента звучит как исполнение, но сессия открыта (`ended=false`)
- **THEN** атакующий продолжает давление до бюджета; лексика не останавливает

#### Scenario: Session closed by shop
- **WHEN** shop закрыл сессию (`ended=true`)
- **THEN** эпизод завершается с исходом `session_closed` независимо от текста
