# Stochastic Probabilistic Simulation API Contracts

**Date:** 2026-03-09

## 1. Purpose

Define the current and planned probabilistic API surface so backend, frontend, QA, and PM docs can reason from implemented contracts instead of aspirational route names.

## 2. Legacy compatibility rule

Existing single-run endpoints remain valid.

Probabilistic mode is additive.

## 3. Current implemented endpoint groups

### Prepare-path extension

`POST /api/simulation/prepare`

New request fields:

- `probabilistic_mode`
- `uncertainty_profile`
- `outcome_metrics`

New response fields:

- prepared artifact summary
- probabilistic mode flag
- requested uncertainty profile
- requested outcome metrics

`GET /api/simulation/prepare/capabilities`

Current response fields include:

- `probabilistic_prepare_enabled`
- `probabilistic_ensemble_storage_enabled`
- `ensemble_runtime_enabled`
- `probabilistic_report_enabled`
- `probabilistic_interaction_enabled`
- `calibrated_probability_enabled`
- supported uncertainty profiles
- supported outcome metrics
- default prepare selections

### Ensemble management

Implemented now:

`POST /api/simulation/<simulation_id>/ensembles`

Purpose:

- create one storage-only ensemble under a prepared probabilistic simulation
- persist `ensemble_spec.json`, `ensemble_state.json`, `run_manifest.json`, and `resolved_config.json`
- return ensemble state plus lightweight run summaries

`GET /api/simulation/<simulation_id>/ensembles`

Purpose:

- list stored ensemble states for one simulation

`GET /api/simulation/<simulation_id>/ensembles/<ensemble_id>`

Purpose:

- fetch one stored ensemble plus lightweight run summaries

`GET /api/simulation/<simulation_id>/ensembles/<ensemble_id>/runs`

Purpose:

- list member runs with storage-level metadata only
- do not embed full resolved configs in list payloads

`GET /api/simulation/<simulation_id>/ensembles/<ensemble_id>/runs/<run_id>`

Purpose:

- fetch one stored run detail, including `run_manifest`, `resolved_config`, and runtime-backed `runtime_status`

Important current contract notes:

- these routes are gated by `PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED`, with `ENSEMBLE_RUNTIME_ENABLED` retained as a compatibility alias
- these routes are simulation-scoped because `ensemble_id` and `run_id` are not globally unique
- create/list/detail routes are storage-first, but the same simulation-scoped namespace now also exposes member-run lifecycle and inspection routes
- current create requests accept `run_count`, `max_concurrency`, optional `root_seed`, and optional `sampling_mode`

### Runtime-backed ensemble execution and inspection

Implemented now:

- `SimulationRunner.start_simulation(...)` can now accept `(simulation_id, ensemble_id, run_id)` and launch from one run-local `resolved_config.json`
- `SimulationRunner` now persists run-local `run_state.json`, reads run-local action logs, stages legacy profile inputs into the run root, supports targeted cleanup for one run root, and passes explicit `--run-dir`, `--run-id`, and manifest-derived `--seed` arguments for run-scoped launches
- `run_parallel_simulation.py`, `run_twitter_simulation.py`, and `run_reddit_simulation.py` now accept explicit runtime CLI arguments and keep runtime seed wording best-effort only
- the public legacy `/api/simulation/start` and `/api/simulation/<simulation_id>/run-status` endpoints still operate on the simulation root only
- the probabilistic namespace now exposes member-run `start`, `stop`, and `run-status`, ensemble-level `start` and `status`, enriched run detail, and raw run `actions` and `timeline`

`POST /api/simulation/<simulation_id>/ensembles/<ensemble_id>/start`

Purpose:

- launch all requested member runs in one batch on top of the verified B2.3 runner seam and the landed B2.4 script semantics

Current note:

- the current implementation starts all requested runs immediately; it does not yet provide queued orchestration semantics
- `run_ids` may be provided to launch only a subset of stored member runs

`GET /api/simulation/<simulation_id>/ensembles/<ensemble_id>/status`

Purpose:

- expose runtime-backed lifecycle progress and capped per-run status for safe polling

`GET /api/simulation/<simulation_id>/ensembles/<ensemble_id>/runs/<run_id>/actions`

Purpose:

- fetch raw run-scoped action history for one stored ensemble member
- support truthful frontend drilldown and operator inspection without implying aggregate metrics

`GET /api/simulation/<simulation_id>/ensembles/<ensemble_id>/runs/<run_id>/timeline`

Purpose:

- fetch raw run-scoped round timeline data for one stored ensemble member
- support detailed runtime inspection alongside the later aggregate artifacts without pretending Step 4 report context already exists

Still deferred from the current implementation:

- richer retry/rerun orchestration semantics

### Aggregate analytics

Live today:

`GET /api/simulation/<simulation_id>/ensembles/<ensemble_id>/summary`

Purpose:

- fetch `aggregate_summary.json`

`GET /api/simulation/<simulation_id>/ensembles/<ensemble_id>/clusters`

Purpose:

- fetch `scenario_clusters.json`

Live today:

`GET /api/simulation/<simulation_id>/ensembles/<ensemble_id>/sensitivity`

Purpose:

- fetch `sensitivity.json`
- surface observational driver rankings derived from stored `resolved_values` plus complete `metrics.json`

Important current contract notes:

- the current sensitivity artifact is empirical and observational only; it does not claim controlled perturbation semantics, causal attribution, or calibration
- missing, degraded, unreadable, or thin evidence is surfaced through explicit warning fields instead of being hidden behind optimistic wording

### Report integration

Live today:

`POST /api/report/generate`

Current request fields:

- `simulation_id`
- optional `ensemble_id`
- optional `run_id`
- optional `force_regenerate`

Current note:

- report generation still uses `simulation_id` as the canonical parent identity, but it now accepts optional `ensemble_id` and `run_id`, persists bounded probabilistic scope on the report record, and keeps legacy report generation working when those fields are absent

Live today:

`GET /api/report/<report_id>`

- optional `ensemble_id`
- optional `run_id`
- optional `probabilistic_context`

Deferred until fuller report/runtime integration exists:

- probabilistic artifact summary
- report provenance status

## 4. Error semantics

- invalid probabilistic mode inputs must return actionable validation errors
- storage routes must return actionable 400s when probabilistic prepare artifacts are missing or the storage flag is off
- missing simulation, ensemble, or run resources must return explicit 404s
- unsupported calibrated mode must return a clear "calibration unavailable" error or downgrade path
- missing aggregate or cluster artifacts must not be silently interpreted as single-run probabilities
