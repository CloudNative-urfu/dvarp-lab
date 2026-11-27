# Tasks

## 1. Tasks

- [x] executor: `read_ticket` возвращает `model_time` (meta.now)
- [x] prompt: строка в п.1 (использовать model_time, не угадывать «сегодня»),
  PROMPT_VERSION → refund-agent-prompt-6
- [x] test `read_ticket.model_time == meta.now`; read_order не расширен

## 2. Validation

- [x] ruff (check + format) зелёный
- [x] `uv run pytest` полный набор зелёный
- [x] смок зелёный
- [x] live-проверка forgetful (g0, 1 эпизод): агент считает окно от model_time
