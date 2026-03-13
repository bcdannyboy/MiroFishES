# Stochastic Probabilistic Simulation Backend Workstreams

**Date:** 2026-03-08

## 1. Purpose

This document decomposes backend delivery into phases, tasks, and subtasks with explicit dependencies and parallelization guidance.

Detailed execution reference:

- for task-by-task purpose, inputs, outputs, acceptance criteria, and evidence requirements, use `docs/plans/2026-03-08-stochastic-probabilistic-backend-task-register.md`

## 2. Backend scope

Primary files and modules in scope:

- `backend/app/models/project.py`
- `backend/app/models/task.py`
- `backend/app/services/simulation_config_generator.py`
- `backend/app/services/simulation_manager.py`
- `backend/app/services/simulation_runner.py`
- `backend/app/services/report_agent.py`
- `backend/app/services/oasis_profile_generator.py`
- `backend/app/services/graph_builder.py`
- `backend/app/services/zep_entity_reader.py`
- `backend/app/services/zep_tools.py`
- `backend/app/api/simulation.py`
- `backend/app/api/report.py`
- `backend/app/api/graph.py`
- `backend/scripts/run_parallel_simulation.py`
- `backend/scripts/run_twitter_simulation.py`
- `backend/scripts/run_reddit_simulation.py`
- `backend/scripts/action_logger.py`

Likely new modules:

- `backend/app/models/probabilistic.py`
- `backend/app/services/uncertainty_resolver.py`
- `backend/app/services/ensemble_manager.py`
- `backend/app/services/outcome_extractor.py`
- `backend/app/services/scenario_clusterer.py`
- `backend/app/services/sensitivity_analyzer.py`
- `backend/app/services/calibration_manager.py`

## 3. Current implementation constraints

### C1: The backend is single-run at almost every layer

`simulation_id` is the root identity for:

- prepare output,
- runtime state,
- log discovery,
- DB reads,
- report lookup,
- IPC interview and environment control.

Planning implication:

- run-scoping is not a localized runtime change. It is a cross-cutting backend refactor.

### C2: The implementation plan assumes pytest, but the test tree does not exist yet

`pytest` is declared in `backend/pyproject.toml`, but `backend/tests/` does not exist today.

Planning implication:

- test scaffolding is a real Phase 0 task, not an afterthought.

## 4. Phase B0: Contract and artifact foundation

### Task B0.0: Create backend test harness scaffolding

**Depends on:** none

**Parallelizable:** yes

**Blocks:** every task that claims new pytest coverage

**Files:**

- create `backend/tests/unit/`
- create `backend/tests/conftest.py`

**Subtasks:**

- B0.0.a Create backend test directory structure.
- B0.0.b Add shared temp-dir fixtures for simulation artifact tests.
- B0.0.c Add helper fixtures for prepared simulation roots, ensemble roots, and run roots.
- B0.0.d Confirm pytest execution path assumptions from repo root vs backend root.

### Task B0.1: Finalize probabilistic artifact taxonomy

**Depends on:** none

**Parallelizable:** yes

**Blocks:** B1.1, B1.2, B2.1, B3.1, B4.1

**Deliverables:**

- canonical artifact names,
- directory layout,
- identifier naming rules,
- seed policy,
- status model.

**Subtasks:**

- B0.1.a Define `simulation_id`, `ensemble_id`, and `run_id` semantics.
- B0.1.b Define file names: `simulation_config.base.json`, `uncertainty_spec.json`, `ensemble_spec.json`, `resolved_config.json`, `run_manifest.json`, `metrics.json`.
- B0.1.c Define which artifacts are immutable after creation.
- B0.1.d Define backward-compatibility rules for legacy `simulation_config.json`.

### Task B0.2: Finalize backend JSON schema contracts

**Depends on:** B0.1

**Parallelizable:** partially

**Blocks:** B1.1, B1.3, B2.2, B3.2, B4.2

**Deliverables:**

- field schemas for probabilistic models,
- ensemble summaries,
- scenario clusters,
- sensitivity artifacts,
- report context artifacts.

**Subtasks:**

- B0.2.a Define `RandomVariableSpec`.
- B0.2.b Define `EnsembleSpec`.
- B0.2.c Define `RunManifest`.
- B0.2.d Define `OutcomeMetricDefinition`.
- B0.2.e Define `AggregateSummary`.
- B0.2.f Define `ScenarioCluster`.

## 5. Phase B1: Preparation-path probabilistic foundation

### Task B1.1: Add probabilistic schema module

**Depends on:** B0.2

**Parallelizable:** yes

**Blocks:** B1.2, B1.3, B2.1

**Files:**

- create `backend/app/models/probabilistic.py`

**Subtasks:**

- B1.1.a Add dataclasses for uncertainty specs.
- B1.1.b Add serialization helpers.
- B1.1.c Add validation rules for supported distributions.
- B1.1.d Add seed-policy structure.

### Task B1.2: Split baseline config from uncertainty spec

**Depends on:** B1.1

**Parallelizable:** no

**Blocks:** B1.3, B2.1, B2.2

**Files:**

- modify `backend/app/services/simulation_config_generator.py`
- modify `backend/app/services/simulation_manager.py`

**Subtasks:**

- B1.2.a Write `simulation_config.base.json`.
- B1.2.b Persist `uncertainty_spec.json`.
- B1.2.c Persist `prepared_snapshot.json`.
- B1.2.d Preserve legacy `simulation_config.json` generation for non-probabilistic mode.
- B1.2.e Add version fields to new artifacts.

### Task B1.3: Extend prepare API for probabilistic mode

**Depends on:** B1.1, B1.2

**Parallelizable:** yes with B1.4

**Blocks:** frontend Step 2 final API wiring

**Files:**

- modify `backend/app/api/simulation.py`

**Subtasks:**

- B1.3.a Add `probabilistic_mode` to request body.
- B1.3.b Add `uncertainty_profile` input.
- B1.3.c Add `outcome_metrics` input.
- B1.3.d Return prepared artifact summary in response payloads.

### Task B1.4: Harden profile generation for probabilistic mode

**Depends on:** B1.1

**Parallelizable:** yes

**Blocks:** B2.1 partially

**Files:**

- modify `backend/app/services/oasis_profile_generator.py`

**Subtasks:**

- B1.4.a Separate stable persona text from run-varying behavior fields.
- B1.4.b Identify hidden random fallbacks.
- B1.4.c Add optional preparation seed plumbing.
- B1.4.d Document which preparation randomness remains uncontrolled because of external LLM calls.

## 6. Phase B2: Resolver and ensemble orchestration

### Task B2.1: Build uncertainty resolver

**Depends on:** B1.2

**Parallelizable:** yes

**Blocks:** B2.2, B2.3, B3.1

**Files:**

- create `backend/app/services/uncertainty_resolver.py`

**Subtasks:**

- B2.1.a Implement supported distribution samplers.
- B2.1.b Implement object-path patching into resolved config.
- B2.1.c Capture sampled values in `RunManifest`.
- B2.1.d Enforce support bounds and validation errors.

### Task B2.2: Build ensemble manager and run directory layout

**Depends on:** B1.2, B2.1

**Parallelizable:** yes

**Blocks:** B2.3, B2.4, B3.1

**Files:**

- create `backend/app/services/ensemble_manager.py`
- modify `backend/app/services/simulation_manager.py`

**Subtasks:**

- B2.2.a Create ensemble directories under one simulation.
- B2.2.b Create run directories under one ensemble.
- B2.2.c Persist `ensemble_state.json`.
- B2.2.d Persist `run_manifest.json`.
- B2.2.e Add helpers to list and load runs.

### Task B2.3: Refactor `SimulationRunner` to be run-scoped

**Depends on:** B2.2

**Parallelizable:** no

**Blocks:** B2.4, B3.1, B4.1

**Files:**

- modify `backend/app/services/simulation_runner.py`

**Subtasks:**

- B2.3.a Replace `simulation_id`-keyed in-memory maps with run-scoped identity maps.
- B2.3.b Load config and logs from run directory.
- B2.3.c Make cleanup and stop operations run-specific.
- B2.3.d Preserve compatibility for legacy single-run endpoints.

### Task B2.4: Refactor runtime scripts for explicit seeds and run directories

**Depends on:** B2.2, B2.3

**Parallelizable:** no

**Blocks:** B3.1

**Files:**

- modify `backend/scripts/run_parallel_simulation.py`
- modify `backend/scripts/run_twitter_simulation.py`
- modify `backend/scripts/run_reddit_simulation.py`
- modify `backend/scripts/action_logger.py`

**Subtasks:**

- B2.4.a Add `--run-id`. Current repo status: implemented.
- B2.4.b Add `--seed`. Current repo status: implemented as an explicit best-effort runtime seed boundary.
- B2.4.c Add `--run-dir`. Current repo status: implemented.
- B2.4.d Replace module-global RNG usage with explicit RNG instances. Current repo status: implemented for script scheduling helpers.
- B2.4.e Separate platform RNG streams in dual-platform mode. Current repo status: implemented in the parallel runner.
- B2.4.f Ensure all logs and DB files write into the run directory. Current repo status: implemented.

### Task B2.5: Add ensemble API endpoints

**Depends on:** B2.2, B2.3

**Parallelizable:** yes

**Blocks:** frontend Step 2 and Step 3 final integration

**Files:**

- modify `backend/app/api/simulation.py`

**Subtasks:**

- B2.5.a Add ensemble create endpoint. Current repo status: implemented.
- B2.5.b Add ensemble launch endpoint. Current repo status: implemented through the new batch `start` route.
- B2.5.c Add ensemble status endpoint. Current repo status: implemented through the poll-safe `status` route.
- B2.5.d Add run list endpoint. Current repo status: implemented.
- B2.5.e Add run detail endpoint. Current repo status: implemented with runtime-backed `runtime_status`.
- B2.5 follow-on raw run inspection routes. Current repo status: implemented through `actions` and `timeline` endpoints under the ensemble namespace.

## 7. Phase B3: Outcome extraction and aggregation

### Task B3.1: Add per-run outcome extractor

Current status:

- implemented on 2026-03-08 for the current count-metric registry and run-quality flags; use this artifact contract as the input seam for B3.2+

**Depends on:** B2.4

**Parallelizable:** yes

**Blocks:** B3.2, B3.3, B4.1

**Files:**

- create `backend/app/services/outcome_extractor.py`
- modify `backend/app/services/simulation_runner.py`

**Subtasks:**

- B3.1.a Define first-pass metric set.
- B3.1.b Extract metrics from action logs and timeline summaries.
- B3.1.c Persist `metrics.json`.
- B3.1.d Add run-quality checks and extraction completeness flags.

### Task B3.2: Add aggregate summary builder

Current status:

- implemented on 2026-03-08 with on-demand `aggregate_summary.json` persistence and the planned `/summary` API route; clustering and sensitivity remain separate work

**Depends on:** B3.1

**Parallelizable:** yes

**Blocks:** B3.3, B4.1, frontend Step 4 final rendering

**Files:**

- modify `backend/app/services/ensemble_manager.py`

**Subtasks:**

- B3.2.a Compute empirical probabilities over binary and categorical outcomes.
- B3.2.b Compute quantiles for continuous metrics.
- B3.2.c Persist `aggregate_summary.json`.
- B3.2.d Expose aggregate summary via API.

### Task B3.3: Add scenario clustering

Current status:

- implemented on 2026-03-08 with deterministic `scenario_clusters.json` persistence, the planned `/clusters` route, degraded-run exclusion, and explicit low-confidence warnings

**Depends on:** B3.1

**Parallelizable:** yes

**Blocks:** B4.1

**Files:**

- create `backend/app/services/scenario_clusterer.py`
- modify `backend/app/api/simulation.py`

**Subtasks:**

- B3.3.a Define run-level feature vectors.
- B3.3.b Cluster runs into scenario families.
- B3.3.c Choose cluster prototype runs.
- B3.3.d Persist `scenario_clusters.json`.

### Task B3.4: Add sensitivity analysis

**Depends on:** B2.5, B3.1

**Parallelizable:** yes

**Blocks:** B4.1

**Files:**

- create `backend/app/services/sensitivity_analyzer.py`

**Subtasks:**

- B3.4.a Define observational sensitivity semantics.
- B3.4.b Compute first-pass one-at-a-time driver ranking.
- B3.4.c Persist `sensitivity.json`.
- B3.4.d Expose sensitivity results through API.

**Implementation note:**

- implemented on 2026-03-09 with `backend/app/services/sensitivity_analyzer.py`, the `/api/simulation/<simulation_id>/ensembles/<ensemble_id>/sensitivity` route, and dedicated unit/API tests; the live slice is observational only and keeps thin-sample plus non-causal warnings explicit

## 8. Phase B4: Report and interaction backend

### Task B4.1: Add probabilistic report context builder

**Depends on:** B3.1, B3.2, B3.3

**Parallelizable:** yes

**Blocks:** B4.2, frontend Step 4 final rendering, frontend Step 5 final integration

**Files:**

- modify `backend/app/services/report_agent.py`

**Subtasks:**

- B4.1.a Load aggregate summary instead of only raw single-run state.
- B4.1.b Load scenario cluster artifacts.
- B4.1.c Load sensitivity artifacts.
- B4.1.d Write `probabilistic_report_context.json`.

### Task B4.2: Make report generation ensemble-aware

**Depends on:** B4.1

**Parallelizable:** no

**Blocks:** frontend Step 4 final integration

**Files:**

- modify `backend/app/api/report.py`
- modify `backend/app/services/report_agent.py`

**Subtasks:**

- B4.2.a Allow report generation by `ensemble_id`.
- B4.2.b Add new report sections for top outcomes, scenario families, drivers, and tail risk.
- B4.2.c Label every probability as empirical or calibrated.
- B4.2.d Ensure representative narratives cite run or cluster provenance.

### Task B4.3: Extend report-agent chat for probabilistic artifacts

**Depends on:** B4.1

**Parallelizable:** yes

**Blocks:** frontend Step 5 final integration

**Files:**

- modify `backend/app/services/report_agent.py`
- modify `backend/app/api/report.py`

**Subtasks:**

- B4.3.a Teach chat context to retrieve aggregate artifacts.
- B4.3.b Add run-vs-cluster-vs-ensemble grounding language.
- B4.3.c Add guardrails against unsupported probability claims.

## 9. Phase B5: Graph confidence and calibration

### Task B5.1: Add project- and graph-side confidence metadata

**Depends on:** B1.2

**Parallelizable:** yes

**Blocks:** none for MVP

**Files:**

- modify `backend/app/models/project.py`
- modify `backend/app/services/ontology_generator.py`
- modify `backend/app/services/graph_builder.py`
- modify `backend/app/api/graph.py`

**Subtasks:**

- B5.1.a Add project-level probabilistic defaults and versions.
- B5.1.b Preserve edge and node uncertainty attributes.
- B5.1.c Add graph build post-processing hook for confidence enrichment.

### Task B5.2: Propagate graph confidence through read helpers

**Depends on:** B5.1

**Parallelizable:** yes

**Blocks:** none for MVP

**Files:**

- modify `backend/app/services/zep_entity_reader.py`
- modify `backend/app/services/zep_tools.py`
- modify `backend/app/api/simulation.py`
- modify `backend/app/api/report.py`

**Subtasks:**

- B5.2.a Preserve uncertainty attributes in edge serializers.
- B5.2.b Surface uncertainty fields in graph-search and entity-detail APIs.
- B5.2.c Expose those fields to report tooling.

### Task B5.3: Add calibration artifact management

**Depends on:** B3.2

**Parallelizable:** yes

**Blocks:** calibrated probability claims

**Files:**

- create `backend/app/services/calibration_manager.py`
- modify `backend/app/services/report_agent.py`

**Subtasks:**

- B5.3.a Define recurring targets eligible for calibration.
- B5.3.b Store calibration metadata and score history.
- B5.3.c Apply calibration only when valid artifacts exist.
- B5.3.d Label calibrated vs uncalibrated outputs in report context.

## 10. Phase B6: Backend hardening and release operations

### Task B6.1: Add backend feature flags and compatibility controls

**Depends on:** B1.3

**Parallelizable:** yes

**Blocks:** controlled rollout

**Subtasks:**

- B6.1.a Wire prepare-path flag behavior.
- B6.1.b Wire ensemble runtime flag behavior.
- B6.1.c Wire report and interaction flag behavior.
- B6.1.d Wire calibration flag behavior.

### Task B6.2: Add observability and performance instrumentation

**Depends on:** B2.4, B2.5

**Parallelizable:** yes

**Blocks:** broader rollout

**Subtasks:**

- B6.2.a Instrument ensemble lifecycle timing.
- B6.2.b Instrument run outcome and failure counts.
- B6.2.c Define MVP performance budgets.
- B6.2.d Produce the first backend evidence bundle.

### Task B6.3: Add failure recovery, cleanup, and rerun operations

**Depends on:** B2.3, B2.5

**Parallelizable:** partially

**Blocks:** broader rollout

**Subtasks:**

- B6.3.a Define retry and rerun semantics.
- B6.3.b Implement targeted cleanup.
- B6.3.c Implement stuck-run handling.
- B6.3.d Preserve lineage across reruns.

### Task B6.4: Produce backend release-evidence bundle and ops handoff

**Depends on:** B6.1, B6.2, B6.3

**Parallelizable:** no

**Blocks:** wider rollout

**Subtasks:**

- B6.4.a Assemble backend gate evidence.
- B6.4.b Assemble the backend release-ops handoff package.
- B6.4.c Record known limits and residual risks.
- B6.4.d Obtain backend rollout signoff.

## 11. Backend critical path

The backend critical path is:

- B0.0
- B0.1
- B0.2
- B1.1
- B1.2
- B2.1
- B2.2
- B2.3
- B2.4
- B3.1
- B3.2
- B4.1
- B4.2
- B6.1
- B6.2
- B6.3
- B6.4

## 12. Backend work that can be parallelized safely

- B1.3 can run in parallel with B1.4 after B1.2 stabilizes.
- B3.3 and B3.4 can run in parallel after B3.1 exists.
- B4.3 can run in parallel with frontend Step 5 scaffolding once B4.1 schema is fixed.
- B5.1, B5.2, and B5.3 are mostly outside the MVP critical path.
- B6.1 and B6.2 can overlap once the API and runtime contracts are stable.

## 13. Backend readiness gates

### Gate BG1

Before Phase B2 begins:

- probabilistic schema finalized
- baseline and uncertainty artifacts persist correctly
- legacy mode preserved

### Gate BG2

Before Phase B3 begins:

- run-scoped runtime works
- explicit seeds are passed through
- no artifact collisions across runs

### Gate BG3

Before report integration begins:

- per-run metrics exist
- aggregate summary exists
- scenario clusters exist

### Gate BG4

Before broad rollout:

- stop, cleanup, rerun, and failure recovery work predictably
- performance limits are measured
- report backend never emits unsupported probability language
