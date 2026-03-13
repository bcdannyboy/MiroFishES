# Stochastic Probabilistic Aggregate Summary Contract

**Date:** 2026-03-08

## 1. Purpose

Define the real B3.2 ensemble-level analytics artifact that now exists in code.

This contract intentionally remains empirical and uncalibrated:

- it summarizes persisted run-level `metrics.json` artifacts
- it does not create calibrated probabilities
- it does not replace scenario clustering or sensitivity analysis

## 2. Producer and access path

Current producer:

- `backend/app/services/ensemble_manager.py`

Current API route:

- `GET /api/simulation/<simulation_id>/ensembles/<ensemble_id>/summary`

Persistence behavior:

- `EnsembleManager.get_aggregate_summary()` rebuilds and persists `aggregate_summary.json` on demand

Artifact path:

- `uploads/simulations/<simulation_id>/ensemble/ensemble_<ensemble_id>/aggregate_summary.json`

## 3. Root fields

Current root fields:

- `artifact_type`: `aggregate_summary`
- `schema_version`: `probabilistic.aggregate.v1`
- `generator_version`: `probabilistic.aggregate.generator.v1`
- `simulation_id`
- `ensemble_id`
- `metric_summaries`
- `quality_summary`
- `source_artifacts`
- `generated_at`

## 4. Metric summary behavior

Each `metric_summaries[metric_id]` entry currently carries:

- the propagated run-level metric metadata when available
- `sample_count`
- `complete_sample_count`
- `partial_sample_count`
- `missing_sample_count`
- `warnings`

The current aggregator supports three summary modes based on the stored metric `value` shape:

- `binary`
  - `empirical_probability`
  - `counts`
- `categorical`
  - `category_counts`
  - `category_probabilities`
- `continuous`
  - `min`
  - `max`
  - `mean`
  - `quantiles` (`p10`, `p50`, `p90`)

Current production metric inputs are still the B3.1 count-metric catalog, so the live repo mainly exercises the continuous/count path today.

## 5. Quality semantics

`quality_summary` currently exposes:

- `status`: `complete` or `partial`
- `total_runs`
- `runs_with_metrics`
- `complete_runs`
- `partial_runs`
- `missing_metrics_runs`
- `warnings`

Current warnings:

- `thin_sample`
- `degraded_runs_present`
- `missing_run_metrics`

Interpretation:

- `thin_sample` means the ensemble sample size is still small and should not be overstated
- `degraded_runs_present` means one or more contributing runs had partial-quality run metrics
- `missing_run_metrics` means one or more stored runs do not yet have `metrics.json`

## 6. Source-artifact linkage

`source_artifacts` currently records:

- `metrics_files`
- `outcome_metric_ids`

This summary contract is therefore grounded in persisted run artifacts rather than inferred directly from raw runtime state.

## 7. Explicit non-goals

This artifact does not yet provide:

- scenario clustering
- sensitivity analysis
- calibrated probability adjustments
- report-ready narrative context
- user-facing Step 4 cards
