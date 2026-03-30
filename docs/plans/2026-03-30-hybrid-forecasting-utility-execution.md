# Hybrid Forecasting Utility Execution Ledger

**Date:** 2026-03-30

**Phase:** NB Active-Path Readiness Expansion

## Phase Checklist

- `P0` Complete
- `P1` Complete
- `P2` Complete
- `NB0` Complete
- `NB1` Complete
- `NB2` Complete
- `NB3` Complete
- `NB4` Complete
- `NB5` Complete
- `NB6` Complete

## Baseline Carried Forward

The repo already carried forward:

- truthful simulation-preservation semantics
- canonical forecast workspace primitives
- typed question service, evidence bundle, prediction ledger, and hybrid worker base
- historical conformance quarantine for archived non-ready simulations
- stable saved-history replay and live report-generation repair work

This phase extended that baseline to active-path non-binary readiness rather than replacing it.

## Completed Work

- Reset the canonical support matrix so the active path is explicitly:
  - `binary`
  - `categorical`
  - `numeric`
  - `scenario`
- Reclassified threshold-style prompts to the `binary` lane and added true numeric templates:
  - `numeric_value_by_horizon`
  - `numeric_range_by_horizon`
- Extended the forecasting domain contract so typed question specs, prediction ledger values, evaluation cases, answer payloads, and capability metadata all carry categorical and numeric semantics.
- Hardened service and API validation so:
  - categorical questions reject binary-only probability payloads
  - numeric resolved outcomes reject non-numeric values
  - typed categorical labels stay aligned with the declared question spec
- Landed non-binary hybrid engine behavior:
  - base-rate and reference-class workers emit typed categorical or numeric outputs when appropriate
  - retrieval-synthesis worker emits typed categorical or numeric judgments
  - simulation remains a supporting scenario worker with `observed_run_share` semantics only
- Landed answer-native aggregation:
  - categorical answers surface normalized distributions, top labels, rival labels, disagreement, and counterevidence
  - numeric answers surface point estimates, units, intervals, disagreement, and counterevidence
- Extended forecast-answer evaluation and calibration evidence so categorical and numeric readiness is answer-bound rather than inherited from ensemble artifacts.
- Hardened frontend/runtime formatting so:
  - categorical answers render as named distributions
  - numeric answers render as point-plus-interval estimates
  - percentages are only used for probability semantics
- Extended smoke fixtures and smoke coverage to include:
  - categorical typed hybrid answers
  - numeric typed hybrid answers
- Extended the scanner and tests so typed calibrated forecast answers are validated honestly without reopening archived history as an active-path blocker.
- Added and used `npm run verify:nonbinary` as the dedicated targeted non-binary verification surface.
- Updated the wrapper script, runbook, README-level truth boundaries, and March 30 design/ledger docs to match the implemented active-path non-binary contract.

## Files Changed

- `backend/app/models/forecasting.py`
- `backend/app/services/forecast_engine.py`
- `backend/app/services/forecast_manager.py`
- `backend/app/services/hybrid_forecast_service.py`
- `backend/app/services/probabilistic_report_context.py`
- `backend/app/services/probabilistic_smoke_fixture.py`
- `backend/scripts/scan_forecasting_artifacts.py`
- `backend/scripts/create_probabilistic_smoke_fixture.py`
- `backend/tests/unit/test_forecasting_schema.py`
- `backend/tests/unit/test_forecast_manager.py`
- `backend/tests/unit/test_forecast_api.py`
- `backend/tests/unit/test_forecast_engine.py`
- `backend/tests/unit/test_hybrid_forecast_service.py`
- `backend/tests/unit/test_probabilistic_report_context.py`
- `backend/tests/unit/test_probabilistic_report_api.py`
- `backend/tests/unit/test_scan_forecasting_artifacts_script.py`
- `frontend/src/components/ProbabilisticReportContext.vue`
- `frontend/src/components/Step2EnvSetup.vue`
- `frontend/src/components/Step5Interaction.vue`
- `frontend/src/utils/forecastRuntime.js`
- `frontend/src/utils/probabilisticRuntime.js`
- `frontend/tests/unit/forecastRuntime.test.mjs`
- `frontend/tests/unit/probabilisticRuntime.test.mjs`
- `tests/smoke/probabilistic-runtime.spec.mjs`
- `scripts/verify-forecasting.sh`
- `README.md`
- `docs/what-mirofishes-adds.md`
- `docs/local-probabilistic-operator-runbook.md`
- `docs/plans/2026-03-30-hybrid-forecasting-utility-design.md`
- `docs/plans/2026-03-30-hybrid-forecasting-utility-execution.md`

## Verification Run

- `node --test frontend/tests/unit/forecastRuntime.test.mjs`
  - `9 passed`
- `npm run verify:smoke`
  - `10 passed`
- `npm run verify:nonbinary`
  - backend: `92 passed`
  - frontend: `79 passed`
- `npm run verify:confidence`
  - backend: `100 passed`
  - frontend: `79 passed`
- `npm run verify:forecasting:artifacts`
  - passed
  - `125` active simulations inspected
  - `122` probabilistic prepared simulations scanned
  - `121` probabilistic report contexts scanned
  - `0` standalone forecast workspaces present in the default forecast directory for this repo snapshot
- `npm run verify:forecasting:artifacts:all`
  - passed
  - `141` archived simulations explicitly quarantined as non-ready historical evidence
- `PLAYWRIGHT_LIVE_ALLOW_MUTATION=true npm run verify:operator:local`
  - `2 passed`
- `npm run verify:forecasting`
  - passed
  - wrapper now runs broad verify, targeted non-binary verify, confidence verify, active artifact scan, and smoke
- `npm run verify`
  - frontend:
    - `84` unit tests passed
    - `vite build` succeeded
  - backend:
    - `295 passed`
    - existing `PytestConfigWarning` remains

## Failures Found

- The March 30 design and execution docs still described the repo as intentionally binary-bounded even after the typed categorical/numeric evaluation and calibration path had landed.
- The README, runbook, and Step 2 disclaimer still used older binary-only calibration wording.
- The forecasting wrapper script did not include `verify:nonbinary`, and its summary text no longer matched the number of evidence surfaces after the non-binary gate was added.
- The typed numeric smoke path initially lacked explicit regression coverage for interval arrays from the smoke fixture shape.

## Remediations Applied

- Rewrote the March 30 design doc around active-path `binary` / `categorical` / `numeric` readiness while preserving the simulation scenario boundary.
- Rewrote the March 30 execution ledger to track `NB0` through `NB6` explicitly and to record the fresh verification evidence.
- Updated user-facing wording in:
  - `README.md`
  - `docs/what-mirofishes-adds.md`
  - `docs/local-probabilistic-operator-runbook.md`
  - `frontend/src/components/Step2EnvSetup.vue`
- Updated `scripts/verify-forecasting.sh` so the wrapper now runs `npm run verify:nonbinary` alongside broad verify, confidence verify, artifact scan, and smoke.
- Added a regression test for numeric interval arrays in `frontend/tests/unit/forecastRuntime.test.mjs`.
- Re-ran smoke, operator-local, confidence, non-binary, artifact, and broad verification after the fixes.

## Before / After Evidence

- Before:
  - March 30 docs still described broader non-binary readiness as out of scope
  - the verification ladder did not surface `verify:nonbinary`
  - the numeric smoke fixture shape was not explicitly regression-tested in the frontend runtime
- After:
  - docs, UI copy, wrapper scripts, and runtime semantics all describe the same active-path non-binary contract
  - categorical and numeric Step 4/5 smoke coverage is green
  - the live operator-local Step 4/5 path is green
  - the dedicated non-binary verification surface is present and green

## Unresolved Risks

- strategic recommendation mode is still out of scope and remains a separate product expansion
- archived historical simulations remain `quarantined_non_ready` when appropriate and still must not be treated as active readiness evidence
- the default forecast workspace directory is empty in this repo snapshot, so typed artifact scanning is currently evidenced through scanner unit tests plus the active Step 4/5 path rather than checked-in persisted workspaces
- live Step 2 prepare still depends on real environment configuration for LLM/Zep-backed flows
- existing frontend chunk-size warnings remain unresolved
- existing backend `PytestConfigWarning` remains unresolved

## Phase Status

### P0

- `Truthfulness hardening remains intact:` complete
- `Workflow and epistemic semantics remain separated:` complete
- `Simulation-frequency language remains descriptive and bounded:` complete

### P1

- `Canonical forecast questions, evidence bundles, prediction ledgers, and hybrid workers remain intact:` complete
- `Simulation remains one worker inside the hybrid architecture:` complete
- `Legacy workspace compatibility remains intact:` complete

### P2

- `Evaluation registries, benchmarks, backtests, and provenance-carrying answers remain integrated:` complete
- `Step 4 and Step 5 expose the hybrid workspace and distinguish evidence, evaluation, calibrated confidence, and simulation-only scenario exploration:` complete
- `Saved-history replay and live operator report generation remain stable:` complete
- `Historical conformance stays explicit and quarantined when non-ready:` complete

### NB0

- `Canonical support matrix explicitly covers binary, categorical, numeric, and scenario lanes:` complete
- `Threshold prompts are treated as binary and true numeric templates are available:` complete
- `Capability metadata exposes typed answer payloads and calibration kinds:` complete

### NB1

- `Forecast questions, prediction ledgers, evaluation cases, and APIs are type-correct for categorical and numeric lanes:` complete
- `Service-layer validation rejects silent binary assumptions in typed lanes:` complete

### NB2

- `Categorical evaluation and benchmark summaries are implemented:` complete
- `Numeric evaluation and interval-aware benchmark summaries are implemented:` complete
- `Typed evaluation outputs surface through forecast answers and ledgers:` complete

### NB3

- `Categorical and numeric answers earn calibration only through type-correct evidence:` complete
- `Evaluation availability and calibrated confidence earned remain separate:` complete
- `Unsupported or weakly supported answers stay uncalibrated or abstain:` complete

### NB4

- `Typed workers emit categorical and numeric outputs:` complete
- `Aggregation produces answer-native categorical and numeric forecast answers:` complete
- `Simulation remains supporting scenario analysis and does not dominate stronger workers:` complete

### NB5

- `Step 4 and Step 5 render categorical and numeric answers honestly:` complete
- `Supported-question templates and abstain UX remain visible:` complete
- `Smoke and operator-local flows validate the typed active path:` complete

### NB6

- `verify:nonbinary is the canonical targeted non-binary verification surface:` complete
- `Artifact tooling and wrapper scripts align to the typed active-path contract:` complete
- `Runbooks and docs match the implemented active-path non-binary contract:` complete
