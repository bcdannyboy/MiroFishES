# Graph Speed And Observability Wave Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add stable phase timing artifacts and remove the main graph-build and prepare bottlenecks by replacing serial throttling, persisting one graph-derived entity index, and avoiding the expensive end-of-build `get_graph_data()` summary fetch.

**Architecture:** Introduce one shared phase-timing writer that persists the same JSON schema across project, simulation, run, ensemble, and report scopes. Rework graph build to use adaptive bounded batch planning, concurrency-limited `add_batch` submission, graph-level episode polling via `episode.get_by_graph_id(lastn=...)`, and one exact post-build graph snapshot that produces both the graph summary and a persisted entity index. Update prepare to use the local entity index first, with explicit schema/version fallback to the existing Zep reread path for older projects.

**Tech Stack:** Python 3.12, Flask blueprints, Zep Cloud SDK 3.13.0, pytest, JSON artifacts under `backend/uploads/projects/`, `backend/uploads/simulations/`, and `backend/uploads/reports/`.

---

### Task 1: Define The Timing Artifact Contract And Project Artifact Helpers

**Files:**
- Create: `backend/app/services/phase_timing.py`
- Modify: `backend/app/models/project.py`
- Modify: `backend/tests/unit/test_forecast_grounding.py`
- Create: `backend/tests/unit/test_phase_timing.py`

**Step 1: Write the failing test**

Add tests for:
- one shared timing schema with `artifact_type`, `schema_version`, `generator_version`, `scope_kind`, `scope_id`, and a `phases` map
- phase entries that store `status`, `duration_ms`, `started_at`, `completed_at`, and deterministic metadata
- project artifact helpers for `graph_phase_timings.json` and `graph_entity_index.json`
- project grounding artifact descriptions surfacing the two new JSON artifacts

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/unit/test_phase_timing.py backend/tests/unit/test_forecast_grounding.py -q`

Expected:
- FAIL because `phase_timing.py` does not exist
- FAIL because `ProjectManager` does not yet describe the new project artifacts

**Step 3: Write minimal implementation**

Implement:
- `backend/app/services/phase_timing.py` with a small recorder API that can create or merge one timing artifact at a known path
- stable JSON shape:
  - `artifact_type: "phase_timings"`
  - `schema_version: "mirofish.phase_timings.v1"`
  - `generator_version: "mirofish.phase_timings.generator.v1"`
  - `scope_kind`: one of `project`, `prepare`, `run`, `ensemble`, `report`
  - `scope_id`: stable scope key such as `proj_x`, `sim_x`, `sim_x::0001::0001`, or `report_x`
  - `phases`: keyed by phase name, each containing `status`, `duration_ms`, `started_at`, `completed_at`, and `metadata`
- `ProjectManager` helpers for:
  - `graph_phase_timings.json`
  - `graph_entity_index.json`
  - save/get/delete/describe methods for both

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/unit/test_phase_timing.py backend/tests/unit/test_forecast_grounding.py -q`

Expected:
- PASS with the timing helper writing stable JSON
- PASS with project artifact summaries exposing the new timing and entity-index artifacts

**Step 5: Commit**

Run:
- `git add backend/app/services/phase_timing.py backend/app/models/project.py backend/tests/unit/test_phase_timing.py backend/tests/unit/test_forecast_grounding.py`
- `git commit -m "feat: add shared phase timing artifact contract"`

### Task 2: Instrument Upload Parse And Ontology Generation

**Files:**
- Modify: `backend/app/api/graph.py`
- Modify: `backend/app/models/project.py`
- Modify: `backend/tests/unit/test_forecast_grounding.py`

**Step 1: Write the failing test**

Extend the ontology-generation tests to assert:
- `graph_phase_timings.json` is persisted during `/api/graph/ontology/generate`
- the project-level timing artifact contains:
  - `upload_parse`
  - `ontology_generation`
- timing metadata carries request-local counts such as `uploaded_file_count`, `parsed_file_count`, `failed_file_count`, and `total_text_length`
- `ProjectManager.describe_grounding_artifacts()` marks `graph_phase_timings` as present in the response payload

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/unit/test_forecast_grounding.py::test_generate_ontology_persists_source_manifest_and_artifact_summary -q`

Expected:
- FAIL because ontology generation does not yet persist timing artifacts

**Step 3: Write minimal implementation**

Implement timing in `backend/app/api/graph.py`:
- wrap the file-save, parse, preprocess, and manifest-build loop with `upload_parse`
- wrap `OntologyGenerator.generate(...)` with `ontology_generation`
- persist both timings into `graph_phase_timings.json` using the Task 1 helper
- keep the route response backward compatible, only adding the new artifact to `grounding_artifacts`
- do not change source-manifest semantics or the existing source-manifest filename

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/unit/test_forecast_grounding.py::test_generate_ontology_persists_source_manifest_and_artifact_summary -q`

Expected:
- PASS with `source_manifest.json` unchanged and `graph_phase_timings.json` present

**Step 5: Commit**

Run:
- `git add backend/app/api/graph.py backend/app/models/project.py backend/tests/unit/test_forecast_grounding.py`
- `git commit -m "feat: persist ontology upload and generation timings"`

### Task 3: Rework Graph Build Batching, Waiting, Summary Counts, And Entity Index Persistence

**Files:**
- Modify: `backend/app/api/graph.py`
- Modify: `backend/app/services/graph_builder.py`
- Modify: `backend/app/services/zep_entity_reader.py`
- Modify: `backend/app/utils/zep_paging.py`
- Modify: `backend/app/models/project.py`
- Modify: `backend/tests/unit/test_graph_builder_service.py`
- Modify: `backend/tests/unit/test_forecast_grounding.py`

**Step 1: Write the failing test**

Add tests for:
- adaptive bounded batch planning, for example:
  - small graphs keep small batches
  - medium and large graphs raise `batch_size`
  - a hard cap keeps fan-out bounded
- `add_text_batches()` no longer calling `time.sleep(1)` in the hot path
- `_wait_for_episodes()` using `client.graph.episode.get_by_graph_id(graph_id, lastn=len(episode_uuids))` instead of one `episode.get(uuid_=...)` per UUID
- one graph snapshot method returning exact `node_count`, `edge_count`, and `entity_types`
- build graph persisting both:
  - `graph_build_summary.json`
  - `graph_entity_index.json`
- the `/api/graph/build` path no longer calling `builder.get_graph_data(graph_id)` to produce final summary counts
- project reset deleting `graph_build_summary.json`, `graph_entity_index.json`, and `graph_phase_timings.json`

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/unit/test_graph_builder_service.py backend/tests/unit/test_forecast_grounding.py -q`

Expected:
- FAIL because graph build still sleeps after every `add_batch`
- FAIL because graph build still polls each episode individually
- FAIL because no entity-index artifact is persisted
- FAIL because build still uses the full `get_graph_data()` path for summary counts

**Step 3: Write minimal implementation**

Implement in `backend/app/services/graph_builder.py`:
- a batch planner such as `_resolve_batch_plan(total_chunks)` that returns:
  - `batch_size`
  - `max_inflight_batches`
  - conservative caps, for example a small fixed ceiling like `16` or `24`
- concurrency-limited batch submission using a bounded executor or equivalent worker pool
- graph wait logic that:
  - polls with `episode.get_by_graph_id(graph_id, lastn=len(episode_uuids))`
  - intersects the returned UUIDs with the pending set
  - uses a bounded polling interval with backoff instead of a fixed 3-second sleep per UUID set
  - falls back to a bounded individual-query path only if the graph-level query is unavailable or malformed
- one exact snapshot helper that fetches uncapped nodes and edges once and returns:
  - trustworthy counts
  - entity types
  - serializable node/edge collections for entity-index building

Implement in `backend/app/utils/zep_paging.py`:
- explicit support for `max_items=None` in the full-fetch helpers so the build summary path can request uncapped node and edge collections without changing preview endpoint defaults

Implement in `backend/app/services/zep_entity_reader.py`:
- a pure helper that can build `FilteredEntities` from already-fetched node and edge collections
- reuse this helper when turning the build snapshot into `graph_entity_index.json`

Implement in `backend/app/api/graph.py`:
- record `graph_batch_send` and `graph_wait` into `graph_phase_timings.json`
- replace the end-of-build `builder.get_graph_data(graph_id)` call with the new exact snapshot helper
- save `graph_build_summary.json` from the exact snapshot counts
- save `graph_entity_index.json` from the same snapshot
- include `graph_entity_index` in the project grounding artifact summary

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/unit/test_graph_builder_service.py backend/tests/unit/test_forecast_grounding.py -q`

Expected:
- PASS with no fixed post-batch sleep in the graph-build hot path
- PASS with graph-level episode polling
- PASS with exact summary counts and a persisted entity index

**Step 5: Commit**

Run:
- `git add backend/app/api/graph.py backend/app/services/graph_builder.py backend/app/services/zep_entity_reader.py backend/app/utils/zep_paging.py backend/app/models/project.py backend/tests/unit/test_graph_builder_service.py backend/tests/unit/test_forecast_grounding.py`
- `git commit -m "feat: speed up graph build and persist entity index"`

### Task 4: Make Prepare Use The Local Entity Index First And Persist Prepare Timings

**Files:**
- Modify: `backend/app/services/zep_entity_reader.py`
- Modify: `backend/app/services/simulation_manager.py`
- Modify: `backend/tests/unit/test_probabilistic_prepare.py`
- Create: `backend/tests/unit/test_zep_entity_reader.py`

**Step 1: Write the failing test**

Add tests for:
- local-artifact-first entity reads when `graph_entity_index.json` exists and matches the requested `graph_id`
- safe fallback to the current Zep node/edge reread when the artifact is:
  - missing
  - schema-incompatible
  - graph-id mismatched
- `prepare_phase_timings.json` containing:
  - `entity_read`
  - `profile_generation`
  - `config_generation`
- `get_prepare_artifact_summary()` exposing the timing artifact without changing existing summary fields
- legacy prepare cleanup removing stale probabilistic timing artifacts when `probabilistic_mode=False`

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/unit/test_zep_entity_reader.py backend/tests/unit/test_probabilistic_prepare.py -q`

Expected:
- FAIL because prepare always rereads the whole graph from Zep
- FAIL because prepare does not persist timing artifacts

**Step 3: Write minimal implementation**

Implement in `backend/app/services/zep_entity_reader.py`:
- local-first load path that accepts `project_id` and optionally `graph_id`
- schema/version checks for `graph_entity_index.json`
- fallback to the current remote path only when the artifact is absent or incompatible
- clear logging of the fallback reason

Implement in `backend/app/services/simulation_manager.py`:
- new prepare artifact filename: `prepare_phase_timings.json`
- `prepare_simulation()` passing `project_id` into the entity reader
- timing wrappers for:
  - entity read
  - profile generation
  - config generation
- additive prepare artifact summary support for the new timing file
- cleanup of `prepare_phase_timings.json` when clearing probabilistic sidecars

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/unit/test_zep_entity_reader.py backend/tests/unit/test_probabilistic_prepare.py -q`

Expected:
- PASS with local entity-index usage on the fast path
- PASS with remote fallback preserved for older projects
- PASS with prepare timings persisted and summarized

**Step 5: Commit**

Run:
- `git add backend/app/services/zep_entity_reader.py backend/app/services/simulation_manager.py backend/tests/unit/test_zep_entity_reader.py backend/tests/unit/test_probabilistic_prepare.py`
- `git commit -m "feat: use persisted entity index during prepare"`

### Task 5: Persist Run, Analytics, And Report Timings Without Widening Scope

**Files:**
- Modify: `backend/app/services/simulation_runner.py`
- Modify: `backend/app/services/scenario_clusterer.py`
- Modify: `backend/app/services/sensitivity_analyzer.py`
- Modify: `backend/app/services/report_agent.py`
- Modify: `backend/tests/unit/test_simulation_runner_runtime_scope.py`
- Modify: `backend/tests/unit/test_simulation_runner_run_scope.py`
- Modify: `backend/tests/unit/test_scenario_clusterer.py`
- Modify: `backend/tests/unit/test_sensitivity_analyzer.py`
- Modify: `backend/tests/unit/test_probabilistic_report_api.py`

**Step 1: Write the failing test**

Add tests for:
- `run_phase_timings.json` being written at run startup with `run_startup`
- `run_phase_timings.json` being updated after metrics extraction with `metrics_extraction`
- run-scoped cleanup removing `run_phase_timings.json` alongside `metrics.json`
- `ensemble_phase_timings.json` being written by:
  - `ScenarioClusterer.get_scenario_clusters()` with `clustering`
  - `SensitivityAnalyzer.get_sensitivity_analysis()` with `sensitivity`
- `report_phase_timings.json` being written by `ReportAgent.generate_report()` with `report_synthesis`

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/unit/test_simulation_runner_runtime_scope.py backend/tests/unit/test_simulation_runner_run_scope.py backend/tests/unit/test_scenario_clusterer.py backend/tests/unit/test_sensitivity_analyzer.py backend/tests/unit/test_probabilistic_report_api.py -q`

Expected:
- FAIL because the run, ensemble, and report timing artifacts do not yet exist

**Step 3: Write minimal implementation**

Implement in `backend/app/services/simulation_runner.py`:
- `run_phase_timings.json` under:
  - the run directory for ensemble members
  - the simulation root for legacy runtime scope
- `run_startup` timing around config resolution, runtime-root materialization, subprocess launch, and state persistence
- `metrics_extraction` timing inside `_persist_run_metrics_artifact(...)`
- cleanup logic removing `run_phase_timings.json` when clearing run-scoped derived outputs

Implement in `backend/app/services/scenario_clusterer.py`:
- wrap `get_scenario_clusters()` and merge `clustering` into `ensemble_phase_timings.json`

Implement in `backend/app/services/sensitivity_analyzer.py`:
- wrap `get_sensitivity_analysis()` and merge `sensitivity` into `ensemble_phase_timings.json`

Implement in `backend/app/services/report_agent.py`:
- write `report_phase_timings.json` into the report folder
- time the full synthesis span inside `generate_report()`, from report initialization to final report assembly
- keep report progress and report body behavior unchanged

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/unit/test_simulation_runner_runtime_scope.py backend/tests/unit/test_simulation_runner_run_scope.py backend/tests/unit/test_scenario_clusterer.py backend/tests/unit/test_sensitivity_analyzer.py backend/tests/unit/test_probabilistic_report_api.py -q`

Expected:
- PASS with stable run, ensemble, and report timing artifacts
- PASS with run cleanup removing the new runtime timing artifact

**Step 5: Commit**

Run:
- `git add backend/app/services/simulation_runner.py backend/app/services/scenario_clusterer.py backend/app/services/sensitivity_analyzer.py backend/app/services/report_agent.py backend/tests/unit/test_simulation_runner_runtime_scope.py backend/tests/unit/test_simulation_runner_run_scope.py backend/tests/unit/test_scenario_clusterer.py backend/tests/unit/test_sensitivity_analyzer.py backend/tests/unit/test_probabilistic_report_api.py`
- `git commit -m "feat: persist runtime analytics and report timings"`

### Task 6: Run Focused Verification And Record Backfill Boundaries

**Files:**
- Modify: none

**Step 1: Run the focused test wave**

Run: `pytest backend/tests/unit/test_phase_timing.py backend/tests/unit/test_forecast_grounding.py backend/tests/unit/test_graph_builder_service.py backend/tests/unit/test_zep_entity_reader.py backend/tests/unit/test_probabilistic_prepare.py backend/tests/unit/test_simulation_runner_runtime_scope.py backend/tests/unit/test_simulation_runner_run_scope.py backend/tests/unit/test_scenario_clusterer.py backend/tests/unit/test_sensitivity_analyzer.py backend/tests/unit/test_probabilistic_report_api.py -q`

Expected:
- PASS

**Step 2: Run one downstream regression check**

Run: `pytest backend/tests/integration/test_probabilistic_operator_flow.py -q`

Expected:
- PASS, or one clearly documented unrelated failure

**Step 3: Run static guardrails against the old bottlenecks**

Run:
- `rg -n "time\\.sleep\\(1\\)" backend/app/services/graph_builder.py`
- `rg -n "episode\\.get\\(uuid_=" backend/app/services/graph_builder.py`
- `rg -n "get_graph_data\\(graph_id\\)" backend/app/api/graph.py`

Expected:
- no hot-path fixed sleep after `add_batch`
- no episode-by-episode completion loop in graph build
- no end-of-build `get_graph_data(graph_id)` summary fetch

**Step 4: Summarize migration and rollback boundaries**

Document in the implementation notes:
- older projects without `graph_entity_index.json` fall back to the current Zep reread path and continue to work
- older projects, simulations, runs, ensembles, and reports without timing artifacts remain readable; absence is not an error
- project reset must delete:
  - `graph_build_summary.json`
  - `graph_entity_index.json`
  - `graph_phase_timings.json`
- legacy prepare cleanup must delete `prepare_phase_timings.json`
- run cleanup must delete `run_phase_timings.json`
- rollback order if the wave has to be reverted:
  1. disable local entity-index reads and leave fallback on
  2. restore serial graph batch submission only if concurrency causes remote instability
  3. leave timing artifacts in place because they are additive and backward compatible

**Step 5: Commit**

Run:
- `git add -A`
- `git commit -m "test: verify graph speed and observability wave"`

## Exact Files Expected To Change

**Create:**
- `backend/app/services/phase_timing.py`
- `backend/tests/unit/test_phase_timing.py`
- `backend/tests/unit/test_zep_entity_reader.py`

**Modify:**
- `backend/app/api/graph.py`
- `backend/app/models/project.py`
- `backend/app/services/graph_builder.py`
- `backend/app/services/zep_entity_reader.py`
- `backend/app/services/simulation_manager.py`
- `backend/app/services/simulation_runner.py`
- `backend/app/services/scenario_clusterer.py`
- `backend/app/services/sensitivity_analyzer.py`
- `backend/app/services/report_agent.py`
- `backend/app/utils/zep_paging.py`
- `backend/tests/unit/test_forecast_grounding.py`
- `backend/tests/unit/test_graph_builder_service.py`
- `backend/tests/unit/test_probabilistic_prepare.py`
- `backend/tests/unit/test_simulation_runner_runtime_scope.py`
- `backend/tests/unit/test_simulation_runner_run_scope.py`
- `backend/tests/unit/test_scenario_clusterer.py`
- `backend/tests/unit/test_sensitivity_analyzer.py`
- `backend/tests/unit/test_probabilistic_report_api.py`

**Inspected, with no direct change planned unless implementation proves otherwise:**
- `backend/app/services/outcome_extractor.py`
- `backend/app/services/probabilistic_report_context.py`
- `backend/tests/integration/test_probabilistic_operator_flow.py`

## Phase Timing Artifact Map

- Project scope: `graph_phase_timings.json`
  - `upload_parse`
  - `ontology_generation`
  - `graph_batch_send`
  - `graph_wait`
- Simulation scope: `prepare_phase_timings.json`
  - `entity_read`
  - `profile_generation`
  - `config_generation`
- Run scope: `run_phase_timings.json`
  - `run_startup`
  - `metrics_extraction`
- Ensemble scope: `ensemble_phase_timings.json`
  - `clustering`
  - `sensitivity`
- Report scope: `report_phase_timings.json`
  - `report_synthesis`

## Batch And Wait Policy

- Batch size must be adaptive but bounded. Start with a small default for small graphs, step up for medium and large graphs, and cap hard at a conservative ceiling such as `16` or `24`.
- Submission concurrency must also be bounded. Use a small worker count such as `2` to `4`, not unbounded fan-out.
- Wait strategy must poll the graph once per round with `episode.get_by_graph_id(graph_id, lastn=len(episode_uuids))`, not one request per pending UUID.
- The exact cap values should be coded in one helper so the policy is testable and easy to tune later.

## Migration And Backfill Behavior

- No offline migration is required for older projects or simulations.
- `graph_entity_index.json` is generated only on new graph builds or rebuilds.
- If prepare sees no entity index, a schema mismatch, or a graph mismatch, it must:
  - log the fallback reason
  - use the current remote Zep read path
  - continue successfully
- Timing artifacts are additive only. Missing timing files must never block existing API reads or report flows.

## Rollback Points

- Safe rollback point 1: leave timing artifacts in place and disable only the new readers or writers if they cause issues.
- Safe rollback point 2: keep the entity index writer but turn off local-index reads in prepare; the remote fallback preserves behavior.
- High-risk rollback point: reverting bounded concurrency in graph build after the API contract changes. Do that only if remote throttling or ordering issues show up in verification.
- Do not reintroduce the end-of-build `get_graph_data()` fetch just to recover summary counts; use the exact snapshot helper instead.

## Verification Commands

- `pytest backend/tests/unit/test_phase_timing.py backend/tests/unit/test_forecast_grounding.py -q`
- `pytest backend/tests/unit/test_graph_builder_service.py -q`
- `pytest backend/tests/unit/test_zep_entity_reader.py backend/tests/unit/test_probabilistic_prepare.py -q`
- `pytest backend/tests/unit/test_simulation_runner_runtime_scope.py backend/tests/unit/test_simulation_runner_run_scope.py -q`
- `pytest backend/tests/unit/test_scenario_clusterer.py backend/tests/unit/test_sensitivity_analyzer.py backend/tests/unit/test_probabilistic_report_api.py -q`
- `pytest backend/tests/integration/test_probabilistic_operator_flow.py -q`
- `rg -n "time\\.sleep\\(1\\)" backend/app/services/graph_builder.py`
- `rg -n "episode\\.get\\(uuid_=" backend/app/services/graph_builder.py`
- `rg -n "get_graph_data\\(graph_id\\)" backend/app/api/graph.py`

