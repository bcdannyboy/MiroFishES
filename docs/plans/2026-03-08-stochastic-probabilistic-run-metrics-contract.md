# Stochastic Probabilistic Run Metrics Contract

**Date:** 2026-03-08

## 1. Purpose

Define the real B3.1 run-level analytics artifact that now exists in code.

This contract is intentionally narrower than the broader aggregate-analytics package:

- it covers one stored ensemble member run only
- it does not expose empirical probabilities or aggregate ensemble summaries
- it does not change the legacy single-run runtime filesystem contract

## 2. Scope

Current producer:

- `backend/app/services/outcome_extractor.py`

Current integration seam:

- `backend/app/services/simulation_runner.py`

Current storage scope:

- only stored probabilistic ensemble members (`ensemble_<id>/runs/run_<id>/`)

Current legacy behavior:

- legacy single-run roots do not automatically emit `metrics.json`

## 3. Artifact location and lifecycle

Artifact path:

- `uploads/simulations/<simulation_id>/ensemble/ensemble_<ensemble_id>/runs/run_<run_id>/metrics.json`

Creation behavior:

- emitted when run-scoped metrics extraction is invoked from the probabilistic runner seam
- written for completed runs and may also be written for stopped/failed runs so partial logs remain explicitly inspectable
- persistence failures are logged as analytics degradation and must not rewrite the already-established terminal runtime status

Cleanup behavior:

- `cleanup_simulation_logs()` deletes `metrics.json`
- cleanup also removes the `metrics` pointer from `run_manifest.json`

Manifest linkage:

- `run_manifest.json.artifact_paths.metrics = "metrics.json"` after persistence

## 4. Root fields

Current root fields:

- `artifact_type`: `run_metrics`
- `schema_version`: `probabilistic.metrics.v1`
- `generator_version`: `probabilistic.metrics.generator.v1`
- `simulation_id`
- `ensemble_id`
- `run_id`
- `requested_metric_ids`
- `metric_values`
- `event_flags`
- `timeline_summaries`
- `top_agents`
- `top_topics`
- `quality_checks`
- `source_artifacts`
- `extracted_at`

`extracted_at` is now derived from persisted run artifacts (`run_state.completed_at`, `run_state.updated_at`, or `run_manifest.generated_at`) before falling back to wall clock time. Re-running extraction against unchanged artifacts should therefore remain stable.

## 5. Metric catalog

The first-pass B3.1 metric catalog is limited to the explicit B0.2 registry already locked in code:

- `simulation.total_actions`
- `platform.twitter.total_actions`
- `platform.reddit.total_actions`

Each `metric_values[metric_id]` entry currently carries the standardized metric definition plus a concrete `value`.

This slice does not add new forecast metrics, calibrated probabilities, or aggregate statistics.

## 6. Quality and completeness semantics

`quality_checks` currently records:

- `is_complete`
- `status`: `complete` or `partial`
- `run_status`
- `log_completeness`
- `has_any_actions_log`
- `missing_platform_logs`
- `missing_simulation_end_platforms`
- `missing_artifacts`
- `warnings`
- `timeline_matches_total_actions`
- `used_default_requested_metric_ids`
- `requested_metric_ids`
- `observed_platforms`
- `top_topics_available`
- `legacy_layout_fallback_used`

Interpretation:

- missing platform logs and missing simulation-end markers are recorded explicitly instead of being silently ignored
- failed/stopped runs remain distinguishable through `run_status` and warning flags
- the persisted `run_state.platform_mode` is now used to avoid falsely marking intentional single-platform runs as incomplete when only one platform was launched
- aggregate consumers must treat `status=partial` as degraded evidence, not as full-fidelity output

## 7. Supporting summaries

`event_flags` currently exposes:

- `simulation_completed`
- `run_completed`
- `run_failed`
- `run_stopped`
- `platform_completion`

`timeline_summaries` currently exposes:

- `round_count`
- `first_round`
- `first_round_num`
- `last_round`
- `last_round_num`
- `total_actions`
- `max_actions_in_round`
- `first_action_time`
- `last_action_time`

`top_agents` currently ranks observed agents by action volume.

`top_topics` currently derives observational counts from configured hot topics plus observed action payloads when topic strings are present. This is support metadata only, not a probabilistic metric.

## 8. Explicit non-goals

This contract does not yet provide:

- `aggregate_summary.json`
- scenario clustering
- sensitivity analysis
- probabilistic report context
- calibrated confidence language
