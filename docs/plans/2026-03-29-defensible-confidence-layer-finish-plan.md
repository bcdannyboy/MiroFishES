# Defensible Confidence Layer Finish Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Finish the strongest defensible in-repo confidence layer by hardening binary backtesting and calibration, making readiness and failure states explicit, and removing capability or report-language overclaims.

**Architecture:** Keep the existing empirical ensemble analytics as the default evidence layer. Treat confidence as one additive artifact lane: `observed_truth_registry.json` -> `backtest_summary.json` -> `calibration_summary.json` -> `probabilistic_report_context.json` plus frontend/report surfaces. Deepen binary backtesting and readiness diagnostics rather than broadening into numeric or categorical pseudo-calibration. Only named binary metrics with explicit observed-truth cases and readiness-passing calibration artifacts may be described as backtested calibration.

**Tech Stack:** Python 3.12, Flask, pytest, Vue 3, Vite, Playwright, JSON artifact contracts under `backend/uploads/simulations/`.

---

## Audit Summary

The current repo already has a narrow calibration substrate, but it is not yet a finished confidence layer.

- `ObservedTruthRegistry`, `BacktestSummary`, and `CalibrationSummary` already exist in [backend/app/models/probabilistic.py](backend/app/models/probabilistic.py), but they still use the generic prepare schema version and carry only thin provenance.
- [backend/app/services/backtest_manager.py](backend/app/services/backtest_manager.py) scores binary cases only, using explicit `forecast_probability` values already stored on the registry cases. It does not add class-balance diagnostics, baseline comparison, or strong skip-reason accounting.
- [backend/app/services/calibration_manager.py](backend/app/services/calibration_manager.py) builds reliability bins and a readiness gate, but readiness is currently based only on total case count, bin coverage, and score presence. It does not require both outcome classes, and it does not surface a stronger operator-facing not-ready state.
- [backend/app/services/probabilistic_report_context.py](backend/app/services/probabilistic_report_context.py) only exposes ready calibration metrics. If a calibration artifact exists but is not ready, Step 4 and Step 5 collapse that state to silence instead of an honest bounded warning.
- [frontend/src/utils/probabilisticRuntime.js](frontend/src/utils/probabilisticRuntime.js) still maps the rollout flag `calibrated_probability_enabled` to the user-facing label `calibrated`, which overstates the actual contract because that flag only enables artifact reading; it does not prove any ready artifact exists.
- The supported outcome registry contains many binary metrics that are eligible for confidence work in principle, but the repo still does not persist frozen predictive distributions for continuous or categorical outcomes. That makes broader calibration work indefensible in this phase.

## Phase Decisions

1. Keep calibration binary-only in this phase.
2. Deepen binary scoring, provenance, and readiness rather than broadening to continuous or categorical calibration.
3. Distinguish `absent`, `not_ready`, and `ready` confidence states end-to-end.
4. Reserve the word `calibrated` for named binary metrics with ready calibration artifacts only.
5. Add repo-local build and verification entry points so the confidence lane is reproducible outside unit tests.

## What Is Feasible And Worth Finishing Now

### Worth finishing now

- stronger observed-truth provenance for explicit historical binary cases
- richer binary backtest diagnostics:
  - Brier score
  - log score
  - Brier skill score against the empirical base-rate baseline
  - observed event rate
  - mean forecast probability
  - positive-case and negative-case counts
  - explicit skipped-case and unsupported-metric accounting
- stronger binary calibration diagnostics:
  - reliability bins
  - expected calibration error
  - maximum calibration gap
  - explicit readiness gates for minimum cases, class balance, and bin support
- report-context and frontend exposure of calibration state even when artifacts are present but not ready
- repo-local scripts and package-level verification so the workflow is not test-only

### Not worth finishing now

- continuous calibration
- categorical or multiclass calibration
- CRPS or other sample-distribution scoring for continuous outcomes
- scenario-family or selected-run calibration claims
- recalibration transforms, isotonic fitting, or Platt-style post-processing
- any global `highest-confidence` or system-wide calibrated claim

The current repo does not persist a frozen predictive-distribution contract for non-binary metrics, so broadening beyond binary would create pseudo-rigor.

## What The Repo Can Truthfully Call Calibrated After This Phase

After this phase, the repo may truthfully say:

- `Backtested calibration is available for <metric_id> at ensemble scope`
- `Calibration readiness is ready for <metric_id>`
- `This named binary metric has limited or moderate backtested calibration support`

Only when all of the following are true:

1. an explicit `observed_truth_registry.json` exists for the ensemble
2. `backtest_summary.json` exists and validates
3. `calibration_summary.json` exists and validates
4. the metric is binary and marked confidence-eligible in the outcome registry
5. readiness gates pass for that metric
6. Step 4 or Step 5 is citing that named metric, not the whole report or whole forecast

After this phase, the repo must still not say:

- the forecast system is globally calibrated
- the report body is calibrated
- a whole scenario family or selected run is calibrated
- continuous, categorical, or time-to-event outcomes are calibrated
- causal confidence, strongest-cause, or highest-confidence prediction is proven

## Supported Metric Families After This Phase

Confidence-eligible:

- any outcome metric whose registry metadata says `value_kind == "binary"`
- this includes existing binary event or threshold families such as:
  - simulation completion or activity flags
  - thresholded concentration or dominance flags
  - platform-presence and platform-balance threshold flags
  - cross-platform transfer observed flags
  - thresholded content concentration flags

Not confidence-eligible:

- `numeric` metrics
- `categorical` metrics
- continuous duration metrics
- raw counts, ratios, and concentration values without explicit binary resolution semantics

## Interface And Artifact Contract

### Artifact files to keep

- `observed_truth_registry.json`
- `backtest_summary.json`
- `calibration_summary.json`
- `probabilistic_report_context.json`

Do not rename these files. Later phases and runbooks already refer to them.

### Versioning decision

Keep filenames stable but bump written schema versions for confidence artifacts:

- `observed_truth_registry.json` -> `probabilistic.observed_truth.v2`
- `backtest_summary.json` -> `probabilistic.backtest.v2`
- `calibration_summary.json` -> `probabilistic.calibration.v2`
- `probabilistic_report_context.json` -> `probabilistic.report_context.v3` if `confidence_status` is added there

Loaders must continue to accept the existing v1 shapes from the current repo.

### New or strengthened fields

`observed_truth_registry.json`

- registry-level:
  - `registry_scope`
  - `quality_summary`
  - `notes`
- per case:
  - `metric_id`
  - `value_kind`
  - `forecast_probability`
  - `forecast_source`
  - `forecast_issued_at`
  - `forecast_scope`
  - `observed_source`
  - `observed_at`
  - `resolution_note`
  - `warnings`

`backtest_summary.json`

- registry-wide:
  - `quality_summary.total_case_count`
  - `quality_summary.scored_case_count`
  - `quality_summary.skipped_case_count`
  - `quality_summary.supported_metric_ids`
  - `quality_summary.unscored_metric_ids`
  - `quality_summary.warnings`
- per metric:
  - `case_count`
  - `positive_case_count`
  - `negative_case_count`
  - `observed_event_rate`
  - `mean_forecast_probability`
  - `scores.brier_score`
  - `scores.log_score`
  - `scores.brier_skill_score`
  - `warnings`

`calibration_summary.json`

- per metric:
  - `diagnostics.expected_calibration_error`
  - `diagnostics.max_calibration_gap`
  - `diagnostics.observed_event_rate`
  - `diagnostics.mean_forecast_probability`
  - `readiness.ready`
  - `readiness.gating_reasons`
  - `readiness.minimum_case_count`
  - `readiness.minimum_positive_case_count`
  - `readiness.minimum_negative_case_count`
  - `readiness.minimum_supported_bin_count`
  - `readiness.confidence_label`

`probabilistic_report_context.json`

- always include `confidence_status`:
  - `status`: `absent | not_ready | ready`
  - `supported_metric_ids`
  - `ready_metric_ids`
  - `not_ready_metric_ids`
  - `gating_reasons`
  - `warnings`
  - `boundary_note`
- keep `calibrated_summary` and `calibration_provenance`, but only when at least one metric is ready

### Capability-surface contract

Keep `calibrated_probability_enabled` for compatibility in `/api/simulation/prepare/capabilities`, but treat it as a rollout flag only.

Add one explicit capability field that states the truthful contract:

- `calibration_artifact_support_enabled`
- `calibration_surface_mode`: `artifact-gated`

Frontend copy must stop translating the rollout flag into `calibrated`.

## Task 1: Tighten Outcome And Observed-Truth Contracts

**Files:**
- Modify: `backend/app/models/probabilistic.py`
- Modify: `backend/tests/unit/test_probabilistic_schema.py`
- Modify: `backend/app/services/backtest_manager.py`

**Implementation steps:**

1. Add failing schema tests for confidence-eligible binary metrics, stronger observed-truth provenance, and confidence-artifact schema versions.
2. Extend the outcome metric registry so each metric exposes confidence support metadata explicitly.
3. Add additive observed-truth fields for forecast provenance and resolution provenance.
4. Keep existing loaders backward-compatible with current registry payloads.

**Decision detail:**

- Confidence eligibility is metadata-driven, not inferred ad hoc in report context.
- The registry continues to allow non-binary metrics to exist, but they must be marked unsupported for scoring and calibration in downstream artifacts.

## Task 2: Deepen Binary Backtesting

**Files:**
- Modify: `backend/app/services/backtest_manager.py`
- Modify: `backend/app/services/ensemble_manager.py`
- Modify: `backend/tests/unit/test_backtest_manager.py`
- Create: `backend/tests/fixtures/confidence/observed_truth_registry.ready.json`
- Create: `backend/tests/fixtures/confidence/observed_truth_registry.not_ready.json`

**Implementation steps:**

1. Add failing tests for:
   - binary scoring with Brier, log score, and Brier skill score
   - positive-case and negative-case counts
   - skipped binary cases with missing forecast probability
   - unsupported non-binary metrics remaining visible as unscored, not silently dropped
2. Extend `BacktestManager` so `quality_summary` reports supported, scored, skipped, and unsupported counts cleanly.
3. Persist explicit per-metric diagnostics needed by the calibration layer.
4. Keep backtesting binary-only in this phase.

**Decision detail:**

- Add Brier skill score against the empirical base-rate baseline because it is cheap, interpretable, and defensible for binary outcomes.
- Do not add continuous or categorical scoring in this phase.

## Task 3: Strengthen Calibration Diagnostics And Readiness Gates

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/app/services/calibration_manager.py`
- Modify: `backend/tests/unit/test_calibration_manager.py`
- Modify: `backend/app/models/probabilistic.py`

**Implementation steps:**

1. Add failing tests for:
   - readiness false when all outcomes are one class
   - readiness false when non-empty bins exist but per-bin support is too thin
   - readiness true only with minimum case count, both outcome classes, and supported-bin coverage
   - expected calibration error and max calibration gap calculation
2. Add explicit config values:
   - `CALIBRATION_MIN_CASE_COUNT`
   - `CALIBRATION_MIN_POSITIVE_CASE_COUNT`
   - `CALIBRATION_MIN_NEGATIVE_CASE_COUNT`
   - `CALIBRATION_MIN_SUPPORTED_BIN_COUNT`
   - keep `CALIBRATION_BIN_COUNT`
3. Extend `CalibrationManager` to compute:
   - expected calibration error
   - maximum calibration gap
   - observed event rate
   - mean forecast probability
4. Tighten readiness gates so binary calibration is not marked ready unless both classes are present and the bins have real support.
5. Keep confidence labels bounded:
   - `insufficient`
   - `limited`
   - `moderate`
   - never `high`

**Decision detail:**

- Diagnostics such as ECE and max gap inform operator confidence, but they are not themselves a license to label the whole system calibrated.
- Readiness should not depend on hitting an arbitrary “good enough” ECE threshold in this phase. Surface the diagnostic; gate readiness on support quality.

## Task 4: Expose Confidence State Truthfully In Report Context And Frontend

**Files:**
- Modify: `backend/app/services/probabilistic_report_context.py`
- Modify: `backend/tests/unit/test_probabilistic_report_context.py`
- Modify: `backend/tests/unit/test_probabilistic_report_api.py`
- Modify: `frontend/src/utils/probabilisticRuntime.js`
- Modify: `frontend/src/components/Step2EnvSetup.vue`
- Modify: `frontend/src/components/ProbabilisticReportContext.vue`
- Modify: `frontend/src/components/Step5Interaction.vue`
- Modify: `frontend/tests/unit/probabilisticRuntime.test.mjs`
- Modify: `tests/smoke/probabilistic-runtime.spec.mjs` only if Step 4 or Step 5 copy/layout changes materially

**Implementation steps:**

1. Add failing tests for:
   - absent calibration artifacts -> `confidence_status.status == "absent"`
   - present but not-ready artifacts -> `confidence_status.status == "not_ready"` with gating reasons
   - ready artifacts -> `confidence_status.status == "ready"` plus `calibrated_summary`
   - Step 2 capability state no longer rendering `calibrated` from config alone
2. Extend report context so `confidence_status` is always present and `calibration_provenance` remains ready-only.
3. Update frontend capability copy so Step 2 says `artifact-gated` or equivalent instead of `calibrated`.
4. Update Step 4 and Step 5 evidence cards so operators can tell the difference between:
   - no calibration artifacts
   - artifacts present but not ready
   - ready backtested calibration for named metrics

**Decision detail:**

- The operator should always be able to tell whether calibration is unavailable, merely insufficient, or actually ready.
- Only ready metrics may produce a calibration provenance card.

## Task 5: Add Repo-Local Build And Verification Entry Points

**Files:**
- Create: `backend/scripts/build_confidence_artifacts.py`
- Create: `backend/tests/unit/test_build_confidence_artifacts_script.py`
- Modify: `package.json`

**Implementation steps:**

1. Add a repo-local script that:
   - loads one observed-truth registry
   - writes `backtest_summary.json`
   - writes `calibration_summary.json`
   - exits non-zero on malformed registries
   - optionally exits non-zero on not-ready calibration with `--strict-ready`
2. Add a focused script test using fixture registries.
3. Add one repo-level script alias such as `npm run verify:confidence` that runs the focused confidence suite.

**Decision detail:**

- Do not add live service mutation APIs in this phase unless the implementation proves a real need.
- A repo-local script is enough to make the confidence lane reproducible and testable.

## Compatibility Rules

- Keep artifact filenames stable.
- Keep existing config keys stable; add clearer aliases rather than renaming in place.
- Keep `calibrated_summary` and `calibration_provenance` field names stable for ready metrics.
- Additive fields are preferred. If a schema version changes, loaders must continue to read current v1/v2 payloads.

## Documentation To Update

- `README.md`
- `docs/local-probabilistic-operator-runbook.md`
- `docs/plans/2026-03-29-forecasting-integration-hardening-wave.md`

Documentation must state:

- calibration is binary-only in this repo after the phase
- the rollout flag is not the same thing as a ready calibration artifact
- `calibrated` means named-metric backtested calibration only
- numeric and categorical metrics remain empirical or observed only

## Acceptance Criteria

- a binary metric with sufficient cases, both outcome classes, and supported bin coverage writes a ready `calibration_summary.json`
- that ready metric appears in `probabilistic_report_context.json` as calibration provenance and a ready calibrated summary
- a present but not-ready calibration artifact yields `confidence_status.status == "not_ready"` with explicit gating reasons
- the frontend no longer labels the stack `calibrated` from config alone
- unsupported non-binary metrics remain visible as unsupported or unscored; they are not mislabeled calibrated
- docs and runbook use the same bounded meaning of `calibrated`

## Exact Verification Commands

Run these commands during implementation:

1. `cd /Users/danielbloom/Desktop/MiroFishES/backend && python3 -m pytest tests/unit/test_probabilistic_schema.py tests/unit/test_backtest_manager.py tests/unit/test_calibration_manager.py tests/unit/test_probabilistic_report_context.py tests/unit/test_probabilistic_report_api.py tests/unit/test_build_confidence_artifacts_script.py -q`
2. `cd /Users/danielbloom/Desktop/MiroFishES/frontend && node --test tests/unit/probabilisticRuntime.test.mjs`
3. `cd /Users/danielbloom/Desktop/MiroFishES && npm run verify`
4. `cd /Users/danielbloom/Desktop/MiroFishES && npm run verify:smoke`

## End State

If this phase lands correctly, MiroFishES will still not have broad calibrated forecasting. It will, however, have a finished, inspectable, reproducible binary confidence lane with explicit provenance, honest readiness states, and bounded report/operator language. That is the strongest defensible in-repo finish before any broader confidence claim.
