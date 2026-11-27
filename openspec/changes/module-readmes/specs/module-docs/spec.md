## ADDED Requirements

### Requirement: Major modules SHALL provide researcher-facing READMEs
Each of services/shop, services/filter, services/metrics, services/traffic,
services/attack, lab, frozen, launcher and services/ui SHALL have a Russian README.
It SHALL describe purpose, inputs/outputs with an API link, storage/schema,
collected fields or metrics, invariants/limitations, a code map and verification commands.

#### Scenario: Research a module without reading its implementation
- **WHEN** a researcher opens a major module README
- **THEN** they SHALL be able to trace its data sources, outputs and ownership
  of stored state, distinguishing runtime observations from post-hoc calculations

### Requirement: Implementation statements SHALL link to source evidence
Module READMEs SHALL identify their source revision and support implementation
statements with relative source links, line anchors and named functions.
Known audit findings SHALL be distinguished from implemented guarantees.

#### Scenario: An audit identifies an unsupported guarantee
- **WHEN** a documented contract is stronger than the current implementation
- **THEN** the README SHALL identify the limitation and link to the issue or report,
  without claiming that documentation fixes the underlying code

### Requirement: Behavior-changing PRs SHALL maintain module documentation
A PR changing a module's documented behavior, interfaces, schemas, fields or files
SHALL update its README in the same PR, or explain why the documented facts remain
unchanged. Cross-module changes SHALL maintain both sides and navigation.
The agent manual SHALL state this documentation discipline.

#### Scenario: A storage field changes
- **WHEN** a PR changes a field consumed by another module
- **THEN** affected README schemas and source references SHALL be updated together

### Requirement: The root README SHALL index module documentation
The root README SHALL link to all major module READMEs. The documentation series
SHALL be published as one module per PR, with the maintenance rule in the first
and a final comparison against the available audit #43 report.

#### Scenario: Finish the documentation series
- **WHEN** the final module PR is prepared
- **THEN** the root index SHALL resolve to existing module READMEs and the audit
  comparison SHALL identify the code revision and unresolved findings
