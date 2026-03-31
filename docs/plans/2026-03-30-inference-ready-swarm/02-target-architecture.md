# Target Architecture

Date: 2026-03-30
Target: internal research-ready inference for a simulation-backed feature generator

## Architectural intent

The system should treat the simulated marketplace as a feature generator for forecasting, not as a direct substitute for an earned real-world forecast.

The canonical path should become:

`forecast_question -> forecast_workspace -> simulation-backed market run(s) -> simulation-market artifacts -> aggregated forecast signals -> forecast_answer -> report context -> resolution_record -> scoring_event`

## Target properties

### 1. Forecast-question-first

- Every inference-ready run starts from a `forecast_question`.
- The `forecast_workspace` is the canonical container for question state, evidence, workers, prediction ledger, answers, resolution, and scoring.
- Simulation scope is attached to the workspace, not the other way around.

### 2. Simulation-backed market as a feature generator

- Simulation runs produce structured deliberation artifacts.
- Those artifacts represent synthetic beliefs, disagreement, scenario splits, and missing-information signals.
- The synthetic market output is informative but does not automatically become the final forecast.

### 3. Explicit aggregation layer

- Raw simulation-market artifacts are converted into a narrow set of forecast-engine input signals.
- Aggregation logic is versioned, bounded, and inspectable.
- The engine can show which simulation-derived signals influenced the final answer.

### 4. Signal-level provenance

- Every simulation-derived signal carries provenance to simulation, ensemble, run, agent, and message-level origin when available.
- Weak or missing provenance downgrades or excludes the signal.

### 5. Forecast resolution and scoring

- Final forecast answers are resolvable and scorable as forecast objects.
- Scoring is explicit about supported question types and calibration status.

### 6. Forecast-object-first reporting

- Report context starts with the forecast question, current answer, signal summary, and provenance health.
- Simulation narrative, interviews, and descriptive scenario outputs remain supporting context.

## Data planes

### A. Forecast control plane

Primary artifacts:

- `forecast_question.json`
- `workspace_manifest.json`
- `resolution_criteria.json`
- `evidence_bundle.json`
- `forecast_workers.json`
- `prediction_ledger.json`
- `evaluation_cases.json`
- `forecast_answers.json`
- `simulation_worker_contract.json`

Primary modules:

- `backend/app/models/forecasting.py`
- `backend/app/services/forecast_manager.py`
- `backend/app/api/forecast.py`

### B. Simulation-market plane

New artifacts:

- `simulation_market_manifest.json`
- `agent_belief_book.json`
- `belief_update_trace.json`
- `disagreement_summary.json`
- `argument_map.json`
- `market_snapshot.json`
- `missing_information_signals.json`

Primary modules to add:

- `backend/app/models/simulation_market.py`
- `backend/app/services/simulation_market_extractor.py`

Placement:

- per run under the existing simulation/ensemble/run storage tree so they remain co-located with the run that produced them

### C. Signal aggregation plane

New aggregated artifact:

- `simulation_market_summary.json`

Primary modules to add:

- `backend/app/services/simulation_market_aggregator.py`

Signal contract:

- `synthetic_consensus_probability`
- `synthetic_disagreement_index`
- `argument_cluster_distribution`
- `belief_momentum`
- `minority_warning_signal`
- `missing_information_signal`
- `scenario_split_distribution`

### D. Provenance plane

New artifact or embedded object:

- `forecast_signal_provenance` entries attached to each simulation-derived signal

Primary modules to add or extend:

- `backend/app/services/forecast_signal_provenance.py`
- `backend/app/services/grounding_bundle_builder.py`
- `backend/app/services/forecast_manager.py`

Rule:

- `grounding_bundle.json` remains a summary artifact, not the source of truth for signal provenance

### E. Forecast inference plane

Primary modules:

- `backend/app/services/forecast_engine.py`
- `backend/app/services/hybrid_forecast_service.py`

Required behavior:

- explicit simulation-market worker or signal adapter
- contribution tracing
- abstention and downgrade gates
- question-type support boundaries

### F. Resolution and scoring plane

New artifacts:

- `resolution_record.json`
- `scoring_event.json`

Primary modules to add:

- `backend/app/services/forecast_resolution_manager.py`

Supported initial scope:

- binary
- categorical
- numeric only if existing engine support is already stable enough for internal research use

### G. Delivery plane

Backend modules:

- `backend/app/api/forecast.py`
- `backend/app/api/simulation.py`
- `backend/app/api/report.py`
- `backend/app/services/probabilistic_report_context.py`
- `backend/app/services/report_agent.py`

Frontend modules:

- `frontend/src/utils/forecastRuntime.js`
- `frontend/src/utils/probabilisticRuntime.js`
- `frontend/src/components/Step2EnvSetup.vue`
- `frontend/src/components/Step3Simulation.vue`
- `frontend/src/components/ProbabilisticReportContext.vue`
- `frontend/src/components/Step4Report.vue`
- `frontend/src/components/Step5Interaction.vue`

Required hierarchy:

1. forecast question and current answer
2. simulation-market summary and provenance health
3. supporting simulation narrative and legacy analysis tools

## Service interactions

### Step 2

- create or reopen a `forecast_workspace`
- attach or confirm simulation scope
- persist explicit simulation-market readiness expectations

### Step 3

- execute the simulation-backed marketplace run
- extract simulation-market artifacts
- aggregate forecast signals
- write the updated forecast answer and worker outputs

### Step 4

- generate report context from the forecast object first
- include simulation-market summary, provenance health, and supporting scenario evidence

### Step 5

- keep interaction scoped to the same forecast object and report context
- ensure chat and follow-up interactions refer to the same signal and provenance state

## Contracts that must remain explicit

### Non-causal boundary

- cluster share means observed run share, not causal effect
- sensitivity remains observational unless a separate causal layer exists

### Non-calibrated boundary

- synthetic market outputs are not calibrated probabilities by default
- calibrated labels require earned resolution/scoring evidence

### Internal research-ready boundary

- the target is internal research use, not public/external defensibility
- keep scope bounded and truth-preserving

## Non-goals for this architecture phase

- prediction-market implementation
- causal graph/intervention engine
- broad live-web evidence acquisition
- polished external product UX
- cross-simulation portfolio analytics

## Success condition

The architecture is successful when one user can:

1. define a forecast question
2. run the simulation-backed market against that question
3. inspect structured simulation-derived inference signals
4. see those signals influence the forecast answer with provenance and contribution tracing
5. later resolve and score the forecast answer

