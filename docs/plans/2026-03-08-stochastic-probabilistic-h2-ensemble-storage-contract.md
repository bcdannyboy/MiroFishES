# Stochastic Probabilistic Simulation H2 Ensemble Storage Contract

**Date:** 2026-03-10

## 1. Purpose

This document records the live H2 storage contract that now exists in the repo beneath the runtime draft.

It locks the current truth for:

- simulation-scoped ensemble and run identity
- durable ensemble and run artifacts on disk
- persisted `run_manifest.json` lifecycle and lineage semantics
- the current storage/runtime boundary, including what storage may record after runtime actions
- the evidence class for each claim

This document is no longer just a storage-and-inspection note. The repo now persists limited lifecycle aftermath inside storage artifacts. It is still not a full runtime contract.

## 2. Repo-grounded implementation surfaces

The current contract is grounded in:

- `backend/app/models/probabilistic.py`
- `backend/app/services/ensemble_manager.py`
- `backend/app/api/simulation.py`
- `backend/app/services/simulation_runner.py`
- `backend/tests/unit/test_probabilistic_schema.py`
- `backend/tests/unit/test_ensemble_storage.py`
- `backend/tests/unit/test_probabilistic_ensemble_api.py`
- `backend/tests/unit/test_simulation_runner_runtime_scope.py`

## 3. Current implemented backend truth

The backend now contains a real simulation-scoped ensemble storage layer that remains additive to the legacy single-run path.

Implemented behavior:

- probabilistic prepare still produces simulation-level artifacts first
- full probabilistic storage readiness requires `simulation_config.base.json`, `uncertainty_spec.json`, `outcome_spec.json`, and `prepared_snapshot.json`; partial sidecars do not authorize ensemble creation
- `EnsembleManager.create_ensemble` creates one durable ensemble root under one prepared `simulation_id`
- each planned run gets an isolated run directory with `run_manifest.json` and `resolved_config.json`
- storage APIs can create, list, and load stored ensembles and stored runs
- runtime launch, stop, cleanup, and rerun behavior now update or consume those stored artifacts instead of treating them as write-once preparation output
- the legacy single-run runtime path remains intact and separate

Explicit non-behavior:

- ensemble creation itself does not start runtime processes
- storage artifacts do not by themselves prove that a live process exists
- this contract does not create aggregate summary, scenario clustering, sensitivity, or calibrated probability claims
- this contract does not define the final operator runbook or release package

## 4. Identity semantics

### 4.1 Parent identity

`simulation_id` remains the durable parent identity.

Meaning today:

- one prepared simulation root
- one legacy compatibility runtime root
- the parent directory under which zero or more stored ensembles may exist

### 4.2 Ensemble identity

`ensemble_id` is simulation-scoped rather than globally unique.

Current semantics:

- canonical public form: zero-padded bare ID such as `0001`
- directory form on disk: `ensemble_0001`
- uniqueness guarantee: unique only within one `simulation_id`

### 4.3 Run identity

`run_id` is ensemble-scoped rather than globally unique.

Current semantics:

- canonical public form: zero-padded bare ID such as `0001`
- directory form on disk: `run_0001`
- uniqueness guarantee: unique only within one `ensemble_id` under one `simulation_id`

### 4.4 Prefix normalization

The service layer accepts either bare or prefixed IDs when loading.

Public contract guidance:

- API consumers should treat bare IDs as canonical
- callers need `(simulation_id, ensemble_id, run_id)` for unambiguous lookup

## 5. Feature flags and capability discovery

Prepare remains gated by:

- `Config.PROBABILISTIC_PREPARE_ENABLED`

Storage and runtime-storage routes are gated by:

- `Config.PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED`
- `Config.ENSEMBLE_RUNTIME_ENABLED` as a compatibility alias

`GET /api/simulation/prepare/capabilities` exposes:

- `probabilistic_prepare_enabled`
- `probabilistic_ensemble_storage_enabled`
- `ensemble_runtime_enabled`
- the probabilistic prepare domain registry

## 6. Directory layout and artifact classes

Current implemented layout:

```text
uploads/simulations/<simulation_id>/
  state.json
  simulation_config.json
  simulation_config.base.json
  uncertainty_spec.json
  outcome_spec.json
  prepared_snapshot.json
  reddit_profiles.json
  twitter_profiles.csv
  ensemble/
    ensemble_<ensemble_id>/
      ensemble_spec.json
      ensemble_state.json
      runs/
        run_<run_id>/
          run_manifest.json
          resolved_config.json
          run_state.json                 # runtime-owned, volatile
          simulation.log                 # runtime-owned, volatile
          metrics.json                   # runtime-owned, regenerable
          twitter/actions.jsonl          # runtime-owned, volatile when platform used
          reddit/actions.jsonl           # runtime-owned, volatile when platform used
```

Important boundary truth:

- `ensemble_spec.json`, `ensemble_state.json`, `run_manifest.json`, and `resolved_config.json` are the durable storage contract
- `run_state.json`, `simulation.log`, `metrics.json`, and per-platform `actions.jsonl` files are runtime-owned artifacts that may appear only after launch and may be deleted during cleanup
- cleanup is expected to preserve the durable input artifacts while removing volatile runtime byproducts

## 7. Persisted artifact semantics

### 7.1 `ensemble_spec.json`

Producer:

- `EnsembleManager.create_ensemble`

Current payload:

- `schema_version`
- `generator_version`
- `run_count`
- `max_concurrency`
- `root_seed`
- `sampling_mode`

### 7.2 `ensemble_state.json`

Producer:

- `EnsembleManager.create_ensemble`
- `EnsembleManager.delete_run`
- `EnsembleManager.clone_run_for_rerun`

Implemented fields:

- `artifact_type`
- `schema_version`
- `generator_version`
- `simulation_id`
- `ensemble_id`
- `status`
- `created_at`
- `updated_at`
- `root_seed`
- `sampling_mode`
- `run_count`
- `prepared_run_count`
- `run_ids`
- `source_artifacts`
- `simulation_relative_path`
- `outcome_metric_ids`

Current status meaning:

- `prepared` means durable storage artifacts exist for the current run set
- it does not imply a runtime process is active

### 7.3 `run_manifest.json`

Primary producers and mutators:

- `UncertaintyResolver.resolve_run_config`
- `EnsembleManager.create_ensemble`
- `EnsembleManager.clone_run_for_rerun`
- run-scoped runtime start/stop/cleanup flows

Implemented fields:

- `schema_version`
- `generator_version`
- `simulation_id`
- `ensemble_id`
- `run_id`
- `root_seed`
- `seed_metadata`
- `resolved_values`
- `config_artifact`
- `artifact_paths`
- `generated_at`
- `updated_at`
- `status`
- `lifecycle`
- `lineage`

Current `status` truth:

- `prepared`, `running`, `stopped`, `completed`, and `failed` are now persisted
- this is durable transition state, not authoritative proof that a process is still alive
- the API layer may use persisted terminal statuses when runtime state is absent, but it does not treat storage-only `running` as proof of an active process

Current `lifecycle` truth:

- `start_count`
- `retry_count`
- `cleanup_count`
- `last_launch_reason`

Current `lineage` truth:

- `kind`
- `source_run_id`
- `parent_run_id`

Implemented lineage semantics today:

- initial ensemble members default to `kind: seeded_member`
- child reruns are created with `kind: rerun`
- rerun children preserve `source_run_id` and `parent_run_id` pointing back to the source run
- legacy single-run manifests without `ensemble_id` normalize to `kind: legacy_single_run`

Implemented lifecycle semantics today:

- first launch records `start_count = 1`, `retry_count = 0`, and `last_launch_reason = initial_start`
- same-run retry records a higher `start_count`, increments `retry_count`, and changes `last_launch_reason` to `retry`
- cleanup increments `cleanup_count`, resets `status` to `prepared`, and removes volatile runtime outputs from the manifest view such as `artifact_paths.metrics`

Important remaining limitation:

- `run_manifest.json` now records durable counters and immediate lineage, but it is not an append-only operator event log and does not preserve a full ancestry chain beyond the current parent/source identifiers

### 7.4 `resolved_config.json`

Producer:

- `UncertaintyResolver.resolve_run_config`
- `EnsembleManager.clone_run_for_rerun` via resolved-config artifact rebuild

Current contract:

- this file stores the resolved concrete config for one future or rerun child run
- cleanup preserves it
- rerun clones rebuild it for the new child `run_id`

## 8. Storage/runtime boundary truth

The repo now has a mixed boundary rather than a pure write-once storage layer.

### 8.1 What storage owns durably

Storage owns:

- ensemble and run identity
- resolved input artifacts
- persisted manifest status/lifecycle/lineage fields
- list/detail payloads derived from those artifacts

### 8.2 What runtime owns

Runtime owns:

- active process state
- live runner status
- raw action streams and timeline growth while a run is executing
- volatile run-local files such as `run_state.json`, `simulation.log`, `metrics.json`, and per-platform `actions.jsonl`

### 8.3 How the boundary behaves today

- ensemble creation writes storage artifacts only
- `POST /api/simulation/<simulation_id>/ensembles/<ensemble_id>/runs/<run_id>/rerun` creates a new prepared child run with fresh lifecycle counters and rerun lineage
- `POST /api/simulation/<simulation_id>/ensembles/<ensemble_id>/cleanup` removes volatile runtime artifacts for an explicit run subset, preserves durable inputs, increments `cleanup_count`, and resets `status` to `prepared`
- cleanup refuses active runs with `409` and explicit `active_run_ids`
- `POST /api/simulation/<simulation_id>/ensembles/<ensemble_id>/runs/<run_id>/start` with `force=true` is same-run retry/restart semantics, not child-run creation; it may stop an active run, clean run-local runtime files, and relaunch the same `run_id`
- user-visible status synthesis happens in the API layer on top of both runtime state and persisted storage state

## 9. Implemented API surfaces tied to this contract

The current routes are simulation-scoped because `ensemble_id` and `run_id` are not globally unique.

Primary storage-contract routes:

- `POST /api/simulation/<simulation_id>/ensembles`
- `GET /api/simulation/<simulation_id>/ensembles`
- `GET /api/simulation/<simulation_id>/ensembles/<ensemble_id>`
- `GET /api/simulation/<simulation_id>/ensembles/<ensemble_id>/runs`
- `GET /api/simulation/<simulation_id>/ensembles/<ensemble_id>/runs/<run_id>`

Storage-plus-runtime mutation routes that now rely on this contract:

- `POST /api/simulation/<simulation_id>/ensembles/<ensemble_id>/runs/<run_id>/start`
- `POST /api/simulation/<simulation_id>/ensembles/<ensemble_id>/runs/<run_id>/stop`
- `POST /api/simulation/<simulation_id>/ensembles/<ensemble_id>/runs/<run_id>/rerun`
- `POST /api/simulation/<simulation_id>/ensembles/<ensemble_id>/cleanup`

Common explicit error cases:

- 400 when storage is disabled
- 400 when the probabilistic prepare sidecar set is incomplete
- 404 when the simulation, ensemble, or run does not exist
- 409 when cleanup is requested for one or more active runs

## 10. Verification evidence and boundaries

This contract is evidenced at different strengths.

### 10.1 Unit and contract evidence

Primary repo-grounded evidence:

- `backend/tests/unit/test_probabilistic_schema.py`
- `backend/tests/unit/test_ensemble_storage.py`
- `backend/tests/unit/test_probabilistic_ensemble_api.py`
- `backend/tests/unit/test_simulation_runner_runtime_scope.py`

These tests prove:

- manifest round-trip and normalization
- durable ensemble/run creation and loading
- rerun child creation with lineage reset/preservation rules
- cleanup refusal for active runs
- cleanup reset semantics for inactive runs
- runtime-scope manifest updates for status, lifecycle counters, and metrics artifact paths

### 10.2 Fixture-backed browser evidence

`npm run verify:smoke` proves that the bounded frontend shell can consume the current storage/runtime contract on deterministic fixtures.

It does not by itself prove:

- real-project runtime behavior
- operator understanding of retry versus rerun versus cleanup
- release-grade reliability

### 10.3 Local-only non-fixture evidence

Existing live passes recorded elsewhere in the packet show that the contract can be exercised against one real local simulation family.

That evidence remains:

- local-only
- thin
- not sufficient for release-grade claims

### 10.4 Release-grade evidence

Absent.

This contract should not be used to claim H2 runtime-final or rollout readiness.

## 11. Consumer guidance

Frontend:

- Step 3 may consume explicit `ensemble_id` and `run_id` query-state for the current probabilistic browser, but it must not synthesize placeholder IDs
- keep `report_id` as the canonical Step 4 and Step 5 route identity for now
- do not present storage-only `prepared` or persisted `running` as proof of active runtime state

QA and support:

- use `(simulation_id, ensemble_id, run_id)` together when inspecting stored runs
- treat `prepared` as a storage state only, not runtime completion
- distinguish same-run retry from child-run rerun when reading manifests or operator logs

Backend:

- build B2.4 and B2.5 on top of the current simulation-scoped storage routes instead of replacing them prematurely
- preserve the current legacy `simulation_id` path behind compatibility adapters as runtime work lands
- keep cleanup additive and targeted so sibling run roots are not destroyed accidentally

## 12. Still deferred

Still missing by design or still incomplete:

- final operator runbook semantics for stop, retry, rerun, cleanup, and stuck-run handling
- a fuller Step 3 UI that exposes the already-implemented backend recovery semantics cleanly
- broader Step 3 history/compare/re-entry ownership of `ensemble_id` and `run_id`
- release-grade non-fixture runtime evidence
- H5 release-ops packaging
