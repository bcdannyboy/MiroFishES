# Stochastic Probabilistic Simulation H1 Prepare-Path Contract

**Date:** 2026-03-10

This document captures the verified H1 prepare-path contract as currently implemented in the repository. It is the handoff package for Step 2 frontend work, QA, and future runtime phases.

## 1. Scope

H1 covers the preparation path only:

- capability discovery for probabilistic prepare
- probabilistic prepare request validation
- probabilistic prepare artifact persistence
- prepared-artifact summary semantics
- legacy compatibility and flag-disabled behavior

H1 does not cover:

- runtime sampling
- ensemble execution
- aggregate analytics
- probabilistic reporting
- calibrated probability surfaces

## 2. Implemented endpoints

### `GET /api/simulation/prepare/capabilities`

Purpose:

- expose the live prepare capability domain to the frontend before Step 2 starts work

Response shape:

```json
{
  "success": true,
  "data": {
    "probabilistic_prepare_enabled": true,
    "supported_uncertainty_profiles": [
      "balanced",
      "deterministic-baseline",
      "stress-test"
    ],
    "default_uncertainty_profile": "deterministic-baseline",
    "supported_outcome_metrics": {
      "simulation.total_actions": {
        "label": "Simulation Total Actions",
        "description": "Count all actions across every enabled platform."
      },
      "platform.twitter.total_actions": {
        "label": "Twitter Total Actions",
        "description": "Count all Twitter-side actions."
      },
      "platform.reddit.total_actions": {
        "label": "Reddit Total Actions",
        "description": "Count all Reddit-side actions."
      }
    },
    "default_outcome_metrics": [
      "simulation.total_actions"
    ],
    "schema_version": "probabilistic.prepare.v1",
    "generator_version": "probabilistic.prepare.generator.v1"
  }
}
```

Behavior:

- `probabilistic_prepare_enabled` comes directly from `Config.PROBABILISTIC_PREPARE_ENABLED`
- supported profiles and metrics come from `backend/app/models/probabilistic.py`
- this surface is global, not project-specific

### `POST /api/simulation/prepare`

New probabilistic request fields:

```json
{
  "simulation_id": "sim_xxx",
  "probabilistic_mode": true,
  "uncertainty_profile": "balanced",
  "outcome_metrics": [
    "simulation.total_actions",
    "platform.twitter.total_actions"
  ]
}
```

Validation rules:

- `probabilistic_mode=true` is required when sending `uncertainty_profile` or `outcome_metrics`
- probabilistic prepare is rejected with `400` when the backend flag is off
- unsupported uncertainty profiles are rejected with `400`
- unsupported outcome metrics are rejected with `400`
- empty `outcome_metrics` falls back to the backend default metric list

Success response additions:

- `probabilistic_mode`
- `uncertainty_profile`
- `outcome_metrics`
- `prepared_artifact_summary`

Compatibility behavior:

- legacy prepare still writes `simulation_config.json`
- probabilistic prepare writes legacy-compatible config plus sidecar artifacts
- a legacy-prepared simulation can be re-prepared in probabilistic mode without `force_regenerate=true`

### `POST /api/simulation/prepare/status`

Current contract:

- accepts optional `probabilistic_mode` so ready checks do not mistake legacy-only artifacts for probabilistic readiness
- probabilistic-ready checks now require the full sidecar set: `simulation_config.base.json`, `uncertainty_spec.json`, `outcome_spec.json`, and `prepared_snapshot.json`
- partial-sidecar states stay non-ready and now surface exact missing filenames in `prepare_info.reason` plus `prepared_artifact_summary.feature_metadata.missing_probabilistic_artifacts`
- returns either task state or `already_prepared=true` with `prepare_info`
- carries `prepared_artifact_summary` through task results when the background task completes

## 3. Implemented artifacts

Legacy artifact preserved:

- `simulation_config.json`

Probabilistic sidecar artifacts:

- `simulation_config.base.json`
- `uncertainty_spec.json`
- `outcome_spec.json`
- `prepared_snapshot.json`

Current summary fields exposed to the frontend:

- `schema_version`
- `generator_version`
- `simulation_id`
- `mode`
- `probabilistic_mode`
- `uncertainty_profile`
- `outcome_metrics`
- `lineage`
- `feature_metadata`
- `artifacts`

Current artifact metadata fields:

- `artifact_type`
- `filename`
- `path`
- `relative_path`
- `exists`
- `size_bytes` when present
- `schema_version` when present
- `generator_version` when present
- `prepared_at` or `generated_at` when present

## 4. Frontend integration rules

Step 2 currently follows these rules:

- if capability discovery reports probabilistic prepare disabled, Step 2 auto-starts the legacy prepare path
- if capability discovery fails, Step 2 falls back to the legacy prepare path and logs the discovery failure
- if probabilistic prepare is enabled, Step 2 still auto-starts the legacy baseline prepare
- after the legacy baseline is ready, Step 2 exposes an explicit probabilistic re-prepare action for the same simulation
- when a new probabilistic prepare begins, Step 2 clears stale config/task/progress state and keeps the Step 3 handoff unavailable until the active prepare task reaches a terminal state or the backend reports `already_prepared`
- probabilistic Step 2 exposes:
  - mode toggle
  - prepared-run-count input for later Step 3 ensemble sizing
  - uncertainty profile selector
  - outcome metric selection
  - explicit prepare CTA
  - compact prepared-artifact summary panel
- UI wording must describe prepared artifacts and empirical metrics only; it must not imply runtime sampling, calibration, or supported probability bands

## 5. Known limitations

- no backend-advertised run-budget min/max contract exists yet; the current Step 2 prepared-run count is validated only as a positive integer before ensemble creation
- seeded resolver and stored concrete run generation now exist in the backend, but Step 2 evidence still does not prove runtime execution
- `prepared_artifact_summary` is a provenance surface, not an analytical artifact
- Step 2 now has deterministic fixture-backed Playwright coverage for the prepared probabilistic state, but it still lacks repeatable non-fixture operator evidence
- Step 3 now has a truthful probabilistic ensemble browser, Step 4 now has a bounded observed ensemble addendum, and Step 5 now has an explicit unsupported-state banner, but grounded probabilistic report/chat semantics are still incomplete

## 6. Evidence

Verified code and tests:

- `backend/app/models/probabilistic.py`
- `backend/app/services/simulation_manager.py`
- `backend/app/api/simulation.py`
- `backend/tests/unit/test_probabilistic_schema.py`
- `backend/tests/unit/test_probabilistic_prepare.py`
- `frontend/src/api/simulation.js`
- `frontend/src/components/Step2EnvSetup.vue`

Verified commands:

- `cd backend && .venv/bin/python -m pytest tests/unit/test_probabilistic_prepare.py tests/unit/test_probabilistic_ensemble_api.py -q`
- `cd frontend && node --test tests/unit/probabilisticRuntime.test.mjs`
- `npm run verify`
- `npm run verify:smoke`
