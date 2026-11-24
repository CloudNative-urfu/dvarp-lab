## 1. Tasks

- [x] env Переименовать `env.example` → `.env.example`; заполнить дефолтами
  из кода (URLs сервисов, пути SQLite); убрать имена моделей из дефолтов —
  плейсхолдеры `<имя-модели-у-прокси>`
- [x] dotenv stdlib-загрузчик `.env` в `scripts/dev.py` (кавычки, export,
  inline-комментарии, setdefault — не перекрывать окружение)
- [x] lint F841 в `tests/test_empty_start.py` (техническая правка: хук
  `ruff check .` был красный на всём наборе из-за неиспользуемой переменной)
- [x] verify `uv run pytest` зелёный; хуки pre-commit зелёные
