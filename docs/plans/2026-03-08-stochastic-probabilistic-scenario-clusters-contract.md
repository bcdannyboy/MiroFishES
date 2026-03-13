# Stochastic Probabilistic Scenario Clusters Contract

**Date:** 2026-03-08

## 1. Purpose

Define the real B3.3 scenario-clustering artifact that now exists in code.

This contract intentionally stays empirical and conservative:

- it groups only stored ensemble runs that have complete `metrics.json` evidence
- it uses standardized metric signatures plus prototype runs, not narrative labels
- it does not claim calibration, causal drivers, or report-ready scenario summaries

## 2. Producer and access path

Current producer:

- `backend/app/services/scenario_clusterer.py`

Current API route:

- `GET /api/simulation/<simulation_id>/ensembles/<ensemble_id>/clusters`

Persistence behavior:

- `ScenarioClusterer.get_scenario_clusters()` rebuilds and persists `scenario_clusters.json` on demand

Artifact path:

- `uploads/simulations/<simulation_id>/ensemble/ensemble_<ensemble_id>/scenario_clusters.json`

## 3. Root fields

Current root fields:

- `artifact_type`: `scenario_clusters`
- `schema_version`: `probabilistic.clusters.v1`
- `generator_version`: `probabilistic.clusters.generator.v1`
- `simulation_id`
- `ensemble_id`
- `cluster_count`
- `clusters`
- `feature_vector_schema`
- `quality_summary`
- `source_artifacts`
- `generated_at`

## 4. Feature-vector behavior

Current `feature_vector_schema` fields:

- `metric_ids`
- `standardization`: `zscore`
- `bucket_thresholds`
- `source`: `metrics.json`

Current clustering behavior:

- only numeric `metric_values[*].value` inputs shared across all complete contributing runs are used
- runs with missing, malformed, partial, failed, or stopped `metrics.json` evidence are excluded from cluster membership
- if no shared numeric metrics remain, the artifact returns zero clusters and surfaces that condition explicitly through `quality_summary.warnings`

Current implementation does not cluster on raw narratives, report copy, or chat/log text.

## 5. Cluster payload behavior

Each `clusters[]` entry currently carries:

- `cluster_id`
- `run_count`
- `probability_mass`
- `prototype_run_id`
- `member_run_ids`
- `feature_signature`
- `centroid`
- `distinguishing_metrics`
- `prototype_resolved_values`
- `prototype_top_topics`
- `warnings`

Current prototype semantics:

- the prototype run is the member nearest the cluster centroid in raw metric space
- ties break deterministically by the lowest `run_id`

Current mass semantics:

- `probability_mass` is normalized against total prepared ensemble runs, not only the subset that remained clusterable
- if some runs are missing or degraded, the cluster masses therefore sum to less than `1.0`

## 6. Quality semantics

`quality_summary` currently exposes:

- `status`: `complete` or `partial`
- `total_runs`
- `runs_with_metrics`
- `clustered_runs`
- `missing_metrics_runs`
- `invalid_metrics_runs`
- `degraded_metrics_runs`
- `invalid_manifest_runs`
- `warnings`

Current warnings:

- `thin_sample`
- `missing_run_metrics`
- `invalid_run_metrics`
- `degraded_run_metrics`
- `no_shared_numeric_metrics`
- `low_confidence`

Interpretation:

- `thin_sample` means the ensemble coverage is still small and should not be overstated
- `missing_run_metrics` means one or more stored runs do not yet have `metrics.json`
- `invalid_run_metrics` means one or more `metrics.json` artifacts were unreadable and were downgraded to exclusions rather than failing the whole artifact
- `degraded_run_metrics` means one or more stored runs had non-complete quality status and were excluded from membership
- `invalid_run_manifest` means one or more `run_manifest.json` artifacts were unreadable and were downgraded to empty-manifest support data instead of failing the whole artifact
- `no_shared_numeric_metrics` means the current run metrics do not support a stable shared feature space
- `partial_feature_space` means the clusterer had to drop one or more prepared outcome metrics from the shared feature vector because they were not available across all complete contributing runs
- `low_confidence` means clustering exists, but the available sample/variance conditions are too weak for strong scenario-family claims

## 7. Source-artifact linkage

`source_artifacts` currently records:

- `metrics_files`
- `run_manifest_files`
- `outcome_metric_ids`

This contract is therefore grounded in persisted run artifacts rather than inferred directly from raw runtime state.

## 8. Explicit non-goals

This artifact does not yet provide:

- sensitivity analysis
- calibrated probability adjustments
- report-ready cluster narratives
- Step 4 cards
- Step 5 interaction grounding
