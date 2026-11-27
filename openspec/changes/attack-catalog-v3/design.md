# Design — attack-catalog-v3

- **Источник иллюстраций**: 124 новые записи `darp_corpus_v3.jsonl` (atk-29…152,
  по одной на иллюстрацию) — сохраняют происхождение и dev/holdout-сплит реестра
  (`len(illustrations) == len(entries) > 0`); формат записи и манифест — по
  прецеденту ext-корпуса (`dvarp.corpus-ext/1` → `dvarp.corpus-v3/1`): file +
  sha256 + entry_hashes (canonical JSON) + coverage + source_note;
- **Вне рантайма**: `load_corpus()` читает только базовый корпус; v3 —
  замороженный артефакт происхождения (как ext), загрузчик реестра
  (`tactics.load_tactics`) не валидирует корпус;
- **Оси записей**: axes.goal — лабовые цели (goals.json), не прототипная ось
  break/burn/slow (ext-прецедент продолжен, отметка в source_note);
  attack-only без контрольных пар — как ext;
- **Фокус семей** (по данным живой калибровки): манипуляция суммой/количеством
  — единственная доказанная брешь промпта агента (7/8 успехов на
  `refund_overprice`); planted context — прямой вызов прививки п.2 промпта
  (untrusted data); давление — под сессии ≤6 ходов.
