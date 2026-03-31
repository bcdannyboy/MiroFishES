# Task Graph

Date: 2026-03-30
Plan scope: internal research-ready inference for a simulation-backed feature generator
Active swarm: `swarm-1774818185510-bscyl8`

## Ownership slices

- Dirac: architecture and forecast control plane
- Lagrange: simulation-market extraction and aggregation
- Arendt: semantics, provenance, and truthfulness boundaries
- Volta: report/API/frontend integration
- Carver: verification, smoke, and end-to-end validation
- Curie: resolution/scoring and narrow technical research support

## Dependency summary

| Phase | Title | Owner | Depends on |
| --- | --- | --- | --- |
| P1 | Canonical forecast control plane | Dirac | none |
| P2 | Simulation-market extraction artifacts | Lagrange | P1 |
| P3 | Signal schema and semantics | Arendt | P1 |
| P4 | Simulation-market aggregation | Lagrange | P2, P3 |
| P5 | Forecast-engine integration | Dirac | P4 |
| P6 | Provenance and signal validation | Arendt | P2, P3, P4 |
| P7 | Resolution and scoring lifecycle | Curie | P1, P5 |
| P8 | Report/API/frontend integration | Volta | P1, P5, P6, P7 |
| P9 | Verification ladder and end-to-end inference path | Carver | P1-P8 |
| P10 | Semantic debt cleanup blocking truthfulness | Dirac, Arendt | P1-P9, may run small fixes earlier when necessary |

## P1. Canonical forecast control plane

Owner: Dirac
Priority: critical
Dependencies: none

### Goal

Make the inference-ready path explicitly forecast-workspace-first while preserving backward compatibility for the legacy simulation path.

### Files to modify

- `backend/app/models/forecasting.py`
- `backend/app/services/forecast_manager.py`
- `backend/app/services/hybrid_forecast_service.py`
- `backend/app/services/simulation_manager.py`
- `backend/app/api/forecast.py`
- `backend/app/api/simulation.py`

### Files to create if needed

- none required if the current forecast foundation can be extended in place

### Tests to add before implementation

- extend `backend/tests/unit/test_forecasting_schema.py`
- extend `backend/tests/unit/test_forecast_manager.py`
- extend `backend/tests/unit/test_forecast_api.py`
- extend `backend/tests/integration/test_probabilistic_operator_flow.py`

### Acceptance criteria

- the inference-ready path can create or reopen a forecast workspace first
- `forecast_id` is explicitly linked to simulation scope
- Step 2/3 APIs can operate from workspace context
- no contract ambiguity remains about the canonical lifecycle for inference-ready runs

### Migration risks

- keep legacy simulation-only routes working
- avoid breaking existing forecast workspace schema round-trips
- preserve existing `primary_simulation_id` semantics

### Deferred scope

- cross-simulation portfolio management

## P2. Simulation-market extraction artifacts

Owner: Lagrange
Priority: critical
Dependencies: P1

### Goal

Extract structured simulation-market artifacts from simulated marketplace discourse and run outputs.

### Files to create

- `backend/app/models/simulation_market.py`
- `backend/app/services/simulation_market_extractor.py`

### Files to modify

- `backend/app/services/simulation_runner.py`
- `backend/app/services/ensemble_manager.py`
- `backend/app/services/probabilistic_report_context.py`

### Tests to add before implementation

- `backend/tests/unit/test_simulation_market_schema.py`
- `backend/tests/unit/test_simulation_market_extractor.py`
- extend `backend/tests/unit/test_simulation_runner_runtime_scope.py`
- extend `backend/tests/unit/test_simulation_runner_run_scope.py`

### Required artifacts

- `simulation_market_manifest.json`
- `agent_belief_book.json`
- `belief_update_trace.json`
- `disagreement_summary.json`
- `argument_map.json`
- `market_snapshot.json`
- `missing_information_signals.json`

### Acceptance criteria

- a completed run can emit persisted simulation-market artifacts
- artifacts are versioned and machine-readable
- artifacts link back to forecast/workspace/run scope
- initial support is bounded to binary and categorical question types unless numeric is clearly safe

### Migration risks

- extraction must not depend on report generation
- extraction must not break existing run storage layout

### Deferred scope

- complex market mechanics
- full numeric discourse extraction

## P3. Signal schema and semantics

Owner: Arendt
Priority: critical
Dependencies: P1

### Goal

Define the simulation-derived inference signal contract and preserve truthfulness boundaries.

### Files to modify

- `backend/app/models/forecasting.py`

### Files to create

- `backend/app/models/simulation_market.py`

### Tests to add before implementation

- `backend/tests/unit/test_simulation_market_schema.py`
- extend `backend/tests/unit/test_forecasting_schema.py`

### Required signal contract

- `synthetic_consensus_probability`
- `synthetic_disagreement_index`
- `argument_cluster_distribution`
- `belief_momentum`
- `minority_warning_signal`
- `missing_information_signal`
- `scenario_split_distribution`

### Truthfulness boundaries to encode

- descriptive within-simulation does not imply real-world probability
- observational scenario analytics are not causal
- calibrated labels are unavailable until earned by scoring evidence

### Acceptance criteria

- signal schema is explicit and versioned
- supported question types and semantics are encoded in code
- non-causal and non-calibrated boundaries are explicit in the contract

### Deferred scope

- public-facing calibration claims
- causal semantics

## P4. Simulation-market aggregation

Owner: Lagrange
Priority: high
Dependencies: P2, P3

### Goal

Convert raw simulation-market artifacts into stable engine-consumable signal summaries.

### Files to create

- `backend/app/services/simulation_market_aggregator.py`

### Files to modify

- `backend/app/models/simulation_market.py`
- `backend/app/services/forecast_manager.py`

### Tests to add before implementation

- `backend/tests/unit/test_simulation_market_aggregator.py`

### Acceptance criteria

- one bounded `simulation_market_summary` is derivable from extracted artifacts
- aggregation rules are deterministic and inspectable
- summary includes consensus, dispersion, minority warnings, missing-information flags, and scenario split structure

### Migration risks

- avoid hidden heuristics that cannot be audited
- keep aggregation independent from report formatting

## P5. Forecast-engine integration

Owner: Dirac
Priority: critical
Dependencies: P4

### Goal

Make simulation-derived signals first-class inputs to the hybrid forecast engine.

### Files to modify

- `backend/app/services/forecast_engine.py`
- `backend/app/services/hybrid_forecast_service.py`
- `backend/app/services/forecast_manager.py`
- `backend/app/models/forecasting.py`

### Tests to add before implementation

- extend `backend/tests/unit/test_forecast_engine.py`
- extend `backend/tests/unit/test_hybrid_forecast_service.py`

### Required behavior

- explicit worker or adapter for simulation-market signals
- contribution tracing for simulation-derived inference
- abstention and downgrade rules for high disagreement, weak provenance, and unsupported question types

### Acceptance criteria

- simulation-derived signals can influence the final forecast answer
- the final answer exposes a trace of which simulation-derived signals contributed
- simulation remains one inference source, not an implicit claim of calibrated truth

### Migration risks

- preserve the existing supporting-scenario behavior until the new path is complete
- avoid regressing existing non-simulation worker logic

## P6. Provenance and signal validation

Owner: Arendt
Priority: critical
Dependencies: P2, P3, P4

### Goal

Attach provenance at signal level and reject or downgrade weak signals.

### Files to create

- `backend/app/services/forecast_signal_provenance.py`

### Files to modify

- `backend/app/services/simulation_market_extractor.py`
- `backend/app/services/simulation_market_aggregator.py`
- `backend/app/services/grounding_bundle_builder.py`
- `backend/app/services/forecast_manager.py`
- `backend/app/services/probabilistic_report_context.py`

### Tests to add before implementation

- `backend/tests/unit/test_forecast_signal_provenance.py`
- extend `backend/tests/unit/test_forecast_grounding.py`
- extend `backend/tests/unit/test_probabilistic_report_context.py`

### Required provenance fields

- `forecast_id`
- `simulation_id`
- `ensemble_id`
- `run_id`
- `agent_id`
- `turn_index`
- `message_index`
- source or artifact reference
- graph reference when applicable

### Acceptance criteria

- each simulation-derived signal can be traced to an origin
- invalid or incomplete provenance prevents full contribution
- provenance health is available to reporting and UI layers

### Deferred scope

- live external provenance acquisition

## P7. Resolution and scoring lifecycle

Owner: Curie
Priority: high
Dependencies: P1, P5

### Goal

Create explicit forecast resolution and scoring artifacts for the final forecast object.

### Files to create

- `backend/app/services/forecast_resolution_manager.py`

### Files to modify

- `backend/app/models/forecasting.py`
- `backend/app/services/forecast_manager.py`
- `backend/app/api/forecast.py`
- `backend/app/services/forecast_engine.py`

### Tests to add before implementation

- `backend/tests/unit/test_forecast_resolution_manager.py`
- extend `backend/tests/unit/test_forecast_api.py`
- extend `backend/tests/unit/test_forecast_manager.py`

### Required artifacts

- `resolution_record.json`
- `scoring_event.json`

### Acceptance criteria

- the final forecast answer can be resolved explicitly
- scoring events are persisted explicitly
- supported question types and scoring semantics are explicit
- earned confidence semantics are separated from unsupported calibration claims

### Deferred scope

- broad calibration dashboards
- advanced market scoring

## P8. Report/API/frontend integration

Owner: Volta
Priority: high
Dependencies: P1, P5, P6, P7

### Goal

Make the forecast object, simulation-market summary, and provenance health the primary delivery surface.

### Files to modify

- `backend/app/api/forecast.py`
- `backend/app/api/simulation.py`
- `backend/app/api/report.py`
- `backend/app/services/probabilistic_report_context.py`
- `backend/app/services/report_agent.py`
- `frontend/src/utils/forecastRuntime.js`
- `frontend/src/utils/probabilisticRuntime.js`
- `frontend/src/components/Step2EnvSetup.vue`
- `frontend/src/components/Step3Simulation.vue`
- `frontend/src/components/ProbabilisticReportContext.vue`
- `frontend/src/components/Step4Report.vue`
- `frontend/src/components/Step5Interaction.vue`

### Tests to add before implementation

- extend `backend/tests/unit/test_probabilistic_report_context.py`
- extend `backend/tests/unit/test_probabilistic_report_api.py`
- extend `frontend/tests/unit/forecastRuntime.test.mjs`
- extend `frontend/tests/unit/probabilisticRuntime.test.mjs`

### Acceptance criteria

- Step 2 can create/select a forecast question or workspace
- Step 3 surfaces simulation-market summary, disagreement, and provenance health
- Step 4 leads with the forecast object
- Step 5 keeps interactions scoped to the same forecast/provenance object
- the report agent consumes forecast-first context rather than simulation-report-only context

### Migration risks

- preserve legacy UI paths while the new path lands
- avoid breaking smoke selectors already used by existing tests

## P9. Verification ladder and end-to-end inference path

Owner: Carver
Priority: critical
Dependencies: P1-P8

### Goal

Prove the inference-ready path with automated coverage and one bounded end-to-end path.

### Files to create

- `backend/tests/integration/test_inference_ready_forecast_flow.py`

### Files to modify

- `backend/tests/integration/test_probabilistic_operator_flow.py`
- `tests/smoke/probabilistic-runtime.spec.mjs`
- `tests/live/probabilistic-operator-local.spec.mjs`

### Required validation layers

- backend unit coverage for new models, extraction, aggregation, provenance, resolution, and engine integration
- backend integration for `question -> simulation -> signals -> forecast answer`
- frontend runtime coverage for forecast-object-first behavior
- smoke and local operator checks updated for the new path

### Acceptance criteria

- one automated path proves end-to-end inference behavior
- no touched forecast/probabilistic suites regress
- readiness gates are machine-checkable before the final prompt in the chain

### Deferred scope

- large-scale benchmark evaluation

## P10. Semantic debt cleanup blocking truthfulness

Owners: Dirac, Arendt
Priority: high
Dependencies: may run tiny unblockers early, must close before final readiness claim

### Goal

Remove code-level ambiguity that would otherwise undermine truthfulness and maintainability.

### Files to modify

- `backend/app/services/probabilistic_report_context.py`
- `backend/app/services/simulation_manager.py`
- `backend/app/services/report_agent.py`
- `backend/app/services/forecast_engine.py`
- any touched API/runtime helpers with duplicated or drifting truthfulness logic

### Known cleanup targets

- remove duplicate `_build_forecast_workspace_context` definitions
- align probabilistic prepare contracts with actual required artifacts
- ensure simulation-derived inference language is distinct from descriptive scenario language
- keep non-causal and non-calibrated boundaries explicit in code paths

### Tests to add or update

- extend `backend/tests/unit/test_probabilistic_prepare.py`
- extend `backend/tests/unit/test_probabilistic_report_context.py`
- extend `backend/tests/unit/test_forecast_engine.py`

### Acceptance criteria

- no code-level truthfulness drift remains in the inference-ready path
- contracts and naming are consistent enough that the final readiness prompt can fail closed reliably

## Implementation order

1. P1
2. P2 and P3 in parallel
3. P4
4. P5 and P6
5. P7
6. P8
7. P9
8. P10 final cleanup and truthfulness pass

## Exit condition for Prompt 1

Prompt 1 is complete when:

- this task graph is present
- the swarm board mirrors these tasks with owners and dependencies
- the local Ruflo task state contains the same task set
- Prompt 2 can start immediately without human interpretation

