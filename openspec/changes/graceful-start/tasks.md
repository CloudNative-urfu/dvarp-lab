## 1. Tasks

- [x] filter-boot filter_svc создаёт сырую БД при старте (lifespan), до первой записи
- [x] metrics-no-data metrics: /compute → 200 {computed: 0}, /metrics → пустой результат с note, если сырой БД нет
- [x] journal-resume shop: нумерация journal-N.jsonl возобновляется после рестартов; коллизия — fail-closed
- [x] tests-empty `tests/test_empty_start.py` — пустой старт трёх сервисов
