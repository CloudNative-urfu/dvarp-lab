## ADDED Requirements

### Requirement: Shared registry SHALL define conversation roles
The registry in `frozen/styles.json` SHALL contain all twenty owner-proposed styles
and preserve the legacy patient, irritated and polite names. Each style SHALL provide
a name, role description and one or two openings. Both legs SHALL use the same registry.

#### Scenario: Enumerate styles
- **WHEN** CLI or UI resolves the styles axis in all, point or set mode
- **THEN** the available names SHALL come from the shared frozen registry

### Requirement: Both live participants SHALL receive the shared tone clause
Legal and attacking LLM clients SHALL receive the selected role description and opening
examples through a common system-prompt clause. Tone SHALL remain separate from legal
facts and the attack method. The attack opening SHALL remain the frozen goal claim.

#### Scenario: Same role in both legs
- **WHEN** a paired campaign requests a style
- **THEN** both participants SHALL receive the same role description without a competing
  generic short/informal instruction or fixed length cap

#### Scenario: Dynamic tone across turns
- **WHEN** an escalating or de-escalating live conversation continues
- **THEN** its role SHALL describe progression over turns and prior messages SHALL remain
  available to the model so it can follow that progression

### Requirement: Stub participants SHALL tolerate optional phrase banks
The confirm, answers and push banks SHALL be optional. Missing or empty banks SHALL
fall back to a neutral set, without requiring live-model calls. The attacker SHALL NOT
receive shop database facts through this fallback.

#### Scenario: Minimal style entry
- **WHEN** a style contains only name, description and openings
- **THEN** legal and attacking stub episodes SHALL run without a missing-bank error

### Requirement: Paired records SHALL identify the selected style
Both episode types SHALL pin their selected style name in raw records. The launcher
SHALL continue sending one style to both legs of each pair.

#### Scenario: Pair with an expanded registry style
- **WHEN** a campaign runs any newly registered style
- **THEN** both legs SHALL receive that name and their raw records SHALL retain it
