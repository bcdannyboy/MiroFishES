# Inference-Ready Gap Analysis

Date: 2026-03-30
Plan scope: internal research-ready inference for a simulation-backed feature generator
Code-only scope: backend/app, frontend/src, backend/tests, frontend/tests, tests/smoke, tests/live

## Executive summary

MiroFishES already contains a substantial forecast foundation. The repo is not starting from zero. It already has:

- a canonical `ForecastQuestion` and `ForecastWorkspaceRecord` contract in `backend/app/models/forecasting.py`
- a filesystem-backed forecast workspace store in `backend/app/services/forecast_manager.py`
- a forecast API in `backend/app/api/forecast.py`
- a hybrid forecast engine with worker traces in `backend/app/services/forecast_engine.py`
- forecast runtime helpers in `frontend/src/utils/forecastRuntime.js`
- existing unit coverage for forecast schema, manager, API, engine, hybrid service, and probabilistic report context

The main gap is narrower and more specific:

- the simulation-backed marketplace does not yet emit structured inference artifacts as first-class objects
- the hybrid forecast engine still treats simulation as supporting `scenario_context`, not as a structured signal source
- provenance exists for bundles and artifacts, but not at signal level
- the final forecast lifecycle does not yet have explicit `resolution_record` and `scoring_event` artifacts
- report and operator surfaces still lead with the legacy simulation/report workflow instead of the forecast object

This means the repo is already forecast-foundation-capable, but not yet inference-ready under the intended framing.

## Current code truth

### 1. Forecast question is primary

Status: partial

What exists:

- `backend/app/models/forecasting.py` defines `ForecastQuestion`, `ResolutionCriteria`, `PredictionLedger`, `ForecastAnswer`, `SimulationWorkerContract`, and `ForecastWorkspaceRecord`.
- `backend/app/api/forecast.py` supports a question-first flow and can create a workspace from a question payload.
- `backend/app/services/forecast_manager.py` persists forecast workspaces in `backend/uploads/forecasts`.
- `backend/app/services/probabilistic_report_context.py` can surface linked forecast questions and a workspace summary for a simulation.

What blocks full truth:

- `backend/app/services/simulation_manager.py` still prepares the legacy `simulation_config.json` runtime first and only then writes probabilistic sidecars.
- Step 2 and Step 3 remain centered on simulation prepare/run semantics rather than forecast workspace semantics.
- `backend/app/services/report_agent.py` still generates a simulation scenario report first and treats the forecast workspace as secondary context.

Gap statement:

- The forecast object model exists.
- The operator/runtime flow still starts from simulation scope and only partially re-centers around the forecast object.

### 2. Simulation-backed marketplace emits structured inference signals

Status: missing

What exists:

- `backend/app/services/simulation_runner.py` runs ensembles and persists run outputs.
- `backend/app/services/ensemble_manager.py` persists ensemble metadata, aggregate summaries, cluster summaries, and sensitivity outputs.
- `backend/app/services/scenario_clusterer.py` and `backend/app/services/sensitivity_analyzer.py` expose descriptive post-run analytics.

What is missing:

- no dedicated simulation-market artifact schema
- no persisted per-agent belief book
- no structured belief update trace
- no disagreement summary built from simulated discourse
- no argument map or missing-information artifact extracted from agent conversation
- no explicit synthetic market snapshot object

Gap statement:

- The code can run scenarios and summarize outcomes.
- It cannot yet convert simulated discussion into structured inference data.

### 3. Simulation-derived signals feed the forecast engine as first-class inputs

Status: partial

What exists:

- `backend/app/services/forecast_engine.py` already supports worker families and produces a `worker_contribution_trace`.
- The engine already includes a simulation worker via `SimulationWorkerContract`.
- The engine already distinguishes `scenario_context` from the defended hybrid estimate.

What blocks full truth:

- the simulation worker currently loads observed shares or distribution payloads from ensemble outputs
- its contribution role is intentionally limited to `scenario_context`
- the engine has no dedicated worker family for simulation-market inference signals
- no explicit signal contract exists for disagreement, belief momentum, minority warnings, or missing-information flags

Gap statement:

- the engine is structurally ready to accept more workers
- the simulation-backed feature generator does not yet have a first-class signal path into the engine

### 4. Provenance exists at signal level

Status: partial-to-missing

What exists:

- `backend/app/services/grounding_bundle_builder.py` can build a bounded grounding/provenance bundle from `source_manifest.json` and `graph_build_summary.json`
- `backend/app/services/forecast_manager.py` can build local evidence bundle entries and link evidence bundles to questions and prediction entries
- `backend/app/services/probabilistic_report_context.py` already exposes bounded confidence and evidence context to Step 4 and Step 5

What blocks full truth:

- provenance is attached at artifact/bundle level, not forecast-signal level
- no signal object currently points back to simulation run, agent, turn, message index, or supporting evidence span
- no validator currently rejects simulation-derived signals with missing or weak provenance

Gap statement:

- provenance bookkeeping exists
- signal-level provenance enforcement does not

### 5. Final forecast can be resolved and scored

Status: partial

What exists:

- `ForecastWorkspaceRecord` already includes `evaluation_cases`, `prediction_ledger`, and `forecast_answers`
- `backend/app/services/forecast_engine.py` already emits evaluation-oriented payloads and confidence metadata
- forecast API and tests already cover parts of the issue/revision/evaluation flow

What blocks full truth:

- there is no explicit `resolution_record.json`
- there is no explicit `scoring_event.json`
- the binary-only probabilistic backtest/calibration lane is narrower than the broader forecast workspace model
- confidence semantics are split between forecast workspace logic and legacy probabilistic calibration artifacts

Gap statement:

- scoring concepts exist
- an explicit forecast-resolution lifecycle artifact model still needs to be built

### 6. Reports consume forecast artifacts first, simulation narrative second

Status: partial

What exists:

- `backend/app/services/probabilistic_report_context.py` already includes a forecast workspace block
- `backend/app/services/report_agent.py` already knows how to summarize a forecast workspace into a prompt-safe payload
- frontend Step 4 and Step 5 already render hybrid workspace context

What blocks full truth:

- `backend/app/services/report_agent.py` is still authored around simulation requirements, interviews, and simulation-report section planning
- the report body is still simulation-report-first
- the forecast workspace is additive context instead of the lead object
- Step 4 and Step 5 still inherit the old report-first interaction model

Gap statement:

- the forecast workspace is visible
- the report and UI hierarchy still put the simulation report ahead of the inference object

## Code assets that reduce implementation risk

- `backend/app/models/forecasting.py` already encodes rich question, worker, ledger, evidence, and answer contracts.
- `backend/app/api/forecast.py` already exposes creation and update entry points for question-first flows.
- `backend/app/services/forecast_manager.py` already persists workspaces, bundles, question summaries, and evidence links.
- `backend/app/services/forecast_engine.py` already has worker-family dispatch, contribution tracing, abstention behavior, and output semantics.
- `frontend/src/utils/forecastRuntime.js` and `frontend/tests/unit/forecastRuntime.test.mjs` already normalize and render forecast workspace concepts.
- `backend/tests/unit/test_forecast_api.py`, `test_forecast_manager.py`, `test_forecast_engine.py`, `test_forecasting_schema.py`, and `test_probabilistic_report_context.py` already cover much of the existing forecast foundation.

## Gaps to close for internal research-ready inference

### A. Canonical forecast control plane alignment

Need:

- explicit forecast-workspace-first Step 2/3 path
- strong linkage between `forecast_id`, `simulation_id`, `ensemble_id`, and run scope
- cleanup of remaining contract drift between forecast and probabilistic prepare surfaces

### B. Simulation-market extraction artifacts

Need new artifacts for:

- per-agent forecast judgment
- per-agent uncertainty/confidence expression
- belief updates over time
- disagreement summary
- argument clusters or rationale tags
- synthetic market snapshot
- missing-information flags

### C. Signal schema

Need a versioned schema for engine-consumable signals such as:

- `synthetic_consensus_probability`
- `synthetic_disagreement_index`
- `belief_momentum`
- `minority_warning_signal`
- `missing_information_signal`
- `scenario_split_distribution`

### D. Aggregation and forecast-engine integration

Need:

- a simulation-market aggregation service
- explicit worker family or signal ingestion path in `forecast_engine.py`
- contribution tracing for simulation-derived inference, not just simulation scenario context

### E. Signal-level provenance and validation

Need:

- signal-level provenance objects
- validation and gating rules
- clear downgrade or abstention behavior when provenance is weak

### F. Resolution and scoring lifecycle

Need:

- dedicated `resolution_record` artifact
- dedicated `scoring_event` artifact
- one forecast-scoring path that is explicit about supported question types and earned confidence semantics

### G. Forecast-object-first reporting and operator flow

Need:

- report context that leads with the forecast object
- report agent planning that starts from forecast + provenance + simulation-market summary
- Step 2/3/4/5 hierarchy that shows the inference object before the narrative report

### H. Verification ladder

Need:

- unit tests for new simulation-market contracts and extraction
- integration test for `question -> simulation -> extracted signals -> forecast answer`
- Step 4/5 UI/runtime tests that assert forecast-object-first behavior

## Truthfulness boundaries that must remain explicit

These boundaries are required for internal research-ready inference and must remain encoded in code and UI language:

- Scenario clustering remains descriptive and observational, not causal.
- Sensitivity analysis remains observational unless a separate causal system is introduced.
- Simulation-derived signals are not automatically calibrated real-world probabilities.
- Confidence remains uncalibrated unless resolution/scoring evidence earns a stronger label.
- The simulation-backed marketplace is one inference mechanism, not the sole source of truth.

## Migration and implementation risks

### Existing contract drift

- `backend/app/services/simulation_manager.py` defines `forecast_brief.json` but does not require it in `REQUIRED_PROBABILISTIC_ARTIFACT_KEYS`.
- `backend/app/services/probabilistic_report_context.py` defines `_build_forecast_workspace_context` twice.

### Runtime coupling

- the current runtime still depends on the legacy simulation config and subprocess execution path
- Step 2/3 APIs are still simulation-centric

### Semantic split risk

- the repo already distinguishes forecast workspace semantics from binary-only probabilistic calibration artifacts
- any new scoring/resolution work must avoid collapsing these two lanes into misleading one-word confidence claims

### Compatibility risk

- existing smoke and local operator tests assume Step 4/5 still expose simulation support language
- the new path must preserve legacy behavior while adding the forecast-object-first path

## Scope that can be deferred without blocking inference-readiness

- cross-simulation compare expansion
- prediction-market mechanics
- causal graph or intervention-analysis claims
- broad numeric forecast sophistication beyond a narrow supported path
- major UI polish
- external/live retrieval improvements

## Bottom line

The repo already has a real forecast foundation. The shortest path to inference-readiness is not a rewrite. It is:

1. keep the existing forecast workspace model
2. add simulation-market extraction artifacts
3. aggregate those artifacts into explicit forecast signals
4. feed those signals into the forecast engine with provenance gating
5. make the report and UI consume the forecast object first

