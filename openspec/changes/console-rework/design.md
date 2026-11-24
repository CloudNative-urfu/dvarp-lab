# Design: console-rework

## Решения

- **Vue global build, не Preact+htm/Alpine.** Один файл, MIT в шапке (htm —
  Apache-2.0), шаблоны прямо в `index.html`, компоненты без билда.
- **Описание формы — `describe.py`, не `/api/meta` inline.** Оси берутся из
  `launcher.axes` (тот же источник, что у CLI); пресеты — полные спецификации
  осей, поэтому их проверяет `/api/volume` в тестах.
- **Состояние формы = спецификация осей.** Фронт держит запасные ключи всех
  режимов и при отправке берёт ключи текущего режима (`MODE_KEYS`) — это
  формат launcher, не логика.
- **Preview в metrics_svc.** Расчёт остаётся только в metrics: `/preview` и
  `/compute` используют общий `_computed`, `/preview` не открывает сессию
  записи.
- **Диалог в filter_svc.** Реплика клиента живёт только в `raw.events` записи
  shop; `/dialog` вынимает из них сообщения канала (`to_defender` →
  customer, `to_attacker` → agent) и ничего больше; `/text` не тронут.
- **Свой listbox вместо `<select>`.** Одна компонента `pick` с клавиатурой
  (стрелки, Enter, Escape) и ARIA listbox для всех выпадающих списков.
