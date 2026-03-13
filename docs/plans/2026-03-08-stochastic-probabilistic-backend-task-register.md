# Stochastic Probabilistic Simulation Backend Detailed Task Register

**Date:** 2026-03-10

## 1. Purpose

This document is the second-pass backend execution register for the stochastic probabilistic simulation program. It expands each backend task into implementation-ready work with explicit purpose, inputs, outputs, dependencies, acceptance criteria, and subtask completion conditions.

Use this document together with:

- `docs/plans/2026-03-08-stochastic-probabilistic-status-audit.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-readiness-dashboard.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-backend-workstreams.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-schema-and-artifact-contracts.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-api-contracts.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-runtime-and-seeding-spec.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-test-and-release-plan.md`

Live-status rule:

- use this register for intended execution detail
- use the status audit and readiness dashboard for current repo-grounded status

## Current verified execution snapshot

Verified in this session:

| Task block | Current status | Verified note |
| --- | --- | --- |
| B0.0 | `implemented` | `backend/tests/` exists with shared fixtures and passing pytest discovery |
| B1.1 | `implemented` | `backend/app/models/probabilistic.py` now owns prepare-phase schemas and validation helpers |
| B1.2 | `implemented` | probabilistic prepare persists sidecar artifacts while preserving legacy `simulation_config.json` |
| B1.3 | `implemented` | `/api/simulation/prepare` and `/api/simulation/prepare/status` now carry probabilistic request/summary semantics, require the full probabilistic sidecar set for ready state, and surface exact missing-artifact detail for partial-sidecar states |
| B2.1 | `implemented` | `backend/app/services/uncertainty_resolver.py` resolves seeded concrete configs and emits manifest metadata |
| B2.2 | `implemented` | `backend/app/services/ensemble_manager.py` now persists storage-only ensembles and isolated run roots with deterministic tests |
| B2.3 | `implemented` | `SimulationRunner` now supports composite run-scoped bookkeeping, run-local state/action roots, run-local profile staging, and targeted cleanup while preserving the legacy root path |
| B2.4 | `implemented` | runtime scripts now accept explicit `--run-id`, `--seed`, and `--run-dir`, honor run-local output roots, and use explicit RNG objects for scheduling helpers while keeping seed language best-effort |
| B2.5 | `implemented` | simulation-scoped storage APIs, member-run `start`/`stop`/`run-status`, ensemble-level `start`/`status`, runtime-backed run detail, raw run `actions`/`timeline` inspection routes, and real batch admission-control reporting now exist |
| B3.3 | `implemented` | `backend/app/services/scenario_clusterer.py` now persists deterministic `scenario_clusters.json` artifacts, excludes degraded metrics from membership, normalizes cluster mass against total prepared runs, and exposes the planned `/clusters` route |
| B3.4 | `implemented` | `backend/app/services/sensitivity_analyzer.py` now persists observational `sensitivity.json` artifacts and exposes the planned `/sensitivity` route |
| B4.1 | `implemented` | `backend/app/services/probabilistic_report_context.py` now persists `probabilistic_report_context.json` and packages aggregate summary, scenario clusters, sensitivity, prepared-artifact provenance, and representative run snapshots |
| B4.2 | `partially implemented` | `POST /api/report/generate` now accepts `ensemble_id` and `run_id`, and saved reports persist probabilistic scope plus embedded report context while the report body remains legacy |
| B6.1 | `partially implemented` | backend prepare and ensemble-storage flags exist and are discoverable via `/api/simulation/prepare/capabilities`; the old `ensemble_runtime_enabled` name remains only as a compatibility alias |
| B6.3 | `partially implemented` | member-run rerun, ensemble-scoped cleanup, manifest lifecycle counters, rerun lineage, direct force-retry coverage, batch admission-control reporting, the new backend app-level operator-flow suite, March 10 mitigation for the first-click Step 2 -> Step 3 handoff race, a repo-owned local-only operator pass, and a bounded local operator runbook now exist, but fuller stuck-run/operator handbook depth and broader recovery evidence remain open |

Immediate backend follow-on:

- B4.2 deeper report-body ensemble awareness on top of the new report-context seam
- B4.3 ensemble-aware Step 5 and chat grounding
- B6.3 stuck-run/operator handbook completion and broader non-fixture runtime recovery evidence beyond the new local-only operator path
- H2/H3/H4 handoff maintenance for runtime, aggregate analytics, and report context
- fixture/examples support for H1 package maintenance

## 2. Task block template

Every backend task in this register follows the same structure:

- Purpose: what capability the task creates and why it exists.
- Inputs / Preconditions: artifacts, APIs, or decisions that must already exist.
- Outputs / Deliverables: exact files, endpoints, artifacts, or schemas produced.
- Files / Modules: known code locations to modify or create.
- Dependencies / Sequencing: predecessor tasks, blocked tasks, and parallelization notes.
- Acceptance Criteria: concrete done-when statements.
- Testing / Evidence: minimum test and verification evidence.
- Subtasks: implementation-level breakdown with dependency and completion notes.

## 3. Phase B0: Contract and artifact foundation

### Task B0.0: Create backend test harness scaffolding

Purpose:
- Establish the backend test layout required to verify every later probabilistic change.

Inputs / Preconditions:
- None.

Outputs / Deliverables:
- `backend/tests/unit/`
- `backend/tests/integration/`
- `backend/tests/conftest.py`
- shared fixtures for prepared simulations, ensembles, runs, and artifact roots

Files / Modules:
- create `backend/tests/unit/`
- create `backend/tests/integration/`
- create `backend/tests/conftest.py`

Dependencies / Sequencing:
- Depends on: none
- Blocks: all later tasks that claim pytest coverage
- Parallelizable: yes

Acceptance Criteria:
- `pytest` discovers the new tree from both repo root and `backend/`
- fixtures can create isolated prepared simulation, ensemble, and run directories
- tests can read and write temporary artifact trees without touching committed data

Testing / Evidence:
- one fixture smoke test proving temp artifact roots are created and cleaned up
- written command examples in the test/release plan

Subtasks:
- B0.0.a Create unit and integration test directories. Depends on: none. Output: test tree exists. Done when: `pytest` discovers empty suite without path errors.
- B0.0.b Add shared temp-dir fixtures. Depends on: B0.0.a. Output: reusable filesystem fixtures. Done when: a smoke test creates and cleans temp roots.
- B0.0.c Add prepared simulation, ensemble, and run-root helpers. Depends on: B0.0.b. Output: domain fixtures. Done when: fixtures emit the expected directory skeleton.
- B0.0.d Verify repo-root and backend-root execution paths. Depends on: B0.0.c. Output: documented invocation assumptions. Done when: both invocation styles pass the smoke fixture test.

### Task B0.1: Finalize probabilistic artifact taxonomy

Purpose:
- Lock the canonical artifact names, identity model, and storage layout before implementation starts.

Inputs / Preconditions:
- None.

Outputs / Deliverables:
- canonical naming for `simulation_id`, `ensemble_id`, and `run_id`
- directory layout for prepared simulations, ensembles, and runs
- artifact list including immutable vs mutable files
- backward-compatibility rule for legacy `simulation_config.json`

Files / Modules:
- update `docs/plans/2026-03-08-stochastic-probabilistic-schema-and-artifact-contracts.md`
- update `docs/plans/2026-03-08-stochastic-probabilistic-runtime-and-seeding-spec.md`

Dependencies / Sequencing:
- Depends on: none
- Blocks: B0.2, B1.2, B2.2, B3.2, B4.1
- Parallelizable: yes

Acceptance Criteria:
- one canonical directory-tree example exists
- producer and consumer are named for each artifact
- immutability rules are explicit
- migration rule for legacy single-run artifacts is explicit

Testing / Evidence:
- contract review signoff
- JSON fixture examples referenced from docs

Subtasks:
- B0.1.a Define identifier semantics. Depends on: none. Output: ID rules. Done when: `simulation_id`, `ensemble_id`, and `run_id` are non-overlapping and lifecycle-scoped.
- B0.1.b Define artifact file names. Depends on: B0.1.a. Output: canonical artifact list. Done when: filenames and producers/consumers are documented.
- B0.1.c Define mutability rules. Depends on: B0.1.b. Output: immutable vs mutable artifact policy. Done when: update rules are explicit for every artifact.
- B0.1.d Define legacy compatibility behavior. Depends on: B0.1.b. Output: migration and fallback rules. Done when: legacy `simulation_config.json` behavior is documented.

### Task B0.2: Finalize backend JSON schema contracts

Purpose:
- Lock the field-level payloads and artifact shapes that backend, frontend, and report layers will consume.

Inputs / Preconditions:
- B0.1

Outputs / Deliverables:
- schemas for `RandomVariableSpec`, `EnsembleSpec`, `RunManifest`, `OutcomeMetricDefinition`, `AggregateSummary`, `ScenarioCluster`, and report context artifacts

Files / Modules:
- update `docs/plans/2026-03-08-stochastic-probabilistic-schema-and-artifact-contracts.md`
- update `docs/plans/2026-03-08-stochastic-probabilistic-api-contracts.md`

Dependencies / Sequencing:
- Depends on: B0.1
- Blocks: B1.1, B1.3, B2.1, B2.5, B3.2, B3.3, B4.1
- Parallelizable: partially, but ratification is serial

Acceptance Criteria:
- every artifact has an example JSON shape
- optional vs required fields are documented
- schema version location is explicit
- validation boundary is explicit for backend vs frontend

Testing / Evidence:
- contract review package
- schema examples referenced by path

Subtasks:
- B0.2.a Define `RandomVariableSpec`. Depends on: B0.1. Output: field shape. Done when: supported distributions and parameter rules are explicit.
- B0.2.b Define `EnsembleSpec`. Depends on: B0.1. Output: ensemble schema. Done when: run-count, concurrency, seed, and status fields are fixed.
- B0.2.c Define `RunManifest`. Depends on: B0.1. Output: run manifest schema. Done when: sampled values, lineage, directories, and lifecycle fields are explicit.
- B0.2.d Define `OutcomeMetricDefinition`. Depends on: B0.1. Output: metric schema. Done when: probability domain, thresholds, and aggregation rules are explicit.
- B0.2.e Define `AggregateSummary`. Depends on: B0.2.d. Output: summary schema. Done when: empirical probabilities, quantiles, and provenance fields are explicit.
- B0.2.f Define `ScenarioCluster`. Depends on: B0.2.d. Output: cluster schema. Done when: membership, prototype run, drivers, and early indicators are explicit.

## 4. Phase B1: Preparation-path probabilistic foundation

### Task B1.1: Add probabilistic schema module

Purpose:
- Introduce backend-native models for uncertainty, ensembles, and run manifests.

Inputs / Preconditions:
- B0.2

Outputs / Deliverables:
- `backend/app/models/probabilistic.py`
- serialization and validation helpers for probabilistic artifacts

Files / Modules:
- create `backend/app/models/probabilistic.py`

Dependencies / Sequencing:
- Depends on: B0.2
- Blocks: B1.2, B1.3, B2.1
- Parallelizable: yes

Acceptance Criteria:
- schema models round-trip to and from JSON
- unsupported distribution types raise validation errors
- seed-policy structure is represented explicitly

Testing / Evidence:
- unit tests for valid and invalid schema instances

Subtasks:
- B1.1.a Add dataclasses or models for uncertainty specs. Depends on: B0.2. Output: backend schema types. Done when: all Phase 0 schemas are represented in code.
- B1.1.b Add serialization helpers. Depends on: B1.1.a. Output: JSON read/write utilities. Done when: sample artifacts round-trip without field loss.
- B1.1.c Add validation rules for supported distributions. Depends on: B1.1.a. Output: validators. Done when: malformed parameter sets fail clearly.
- B1.1.d Add seed-policy structure. Depends on: B1.1.a. Output: seed model. Done when: root seed and derived-stream semantics are encoded.

### Task B1.2: Split baseline config from uncertainty spec

Purpose:
- Separate stable prepared simulation state from uncertain run-resolved state.

Inputs / Preconditions:
- B1.1

Outputs / Deliverables:
- `simulation_config.base.json`
- `uncertainty_spec.json`
- `prepared_snapshot.json`
- preserved legacy `simulation_config.json` for non-probabilistic mode

Files / Modules:
- modify `backend/app/services/simulation_config_generator.py`
- modify `backend/app/services/simulation_manager.py`

Dependencies / Sequencing:
- Depends on: B1.1
- Blocks: B1.3, B2.1, B2.2
- Parallelizable: no

Acceptance Criteria:
- prepare flow emits baseline and uncertainty artifacts in probabilistic mode
- legacy mode still emits a usable scalar config
- artifact version fields exist
- prepared snapshot captures deterministic project context and references to derived artifacts

Testing / Evidence:
- unit tests for artifact emission
- integration test for probabilistic prepare and legacy prepare

Subtasks:
- B1.2.a Write `simulation_config.base.json`. Depends on: B1.1. Output: baseline config artifact. Done when: stable config fields no longer mix sampled values.
- B1.2.b Persist `uncertainty_spec.json`. Depends on: B1.2.a. Output: uncertainty artifact. Done when: uncertain fields are stored separately with versions.
- B1.2.c Persist `prepared_snapshot.json`. Depends on: B1.2.a. Output: snapshot artifact. Done when: snapshot references inputs, ontology/graph context, and config lineage.
- B1.2.d Preserve legacy `simulation_config.json`. Depends on: B1.2.a. Output: compatibility artifact. Done when: non-probabilistic mode behavior is unchanged.
- B1.2.e Add version fields. Depends on: B1.2.a. Output: versioned artifacts. Done when: every new artifact includes schema and generator versions.

### Task B1.3: Extend prepare API for probabilistic mode

Purpose:
- Make the prepare endpoint capable of receiving probabilistic inputs and returning prepared probabilistic artifact summaries.

Inputs / Preconditions:
- B1.1
- B1.2
- API contract from Phase 0

Outputs / Deliverables:
- extended prepare request payload
- extended prepare response payload with artifact summary

Files / Modules:
- modify `backend/app/api/simulation.py`

Dependencies / Sequencing:
- Depends on: B1.1, B1.2
- Blocks: frontend probabilistic Step 2 wiring
- Parallelizable: yes with B1.4

Acceptance Criteria:
- prepare request accepts `probabilistic_mode`, `uncertainty_profile`, and `outcome_metrics`
- invalid combinations produce clear 4xx errors
- response contains prepared artifact references and mode metadata

Testing / Evidence:
- API tests for success and validation failures
- example request/response fixtures

Subtasks:
- B1.3.a Add `probabilistic_mode` request field. Depends on: B1.2. Output: mode flag in API. Done when: backend can branch safely between legacy and probabilistic prepare.
- B1.3.b Add `uncertainty_profile` input. Depends on: B1.2. Output: profile input contract. Done when: request validation enforces allowed profile values.
- B1.3.c Add `outcome_metrics` input. Depends on: B0.2, B1.2. Output: metric selection input. Done when: prepare request validates against known metric definitions.
- B1.3.d Return prepared artifact summary. Depends on: B1.2. Output: response metadata. Done when: Step 2 can render artifact versions, paths, and mode.

### Task B1.4: Harden profile generation for probabilistic mode

Purpose:
- Separate stable agent/persona generation from run-varying behavioral parameters.

Inputs / Preconditions:
- B1.1

Outputs / Deliverables:
- clearer separation between stable profile output and run-varying behavior fields
- documented nondeterministic preparation boundaries

Files / Modules:
- modify `backend/app/services/oasis_profile_generator.py`

Dependencies / Sequencing:
- Depends on: B1.1
- Blocks: B2.1 partially
- Parallelizable: yes

Acceptance Criteria:
- stable persona text is not randomly resampled per run
- run-varying behavior fields are surfaced into uncertainty resolution inputs
- uncontrolled LLM nondeterminism is explicitly documented

Testing / Evidence:
- unit tests or fixture checks for stable vs variable field separation
- design note on remaining nondeterministic preparation stages

Subtasks:
- B1.4.a Separate stable persona text from run-varying behavior fields. Depends on: B1.1. Output: clear profile model boundary. Done when: only the intended fields are candidates for sampling.
- B1.4.b Identify hidden random fallbacks. Depends on: B1.4.a. Output: nondeterminism inventory. Done when: random or time-based defaults are cataloged.
- B1.4.c Add optional preparation seed plumbing. Depends on: B1.4.b. Output: controllable seeding where feasible. Done when: seed input reaches deterministic preparation helpers.
- B1.4.d Document uncontrolled preparation randomness. Depends on: B1.4.b. Output: explicit limitation note. Done when: team can distinguish controlled vs uncontrolled variance.

## 5. Phase B2: Resolver and ensemble orchestration

### Task B2.1: Build uncertainty resolver

Purpose:
- Convert baseline config plus uncertainty spec into one concrete resolved run config.

Inputs / Preconditions:
- B1.2
- B0.2 schema contract

Outputs / Deliverables:
- `backend/app/services/uncertainty_resolver.py`
- resolved config generation logic
- sampled-value capture for manifests

Files / Modules:
- create `backend/app/services/uncertainty_resolver.py`

Dependencies / Sequencing:
- Depends on: B1.2
- Blocks: B2.2, B2.3, B3.1
- Parallelizable: yes

Acceptance Criteria:
- supported distributions sample deterministically for a fixed seed
- object-path patching is stable and validated
- unsupported paths or out-of-support values fail clearly

Testing / Evidence:
- unit tests covering each supported distribution
- resolver snapshot tests with fixed seeds

Subtasks:
- B2.1.a Implement supported distribution samplers. Depends on: B0.2. Output: sampler library. Done when: each supported distribution has deterministic seeded behavior.
- B2.1.b Implement object-path patching. Depends on: B2.1.a. Output: config mutator. Done when: sampled values land on the intended config fields only.
- B2.1.c Capture sampled values in `RunManifest`. Depends on: B2.1.b. Output: manifest write data. Done when: every sampled variable is recorded with value and source spec.
- B2.1.d Enforce bounds and validation errors. Depends on: B2.1.a. Output: guardrails. Done when: out-of-support and malformed specs fail with actionable errors.

### Task B2.2: Build ensemble manager and run directory layout

Purpose:
- Create the storage and lifecycle layer for ensembles and their member runs.

Inputs / Preconditions:
- B1.2
- B2.1

Outputs / Deliverables:
- `backend/app/services/ensemble_manager.py`
- run directory layout under each simulation
- ensemble and run state artifacts

Files / Modules:
- create `backend/app/services/ensemble_manager.py`
- modify `backend/app/services/simulation_manager.py`

Dependencies / Sequencing:
- Depends on: B1.2, B2.1
- Blocks: B2.3, B2.4, B2.5, B3.1
- Parallelizable: yes

Acceptance Criteria:
- ensemble creation never collides with existing run artifacts
- run manifests are persisted in deterministic locations
- load/list helpers support both single-run fallback and ensemble mode

Testing / Evidence:
- unit tests for directory creation and reload
- collision and idempotency tests

Subtasks:
- B2.2.a Create ensemble directories. Depends on: B1.2. Output: ensemble root. Done when: one simulation can host multiple ensembles safely.
- B2.2.b Create run directories. Depends on: B2.2.a. Output: run roots. Done when: each run has isolated artifact, log, and DB paths.
- B2.2.c Persist `ensemble_state.json`. Depends on: B2.2.a. Output: ensemble state artifact. Done when: lifecycle state and counts are tracked.
- B2.2.d Persist `run_manifest.json`. Depends on: B2.1, B2.2.b. Output: manifest artifact. Done when: manifests capture lineage, seed, sampled values, and paths.
- B2.2.e Add list/load helpers. Depends on: B2.2.c. Output: manager API. Done when: callers can enumerate runs and ensembles without direct filesystem assumptions.

### Task B2.3: Refactor `SimulationRunner` to be run-scoped

Purpose:
- Replace the current single-run runtime assumptions with explicit run-scoped execution and lifecycle management.

Inputs / Preconditions:
- B2.2

Outputs / Deliverables:
- run-scoped runtime state
- run-scoped stop, cleanup, rerun, and legacy compatibility behavior

Files / Modules:
- modify `backend/app/services/simulation_runner.py`
- inspect and update any runtime callers that assume `simulation_id`-only identity

Dependencies / Sequencing:
- Depends on: B2.2
- Blocks: B2.4, B2.5, B3.1, B6.3
- Parallelizable: no

Acceptance Criteria:
- runtime state is keyed by a run-scoped identity rather than `simulation_id` alone
- multiple runs under one simulation do not collide in memory or on disk
- stop and cleanup can target one run without destroying the whole ensemble
- legacy single-run endpoints still function

Testing / Evidence:
- integration tests for multi-run concurrency
- regression tests for legacy single-run start/stop/report

Subtasks:
- B2.3.a Replace `simulation_id`-keyed maps with run-scoped identity maps. Depends on: B2.2. Output: isolated runtime state. Done when: concurrent runs no longer share mutable runtime entries.
- B2.3.b Load config and logs from run directory. Depends on: B2.3.a. Output: run-local IO. Done when: each runtime instance reads only its run-local artifacts.
- B2.3.c Make stop and cleanup operations run-specific. Depends on: B2.3.a. Output: targeted lifecycle controls. Done when: stopping one run preserves sibling runs.
- B2.3.d Preserve legacy endpoint compatibility. Depends on: B2.3.b. Output: compatibility adapter. Done when: existing single-run flows still call into the refactored runtime successfully.

### Task B2.4: Refactor runtime scripts for explicit seeds and run directories

Purpose:
- Ensure platform scripts and logging honor per-run directories and seed streams.

Inputs / Preconditions:
- B2.2
- B2.3

Outputs / Deliverables:
- CLI arguments for run identity and seed
- explicit RNG usage in runtime scripts
- run-scoped log and DB output

Files / Modules:
- modify `backend/scripts/run_parallel_simulation.py`
- modify `backend/scripts/run_twitter_simulation.py`
- modify `backend/scripts/run_reddit_simulation.py`
- modify `backend/scripts/action_logger.py`

Dependencies / Sequencing:
- Depends on: B2.2, B2.3
- Blocks: B3.1, B6.2
- Parallelizable: no

Acceptance Criteria:
- scripts accept `--run-id`, `--seed`, and `--run-dir`
- module-global RNG usage is eliminated or isolated
- dual-platform mode uses separate child RNG streams
- all artifacts write inside the run root

Testing / Evidence:
- CLI argument tests
- seed reproducibility tests
- multi-run filesystem isolation test

Subtasks:
- B2.4.a Add `--run-id`. Depends on: B2.3. Output: CLI arg. Done when: all scripts can identify the run explicitly. Current status: implemented.
- B2.4.b Add `--seed`. Depends on: B2.3. Output: CLI arg. Done when: deterministic seeded execution is possible. Current status: implemented as an explicit best-effort runtime seed boundary.
- B2.4.c Add `--run-dir`. Depends on: B2.2. Output: CLI arg. Done when: scripts never infer shared output roots. Current status: implemented.
- B2.4.d Replace module-global RNG usage. Depends on: B2.4.b. Output: explicit RNG streams. Done when: randomness is derived from provided seeds only. Current status: implemented for the scripts' scheduling helpers.
- B2.4.e Separate platform RNG streams. Depends on: B2.4.d. Output: child streams. Done when: Reddit and Twitter paths have independent but reproducible sampling. Current status: implemented in the parallel script through derived platform RNG streams.
- B2.4.f Force log and DB writes into run directory. Depends on: B2.4.c. Output: isolated IO. Done when: no cross-run collisions occur on disk. Current status: implemented.

### Task B2.5: Add ensemble API endpoints

Purpose:
- Provide HTTP APIs for creating, launching, monitoring, and inspecting ensembles and runs.

Inputs / Preconditions:
- B2.2
- B2.3
- Phase 0 API contract

Outputs / Deliverables:
- ensemble create, launch, status, run list, and run detail endpoints
- raw run `actions` and `timeline` inspection endpoints under the same ensemble namespace

Files / Modules:
- modify `backend/app/api/simulation.py`

Dependencies / Sequencing:
- Depends on: B2.2, B2.3
- Blocks: frontend Step 2 final launch flow, Step 3 monitor
- Parallelizable: yes

Acceptance Criteria:
- ensemble endpoints return stable schemas
- error states are explicit for missing runs, failed runs, and invalid lifecycle transitions
- pagination or result-capping rule exists for large run sets
- run detail exposes truthful runtime status without fabricating aggregate probability claims
- raw action/timeline inspection remains clearly distinguished from future B3 aggregate artifacts

Testing / Evidence:
- API tests for all new endpoints
- error-path tests for invalid lifecycle transitions

Subtasks:
- B2.5.a Add ensemble create endpoint. Depends on: B2.2. Output: create API. Done when: prepared simulations can create empty ensembles.
- B2.5.b Add ensemble launch endpoint. Depends on: B2.3. Output: launch API. Done when: backend can queue or start all requested runs.
- B2.5.c Add ensemble status endpoint. Depends on: B2.2. Output: status API. Done when: frontend can poll summary progress safely.
- B2.5.d Add run list endpoint. Depends on: B2.2. Output: list API. Done when: frontend can enumerate all run members with lightweight payloads.
- B2.5.e Add run detail endpoint. Depends on: B2.3. Output: detail API. Done when: frontend can inspect per-run seed, status, resolved config, and runtime status. Current status: implemented.
- B2.5.f Add raw run `actions` and `timeline` inspection endpoints. Depends on: B2.3. Output: inspection APIs. Done when: frontend and QA can inspect run-local traces without direct filesystem access. Current status: implemented.

## 6. Phase B3: Outcome extraction and aggregation

### Task B3.1: Add per-run outcome extractor

Current status:

- implemented on 2026-03-08 for the locked count-metric registry plus explicit completeness/quality metadata; aggregate summary, clustering, and sensitivity remain separate follow-on work

Purpose:
- Convert run logs and summaries into standardized metric artifacts for aggregation.

Inputs / Preconditions:
- B2.4
- outcome metric catalog from B0.2

Outputs / Deliverables:
- `backend/app/services/outcome_extractor.py`
- per-run `metrics.json`
- extraction completeness and quality flags

Files / Modules:
- create `backend/app/services/outcome_extractor.py`
- modify `backend/app/services/simulation_runner.py`

Dependencies / Sequencing:
- Depends on: B2.4
- Blocks: B3.2, B3.3, B3.4, B4.1
- Parallelizable: yes

Acceptance Criteria:
- first-pass metric catalog is implemented from the locked metric definitions
- metrics extraction is deterministic for a fixed run artifact set
- missing or partial logs are recorded as completeness flags instead of silent omissions

Testing / Evidence:
- unit tests for metric extraction against fixture runs
- integration test persisting `metrics.json`

Subtasks:
- B3.1.a Implement the first-pass metric catalog. Depends on: B0.2. Output: extractor mapping. Done when: every MVP metric definition has extraction logic.
- B3.1.b Extract metrics from logs and summaries. Depends on: B3.1.a. Output: computed metrics. Done when: fixture runs yield expected metric values.
- B3.1.c Persist `metrics.json`. Depends on: B3.1.b. Output: metrics artifact. Done when: each completed run writes one metrics artifact.
- B3.1.d Add quality and completeness flags. Depends on: B3.1.c. Output: quality metadata. Done when: partial or degraded runs are distinguishable in aggregation.

### Task B3.2: Add aggregate summary builder

Current status:

- implemented on 2026-03-08 for persisted run metrics plus the planned `/summary` route; scenario clustering, sensitivity, and report consumers remain follow-on work

Purpose:
- Produce empirical ensemble-level probability and distribution summaries from run metrics.

Inputs / Preconditions:
- B3.1

Outputs / Deliverables:
- `aggregate_summary.json`
- API exposure for aggregate summary

Files / Modules:
- modify `backend/app/services/ensemble_manager.py`
- modify `backend/app/api/simulation.py`

Dependencies / Sequencing:
- Depends on: B3.1
- Blocks: B4.1, Step 3 provisional widgets, Step 4 report cards
- Parallelizable: yes

Acceptance Criteria:
- binary and categorical metrics produce empirical probabilities
- continuous metrics produce means and quantiles where defined
- thin-sample and degraded-run warnings are included

Testing / Evidence:
- unit tests for probability and quantile calculations
- API tests for summary endpoint or payload inclusion

Subtasks:
- B3.2.a Compute empirical probabilities. Depends on: B3.1. Output: summary statistics. Done when: binary and categorical outcomes are aggregated correctly.
- B3.2.b Compute quantiles for continuous metrics. Depends on: B3.1. Output: quantile stats. Done when: quantile fields match fixture expectations.
- B3.2.c Persist `aggregate_summary.json`. Depends on: B3.2.a. Output: summary artifact. Done when: ensembles write a summary artifact with provenance.
- B3.2.d Expose aggregate summary via API. Depends on: B3.2.c. Output: API surface. Done when: frontend and report consumers can fetch the summary.

### Task B3.3: Add scenario clustering

Current status:

- implemented on 2026-03-08 with deterministic `scenario_clusters.json` persistence, the planned `/clusters` route, degraded-run exclusion, total-run mass normalization, and explicit low-confidence warnings for thin or weak evidence

Purpose:
- Group runs into scenario families so ensemble outputs are intelligible to users.

Inputs / Preconditions:
- B3.1

Outputs / Deliverables:
- `backend/app/services/scenario_clusterer.py`
- `scenario_clusters.json`
- `GET /api/simulation/<simulation_id>/ensembles/<ensemble_id>/clusters`

Files / Modules:
- create `backend/app/services/scenario_clusterer.py`
- modify `backend/app/api/simulation.py`

Dependencies / Sequencing:
- Depends on: B3.1
- Blocks: B4.1, Step 4 cluster rendering
- Parallelizable: yes

Acceptance Criteria:
- run-level feature vectors are derived from standardized metrics rather than raw narratives
- every cluster has a prototype run and mass estimate
- low-confidence clustering conditions are surfaced explicitly

Testing / Evidence:
- clustering tests on fixture ensembles
- deterministic output tests for fixed fixture metrics
- API tests for the `/clusters` route

Subtasks:
- B3.3.a Define run-level feature vectors. Depends on: B3.1. Output: feature schema. Done when: cluster input features are documented and reproducible.
- B3.3.b Cluster runs into scenario families. Depends on: B3.3.a. Output: cluster assignments. Done when: each run receives a stable scenario-family membership.
- B3.3.c Choose prototype runs. Depends on: B3.3.b. Output: representative run mapping. Done when: each cluster has one explainable prototype run.
- B3.3.d Persist `scenario_clusters.json`. Depends on: B3.3.b. Output: cluster artifact. Done when: cluster metadata and provenance are written to disk.

Implementation note:

- implemented on 2026-03-08 through `backend/app/services/scenario_clusterer.py`, `backend/app/api/simulation.py`, `backend/tests/unit/test_scenario_clusterer.py`, and `backend/tests/unit/test_probabilistic_ensemble_api.py`; the live slice stays metric-driven, excludes degraded or unreadable run metrics from membership, and keeps low-confidence conditions explicit instead of inventing richer scenario semantics than the repo can support

### Task B3.4: Add sensitivity analysis

Purpose:
- Rank which observed resolved-value changes most affect ensemble outcome distributions without claiming causality.

Inputs / Preconditions:
- B2.5
- B3.1

Outputs / Deliverables:
- `backend/app/services/sensitivity_analyzer.py`
- `sensitivity.json`
- API exposure for sensitivity results

Files / Modules:
- create `backend/app/services/sensitivity_analyzer.py`
- modify `backend/app/api/simulation.py`

Dependencies / Sequencing:
- Depends on: B2.5, B3.1
- Blocks: B4.1, Step 4 sensitivity view
- Parallelizable: yes

Acceptance Criteria:
- observational-only semantics are explicit
- first-pass driver ranking works for locked MVP metrics
- sensitivity outputs are flagged as empirical and method-specific

Testing / Evidence:
- tests for observational grouping over stored resolved values
- API tests for sensitivity responses

Implementation note:

- implemented on 2026-03-09 through `backend/app/services/sensitivity_analyzer.py`, `backend/app/api/simulation.py`, `backend/tests/unit/test_sensitivity_analyzer.py`, and the sensitivity cases in `backend/tests/unit/test_probabilistic_ensemble_api.py`; the live slice derives ranked driver effects from complete `metrics.json` artifacts plus stored `resolved_values`, persists `sensitivity.json` on demand, and keeps `observational_only` and `thin_sample` warnings explicit instead of implying perturbation or calibrated semantics

Subtasks:
- B3.4.a Define observational sensitivity semantics. Depends on: B2.5. Output: method boundary. Done when: the artifact explicitly states that rankings are empirical and non-causal.
- B3.4.b Compute one-at-a-time driver ranking. Depends on: B3.1, B3.4.a. Output: ranked drivers. Done when: fixture resolved-value groupings yield stable ordering.
- B3.4.c Persist `sensitivity.json`. Depends on: B3.4.b. Output: sensitivity artifact. Done when: method, ranked variables, and effect sizes are stored.
- B3.4.d Expose sensitivity via API. Depends on: B3.4.c. Output: sensitivity API. Done when: report and frontend consumers can fetch ranked drivers.

## 7. Phase B4: Report and interaction backend

### Task B4.1: Add probabilistic report context builder

Purpose:
- Build one report-ready context artifact that merges ensemble summaries, clusters, and sensitivity for reporting and chat.

Inputs / Preconditions:
- B3.1
- B3.2
- B3.3
- B3.4 for full driver context

Outputs / Deliverables:
- `probabilistic_report_context.json`

Files / Modules:
- `backend/app/services/probabilistic_report_context.py`
- `backend/app/services/ensemble_manager.py`
- `backend/app/services/scenario_clusterer.py`
- `backend/app/services/sensitivity_analyzer.py`

Dependencies / Sequencing:
- Depends on: B3.1, B3.2, B3.3, B3.4
- Blocks: B4.2, B4.3, Step 4 final rendering, Step 5 final integration
- Parallelizable: yes

Acceptance Criteria:
- context clearly distinguishes ensemble-level, cluster-level, and run-level facts
- probability provenance is explicit for every field
- degraded or missing artifacts are surfaced as omissions, not hallucinated fills

Testing / Evidence:
- fixture-based context generation tests
- prompt-size sanity checks for chat/report usage

Implementation note:

- implemented on 2026-03-09 through `backend/app/services/probabilistic_report_context.py`, `backend/tests/unit/test_probabilistic_report_context.py`, and the new H4 contract doc; the live builder now persists `probabilistic_report_context.json`, embeds prepared-artifact provenance, carries explicit empirical/observational semantics, and preserves thin-sample or degraded-evidence warnings instead of normalizing them away

Subtasks:
- B4.1.a Load aggregate summary. Depends on: B3.2. Output: summary input. Done when: report context always uses ensemble summary as the probability backbone.
- B4.1.b Load scenario clusters. Depends on: B3.3. Output: cluster input. Done when: report context includes family masses and prototype references.
- B4.1.c Load sensitivity artifacts. Depends on: B3.4. Output: driver input. Done when: report context includes ranked drivers or thin-evidence warnings.
- B4.1.d Write `probabilistic_report_context.json`. Depends on: B4.1.a, B4.1.b, B4.1.c. Output: report context artifact. Done when: one structured artifact can feed Step 4 and Step 5.

### Task B4.2: Make report generation ensemble-aware

Purpose:
- Extend report generation so it can produce probabilistic summaries backed by ensemble artifacts.

Inputs / Preconditions:
- B4.1

Outputs / Deliverables:
- report generation by `ensemble_id`
- new report sections for top outcomes, scenario families, drivers, and tail risk

Files / Modules:
- modify `backend/app/api/report.py`
- modify `backend/app/services/report_agent.py`

Dependencies / Sequencing:
- Depends on: B4.1
- Blocks: Step 4 final integration
- Parallelizable: no

Acceptance Criteria:
- report generation accepts ensemble context safely
- every probability is labeled empirical or calibrated
- representative narratives cite cluster or run provenance

Testing / Evidence:
- report-generation tests against fixture report context
- prompt or output review checklist for unsupported claims

Implementation note:

- partially implemented on 2026-03-09 through `backend/app/api/report.py`, `backend/app/services/report_agent.py`, and `backend/tests/unit/test_probabilistic_report_api.py`; the live report API now accepts `ensemble_id` and `run_id`, persists them in report metadata, and embeds the new probabilistic report context in `GET /api/report/<report_id>`, but the generated markdown body is still the legacy simulation-scoped report rather than a full ensemble-aware renderer

Subtasks:
- B4.2.a Allow report generation by `ensemble_id`. Depends on: B4.1. Output: new report entry path. Done when: report API can resolve ensemble-scoped inputs.
- B4.2.b Add probabilistic report sections. Depends on: B4.2.a. Output: new sections. Done when: top outcomes, scenario families, drivers, and tail risk render from artifacts.
- B4.2.c Label empirical vs calibrated probabilities. Depends on: B4.2.b. Output: provenance labels. Done when: reports never blur uncalibrated and calibrated values.
- B4.2.d Enforce representative narrative provenance. Depends on: B4.2.b. Output: provenance rules. Done when: any narrative example cites run or cluster identity.

### Task B4.3: Extend report-agent chat for probabilistic artifacts

Purpose:
- Allow chat and report Q&A to answer ensemble-aware questions without making unsupported probability claims.

Inputs / Preconditions:
- B4.1

Outputs / Deliverables:
- chat grounding over report context artifacts
- claim guardrails for unsupported or absent probability evidence

Files / Modules:
- modify `backend/app/services/report_agent.py`
- modify `backend/app/api/report.py`

Dependencies / Sequencing:
- Depends on: B4.1
- Blocks: Step 5 final integration
- Parallelizable: yes

Acceptance Criteria:
- chat can distinguish ensemble, cluster, and run scopes
- unsupported questions fall back to evidence-aware disclaimers
- no answer fabricates calibrated probability claims when calibration is disabled

Testing / Evidence:
- chat grounding tests with fixture context
- manual red-team prompt checklist for unsupported claims

Subtasks:
- B4.3.a Retrieve aggregate artifacts in chat context. Depends on: B4.1. Output: artifact-aware retrieval. Done when: chat has access to summary, clusters, and drivers.
- B4.3.b Add run-vs-cluster-vs-ensemble grounding language. Depends on: B4.3.a. Output: scope framing. Done when: answers explicitly state the evidence scope they are using.
- B4.3.c Add unsupported-claim guardrails. Depends on: B4.3.a. Output: safe fallback logic. Done when: chat refuses or qualifies claims not backed by artifacts.

## 8. Phase B5: Graph confidence and calibration

### Task B5.1: Add project- and graph-side confidence metadata

Purpose:
- Preserve graph-side confidence and uncertainty so later phases can reason about source trust and confidence propagation.

Inputs / Preconditions:
- B1.2

Outputs / Deliverables:
- project-level probabilistic defaults and graph confidence fields

Files / Modules:
- modify `backend/app/models/project.py`
- modify `backend/app/services/ontology_generator.py`
- modify `backend/app/services/graph_builder.py`
- modify `backend/app/api/graph.py`

Dependencies / Sequencing:
- Depends on: B1.2
- Blocks: none for MVP
- Parallelizable: yes

Acceptance Criteria:
- graph nodes and edges can preserve uncertainty metadata
- project model can store probabilistic defaults and versions
- graph build does not drop confidence fields

Testing / Evidence:
- unit or integration tests for graph confidence persistence

Subtasks:
- B5.1.a Add project-level probabilistic defaults and versions. Depends on: B1.2. Output: project model fields. Done when: project metadata can express probabilistic configuration defaults.
- B5.1.b Preserve edge and node uncertainty attributes. Depends on: B5.1.a. Output: graph persistence. Done when: build and serialization paths retain uncertainty fields.
- B5.1.c Add graph-build post-processing hook. Depends on: B5.1.b. Output: enrichment hook. Done when: a single hook can attach confidence metadata consistently.

### Task B5.2: Propagate graph confidence through read helpers

Purpose:
- Ensure confidence metadata survives graph reads used by simulation and report workflows.

Inputs / Preconditions:
- B5.1

Outputs / Deliverables:
- graph search and entity detail responses that preserve uncertainty fields

Files / Modules:
- modify `backend/app/services/zep_entity_reader.py`
- modify `backend/app/services/zep_tools.py`
- modify `backend/app/api/simulation.py`
- modify `backend/app/api/report.py`

Dependencies / Sequencing:
- Depends on: B5.1
- Blocks: none for MVP
- Parallelizable: yes

Acceptance Criteria:
- uncertainty attributes survive serializer and helper transformations
- simulation and report layers can access those fields when needed

Testing / Evidence:
- serializer tests showing field preservation

Subtasks:
- B5.2.a Preserve uncertainty attributes in edge serializers. Depends on: B5.1. Output: serializer update. Done when: edge confidence fields survive read serialization.
- B5.2.b Surface uncertainty fields in APIs. Depends on: B5.2.a. Output: API payloads. Done when: graph-search and entity-detail APIs return the new fields.
- B5.2.c Expose uncertainty fields to report tooling. Depends on: B5.2.b. Output: report access path. Done when: report tools can inspect graph-side confidence without custom queries.

### Task B5.3: Add calibration artifact management

Purpose:
- Introduce the storage and policy layer required before calibrated probability labels can be enabled.

Inputs / Preconditions:
- B3.2

Outputs / Deliverables:
- `backend/app/services/calibration_manager.py`
- calibration metadata and score history artifacts

Files / Modules:
- create `backend/app/services/calibration_manager.py`
- modify `backend/app/services/report_agent.py`

Dependencies / Sequencing:
- Depends on: B3.2
- Blocks: calibrated probability claims
- Parallelizable: yes

Acceptance Criteria:
- eligible recurring targets are explicitly listed
- calibration score history is stored and versioned
- calibrated labels only appear when valid calibration artifacts exist

Testing / Evidence:
- unit tests for calibration artifact reads/writes
- report tests ensuring calibrated labels remain off without valid artifacts

Subtasks:
- B5.3.a Define recurring targets eligible for calibration. Depends on: B3.2. Output: eligible target catalog. Done when: only recurring measurable targets can receive calibration treatment.
- B5.3.b Store calibration metadata and score history. Depends on: B5.3.a. Output: calibration artifacts. Done when: scores, timestamps, methods, and versions persist.
- B5.3.c Apply calibration only when valid artifacts exist. Depends on: B5.3.b. Output: gating logic. Done when: report context suppresses calibrated labels when prerequisites are absent.
- B5.3.d Label calibrated vs uncalibrated outputs. Depends on: B5.3.c. Output: provenance behavior. Done when: users can distinguish adjusted from raw empirical probabilities.

## 9. Phase B6: Backend hardening and release operations

### Task B6.1: Add backend feature flags and compatibility controls

Purpose:
- Ensure probabilistic capabilities can be enabled, disabled, and rolled back without breaking legacy flows.

Inputs / Preconditions:
- B1.3
- governance flag policy

Outputs / Deliverables:
- backend flag checks for prepare, ensemble storage, report, interaction, and calibration features

Files / Modules:
- modify relevant backend API and service entry points

Dependencies / Sequencing:
- Depends on: B1.3
- Blocks: B6.4, controlled rollout
- Parallelizable: yes

Acceptance Criteria:
- each probabilistic capability is independently disableable
- legacy endpoints remain available when flags are off
- unsupported flagged-off requests degrade gracefully

Testing / Evidence:
- flag-on and flag-off API tests

Subtasks:
- B6.1.a Wire `probabilistic_prepare_enabled`. Depends on: B1.3. Output: prepare gating. Done when: probabilistic prepare can be disabled cleanly.
- B6.1.b Wire `probabilistic_ensemble_storage_enabled`. Depends on: B2.2. Output: storage gating. Done when: ensemble creation and inspection can be disabled independently of prepare.
- B6.1.c Wire report and interaction flags. Depends on: B4.2, B4.3. Output: report/chat gating. Done when: probabilistic report and interaction can be disabled without 500s.
- B6.1.d Wire calibration flag. Depends on: B5.3. Output: calibration gating. Done when: calibrated labels cannot surface when the flag is off.

### Task B6.2: Add observability and performance instrumentation

Purpose:
- Make probabilistic execution measurable enough to support rollout and debugging.

Inputs / Preconditions:
- B2.4
- B2.5

Outputs / Deliverables:
- ensemble/run timing metrics
- failure counts and status metrics
- basic performance budget evidence

Files / Modules:
- modify runtime and API layers that launch and monitor runs

Dependencies / Sequencing:
- Depends on: B2.4, B2.5
- Blocks: B6.4, wider rollout
- Parallelizable: yes

Acceptance Criteria:
- ensemble launch, completion, failure, and runtime duration are measurable
- performance budget evidence exists for MVP-size ensembles
- debugging a stuck or failed run has a first-pass telemetry path

Testing / Evidence:
- observability smoke checklist
- timing capture in fixture or local dry-run environments

Subtasks:
- B6.2.a Instrument ensemble lifecycle timings. Depends on: B2.5. Output: timing metrics. Done when: creation, launch, completion, and failure timestamps are recorded.
- B6.2.b Instrument run outcome and failure counts. Depends on: B2.5. Output: status metrics. Done when: failed, completed, and retried runs are countable.
- B6.2.c Define MVP performance budgets. Depends on: B6.2.a. Output: documented thresholds. Done when: team has written expected limits for run count, time, and storage.
- B6.2.d Produce first evidence bundle. Depends on: B6.2.a, B6.2.b. Output: rollout evidence. Done when: one measured run campaign is documented.

### Task B6.3: Add failure recovery, cleanup, and rerun operations

Purpose:
- Make run lifecycle behavior predictable under partial failure and operator intervention.

Inputs / Preconditions:
- B2.3
- B2.5

Outputs / Deliverables:
- retry, rerun, targeted cleanup, and stuck-run recovery semantics

Files / Modules:
- modify `backend/app/services/simulation_runner.py`
- modify `backend/app/services/ensemble_manager.py`
- modify relevant APIs

Dependencies / Sequencing:
- Depends on: B2.3, B2.5
- Blocks: B6.4, broader rollout
- Parallelizable: partially

Acceptance Criteria:
- failed runs can be identified and recovered without corrupting sibling runs
- cleanup can target one run or one ensemble safely
- reruns preserve lineage and do not overwrite prior artifacts

Testing / Evidence:
- integration tests for failure recovery
- local operator runbook plus recovery-path evidence

Subtasks:
- B6.3.a Define retry and rerun semantics. Depends on: B2.5. Output: lifecycle policy. Done when: retry vs rerun vs restart behavior is explicit.
- B6.3.b Implement targeted cleanup behavior. Depends on: B2.3. Output: cleanup controls. Done when: one run can be cleaned without deleting sibling evidence.
- B6.3.c Implement stuck-run handling. Depends on: B6.3.a. Output: recovery path. Done when: operators can mark or stop stuck runs without breaking the ensemble.
- B6.3.d Preserve lineage across reruns. Depends on: B6.3.a. Output: lineage tracking. Done when: reruns reference parent runs and preserve prior evidence.

Implementation note:

- partially implemented on 2026-03-10 through `backend/app/models/probabilistic.py`, `backend/app/services/simulation_runner.py`, `backend/app/services/ensemble_manager.py`, `backend/app/services/simulation_manager.py`, `backend/app/api/simulation.py`, `backend/tests/integration/test_probabilistic_operator_flow.py`, the targeted backend pytest suite, the local operator runbook, and the repo-owned local-only operator pass on `sim_7a6661c37719`: retry now reuses the existing member-run `start` path after cleanup policy, direct member-run `force=true` retry now has API-level coverage, `POST /api/simulation/<simulation_id>/ensembles/<ensemble_id>/runs/<run_id>/rerun` now creates a child run with preserved lineage, `POST /api/simulation/<simulation_id>/ensembles/<ensemble_id>/cleanup` now cleans one run subset or a whole ensemble without deleting resolved-config lineage inputs by default, batch `POST /api/simulation/<simulation_id>/ensembles/<ensemble_id>/start` now enforces stored `max_concurrency` with explicit active/start/defer reporting, probabilistic readiness now requires the full sidecar set with explicit missing-artifact reporting, the first-click ensemble-create handoff has repeatable local-only proof after the March 10 mitigation, `run_manifest.json` now records lifecycle counters plus lineage, and a bounded artifact-inspection/recovery guide now exists; fuller stuck-run/operator handbook depth and release-grade non-fixture recovery evidence remain open

### Task B6.4: Produce backend release-evidence bundle and ops handoff

Purpose:
- Convert backend completion into a signoff-ready release package.

Inputs / Preconditions:
- B6.1
- B6.2
- B6.3

Outputs / Deliverables:
- backend gate evidence
- release-ops handoff package
- support notes for probabilistic runtime behavior

Files / Modules:
- update ops docs and release evidence docs

Dependencies / Sequencing:
- Depends on: B6.1, B6.2, B6.3
- Blocks: wider rollout
- Parallelizable: no

Acceptance Criteria:
- schema, runtime, analytics, and ops evidence are assembled
- rollback behavior is documented
- support can identify the difference between empirical and calibrated claims

Testing / Evidence:
- completed gate checklist
- linked test outputs and measured evidence

Subtasks:
- B6.4.a Assemble gate evidence. Depends on: B6.1, B6.2, B6.3. Output: signoff bundle. Done when: G1-G3 backend evidence is collated.
- B6.4.b Assemble ops handoff package. Depends on: B6.2, B6.3. Output: release-ops package. Done when: dashboards, alerts, runbook, and rollback notes are listed.
- B6.4.c Record known limits and open risks. Depends on: B6.4.a. Output: limitations note. Done when: rollout reviewers can see residual risk explicitly.
- B6.4.d Obtain backend signoff. Depends on: B6.4.a, B6.4.b. Output: approval record. Done when: accountable owners approve progression to rollout.
