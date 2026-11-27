## Why

Issue: https://github.com/CloudNative-urfu/dvarp-lab/issues/67

OpenAI-совместимые провайдеры (Groq через OpenRouter и др.) у инструмента без
параметров отдают `"arguments": "null"`. Парсер `tool_calls` отвергал такой
ответ (`LLMResponseError: аргументы не объект`), и живой агент падал на первом
ходу каждого эпизода.

## What Changes

- `services/shop/llm/backends.py`: `arguments` равные JSON `null` читаются как `{}`;
  остальные не-объекты по-прежнему отвергаются;
- тест `test_null_arguments_of_parameterless_tool`.

## Capabilities

### Modified Capabilities
- `remote-llm`: разбор вызовов инструментов живого клиента.

## Impact

Только живой клиент; заглушка и формат кассет не меняются.
