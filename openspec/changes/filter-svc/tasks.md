## 1. Tasks

- [x] store `services/filter/store.py` — сырая БД, append-only записи на хеш-цепочке lab.chain
- [x] models `services/filter/models.py` — модель записи (raw, snapshot, model_spec)
- [x] app `services/filter/app.py` — /record, /text/{episode_id}, /chain/verify
- [x] tests `tests/test_filter_service.py` — барьер «только текст», целостность цепочки
