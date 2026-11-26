## Why

Issue: [CloudNative-urfu/dvarp-lab#21](https://github.com/CloudNative-urfu/dvarp-lab/issues/21).

В реестре плагинов есть три LLM-гварда (Qwen3Guard-Gen-4B, Granite Guardian 3.1-2B,
Llama Guard 3 8B), но в замороженной матрице их не было: эндпоинта для моделей-детекторов
не было, а shop не передавал модели в хост гвардрейлов. Тариф `guard_tariff` (#11)
без них ничего не измерял.

## What Changes

- три замороженные конфигурации `g_in_qwen`, `g_in_granite`, `g_in_llama`: позиция
  `input` занята LLM-детектором, политика — как у `g_in` (canon_escalate). Сравнение
  детекторов внутри позиции, при одинаковой политике; перебор — штатной осью `configs`,
  отдельной оси нет (правка владельца 2026-11-26);
- shop собирает модели LLM-гвардов из `LAB_GUARD_LLM_BASE_URL` (+ `LAB_GUARD_LLM_API_KEY`):
  один OpenAI-совместимый сервер, модель выбирается закреплённым параметром плагина
  `model`; `/configure` такой конфигурации без эндпоинта отвечает 400; не-локальный
  эндпоинт маркирует прогон remote;
- манифест кампании получает `guard_budget`: на эпизод — вызовы (стадии × ходы),
  потолок выходных токенов (≤64/8/32 на вызов) и его цена по `guard_tariff`;
  промпт и итоговый C_guard измеряются журналом post-hoc (#11);
- `configs.lock.json` дополнен тремя записями, `set_fingerprint` пересчитан.

## Capabilities

### New Capabilities
- `llm-input-guards`: LLM-детекторы на позиции input как замороженные конфигурации.

## Impact

- матрица: 25 → 28 конфигураций; `configs: all` включает LLM-гварды и требует
  `LAB_GUARD_LLM_BASE_URL`;
- `defense_code` в lock не пересчитывался: в lab нет кода заморозки прототипа.
