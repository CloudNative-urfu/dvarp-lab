## 1. Tasks

- [x] tactics-registry `frozen/corpus/tactics.json` — реестр тактик, сгруппированный из корпуса атак
- [x] tactics-module `services/attack/tactics.py` — загрузка/группировка тактик, выбор по имени

- [x] episode-loop `services/attack/episode.py` — цикл эпизода атаки с бюджетом
- [x] attacker `services/attack/attacker.py` — атакующий: корпусный стартовый промпт, ходы только текстом
- [x] app-signals `services/attack/app.py` — /run-episode, /start, /stop
- [x] tests `tests/test_attack.py` — эпизод атаки, бюджет, изоляция
