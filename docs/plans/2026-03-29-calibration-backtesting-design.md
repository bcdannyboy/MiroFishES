# Calibration And Backtesting Design

## Goal

Add the first real calibration and backtesting layer without changing the meaning of the existing empirical ensemble outputs. Calibration must only appear in the product when explicit historical-case artifacts exist and pass a conservative readiness gate.

## North-Star Alignment

The forecasting-upgrades plan calls for a forecast-centric workflow with explicit truth, scoring, and later calibration. This wave should establish that substrate by introducing durable historical-truth and scoring artifacts, but it should not imply that every ensemble summary is calibrated. The empirical layer remains the default truth source for simulation outputs; calibration is additive and opt-in through artifacts.

## Current Context

- `aggregate_summary.json` already exposes empirical run aggregation.
- `probabilistic_report_context.py` currently labels all report context semantics as empirical or observational.
- `Config` already exposes `CALIBRATED_PROBABILITY_ENABLED`, but that flag is only a rollout capability today.
- The repo has outcome metrics with binary, categorical, and continuous value kinds, but it does not yet have a durable predictive-distribution artifact for continuous outcomes.

## Design Choice

Use an additive artifact lane rather than folding calibration into `aggregate_summary.json`.

Why this is the right v1:
- It preserves the existing empirical semantics and backward compatibility.
- It makes calibration inspectable and auditable as a separate derivation step.
- It keeps report-context gating simple: calibrated summaries appear only when explicit calibration artifacts exist and are ready.

## Artifact Model

### 1. Observed Truth Registry

Add a lightweight historical-case artifact, `observed_truth_registry.json`, under the ensemble directory.

Purpose:
- persist the case-level inputs needed for scoring
- separate observed truth from derived scores
- provide a durable shape for later richer backtests

Proposed shape:
- `artifact_type`: `observed_truth_registry`
- `schema_version`, `generator_version`
- `simulation_id`, `ensemble_id`
- `cases`: list of historical-case records

Each case record should include:
- `case_id`
- `metric_id`
- `forecast_probability` for binary scoring when available
- `observed_value`
- `resolved_at` or `observed_at`
- `source_run_id` or provenance metadata when the forecast came from stored run/ensemble artifacts
- optional `notes` and `warnings`

The registry is intentionally lightweight. It is not a general event store.

### 2. Backtest Summary

Add `backtest_summary.json` as the empirical scoring artifact.

Purpose:
- compute proper scores from case-level forecast and truth pairs
- keep raw scoring separate from calibration summaries

Proposed shape:
- `artifact_type`: `backtest_summary`
- `schema_version`, `generator_version`
- `simulation_id`, `ensemble_id`
- `quality_summary`
- `metric_backtests`

Each metric backtest should include:
- `metric_id`
- `value_kind`
- `case_count`
- `scoring_rules`
- `case_results`: compact per-case score records
- aggregate fields such as:
  - `mean_brier_score`
  - `mean_log_score` when valid
- warnings for unsupported or degraded cases

### 3. Calibration Summary

Add `calibration_summary.json` as the binary calibration artifact.

Purpose:
- summarize whether forecast probabilities align with observed frequencies
- expose reliability bins and readiness/confidence metadata

Proposed shape:
- `artifact_type`: `calibration_summary`
- `schema_version`, `generator_version`
- `simulation_id`, `ensemble_id`
- `quality_summary`
- `metric_calibrations`

Each metric calibration should include:
- `metric_id`
- `value_kind`
- `case_count`
- `supported_scoring_rules`
- `scores`
- `reliability_bins`
- `readiness`
- `warnings`

`readiness` should include:
- `ready`: boolean
- `minimum_case_count`: 10
- `actual_case_count`
- `non_empty_bin_count`
- `gating_reasons`
- `confidence_label`

## Supported Semantics In V1

### Supported

- Binary outcomes:
  - Brier score
  - log score with conservative clipping metadata
  - reliability / calibration bins
- Readiness gating metadata
- Explicit separation between:
  - empirical summaries
  - empirical backtest summaries
  - calibrated summaries

### Deferred

- CRPS
- continuous predictive calibration
- multiclass calibration
- recalibration transforms
- claims of calibrated forecasting at runtime

CRPS is intentionally deferred because the repo currently stores empirical outcome summaries, not durable predictive CDF or sample-weight artifacts that can support a clean CRPS contract without inventing semantics.

## Readiness Gate

Use the approved moderate gate.

A metric-level calibration is ready only when:
- the metric is binary
- at least 10 resolved cases exist
- at least 2 reliability bins are non-empty
- at least one supported proper score was computed cleanly

If a calibration artifact exists but readiness is false:
- keep the artifact on disk
- expose readiness metadata and warnings
- do not surface calibrated summaries in report context

## Service Boundaries

### `backtest_manager.py`

Responsibilities:
- load the observed-truth registry
- validate case records
- compute per-case and aggregate scores
- write `backtest_summary.json`

### `calibration_manager.py`

Responsibilities:
- read `backtest_summary.json`
- filter to supported binary metrics
- build reliability bins
- compute readiness/confidence metadata
- write `calibration_summary.json`

### `ensemble_manager.py`

Additive responsibilities:
- persist and load observed-truth, backtest, and calibration artifacts
- avoid altering aggregate-summary semantics

### `probabilistic_report_context.py`

Keep the default report context empirical.

Only add a `calibrated_summary` section when:
- a calibration artifact exists
- the artifact validates
- at least one metric is readiness-passing

Otherwise:
- keep empirical semantics unchanged
- optionally surface a narrow warning that calibration artifacts are unavailable or not ready

## API Surface

Keep API changes conservative.

Recommended v1:
- expose calibration availability only through existing capability/report surfaces where already appropriate
- avoid new write APIs unless local tests show a real need
- if a read endpoint is needed, prefer an existing ensemble/report artifact fetch pattern over a new workflow surface

## Testing Strategy

Follow strict TDD:
- artifact schema round trips
- deterministic score calculations
- reliability bin construction
- readiness gating
- report-context gating
- backward compatibility proving that empirical outputs are unchanged when no calibration artifacts exist

## Success Criteria

This wave succeeds if:
- historical truth and scoring artifacts can be persisted and reloaded
- binary Brier/log scoring works deterministically
- calibration bins and readiness metadata are produced conservatively
- report context only exposes calibrated summaries when valid ready artifacts exist
- the codebase still treats ordinary empirical ensemble outputs as uncalibrated
