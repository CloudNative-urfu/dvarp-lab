## Why

Issue: https://github.com/CloudNative-urfu/dvarp-lab/issues/50.

`legal_episode_id` (`{run}-L{i}-{style}-s{seed}`) не содержит сценарных осей
ячейки: все легальные ноги одного прогона (один run/стиль/сид) сворачиваются
метриками в один эпизод — ходы пулятся, финал переживает последнюю ногу
(upsert `/finalize`), `n_legal` = 1–2 вместо реальных, `E_legal`/`G_tau`
искажаются (найдено на живой мини-кампании: `mini-campaign-2026-11-27`,
54 ноги → 1 «эпизод», `G_tau_rate=1.0` как артефакт).

## What Changes

- `legal_episode_id` зеркалит `attack_signature` ячейки (`{run}-L{i}-{goal}-{style}-{tactic}-s{seed}`):
  уникальность ячейки + аудируемая парность — id обеих ног пары отличаются
  только маркером L/A; манифест и `/finals` ссылаются на новый id.

## Capabilities

### New Capabilities
- `legal-episode-id`: уникальный id легальной ноги с сигнатурой ячейки.

## Impact

- launcher/campaign.py (id пары, манифест), тесты кампании; старые прогоны
  не пересчитываются (raw остаётся как записан); `/finalize`-upsert без изменений.
