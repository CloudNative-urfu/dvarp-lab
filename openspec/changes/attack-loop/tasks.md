## 1. Tasks

- [x] tactics-registry `frozen/corpus/tactics.json` — реестр тактик, сгруппированный из корпуса атак
- [x] tactics-module `services/attack/tactics.py` — загрузка/группировка тактик, выбор по имени

- [x] episode-loop `services/attack/episode.py` — цикл эпизода атаки с бюджетом
- [x] attacker `services/attack/attacker.py` — атакующий: корпусный стартовый промпт, ходы только текстом
- [x] app-signals `services/attack/app.py` — /run-episode, /start, /stop
- [x] tests `tests/test_attack.py` — эпизод атаки, бюджет, изоляция

- [x] pair-style Общий стиль пары: тон-клауза атакующему, стартовая реплика корпусная, raw.style
- [x] ext-corpus Социальный сектор тактик (atk-21…28): darp_corpus_v2_ext.jsonl + MANIFEST_ext.json, реестр переgroup
- [x] tests-attack `tests/test_attack.py` — стиль в промпте, пин стиля, расширенный корпус
