## ADDED Requirements

### Requirement: Demo maps render
Скрипт `scripts/demo_maps.py` SHALL рендерить пять SVG-карт метрик
(конфигурация × метрика; break-even L*/L_viol; L* реального фрейма по p_att;
G-τ с Wilson 95% CI и порогом 5%; Pareto V ↔ R+G-τ) из `/metrics/{config}`
metrics_svc в каталог `--out`, вместе с `index.html` и дампом сырых чисел.
Скрипт SHALL не изменять сырую и метрическую БД; группы моделей SHALL не
схлопываться.

#### Scenario: Render from metrics service
- **WHEN** скрипт запускается с доступной metrics_svc
- **THEN** каталог вывода содержит 5 SVG, index.html и metrics_dump.json;
  БД не изменены

#### Scenario: Model groups preserved
- **WHEN** у конфигурации несколько групп model_spec (агент/атакующий,
  разные пины)
- **THEN** каждая группа отображается отдельной строкой/колонкой
