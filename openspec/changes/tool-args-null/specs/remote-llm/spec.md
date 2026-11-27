## ADDED Requirements

### Requirement: Parameterless tool call arguments
Живой клиент SHALL читать `arguments` вызова инструмента, равные JSON `null`,
как пустой объект; любые другие не-объекты остаются ошибкой ответа модели.

#### Scenario: Null arguments
- **WHEN** провайдер вернул вызов инструмента с `"arguments": "null"`
- **THEN** вызов разобран с аргументами `{}`, эпизод продолжается
