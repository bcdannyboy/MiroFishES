# Stochastic Probabilistic Sensitivity Contract

**Date:** 2026-03-09

## 1. Purpose

Define the live `sensitivity.json` artifact and `/sensitivity` API contract for the current probabilistic analytics slice.

This contract is intentionally narrow and conservative.

It exists to expose empirical driver ranking over stored runs without implying:

- controlled perturbation orchestration,
- causal attribution,
- calibrated probabilities,
- or report-ready narrative semantics.

## 2. Current implementation truth

Implemented now:

- `backend/app/services/sensitivity_analyzer.py`
- `GET /api/simulation/<simulation_id>/ensembles/<ensemble_id>/sensitivity`
- `backend/tests/unit/test_sensitivity_analyzer.py`
- sensitivity coverage inside `backend/tests/unit/test_probabilistic_ensemble_api.py`

Current methodology:

- source runs are stored ensemble members only
- only runs with complete `metrics.json` quality and readable manifests participate
- driver values come from `run_manifest.json` `resolved_values`, with `resolved_config.json` `sampled_values` used only as a compatibility fallback
- outcome effects are computed from numeric `metrics.json` values only
- group effects are observational comparisons across identical resolved-value groupings

## 3. Artifact location

`uploads/simulations/<simulation_id>/ensemble/ensemble_<ensemble_id>/sensitivity.json`

The artifact is generated on demand and may be recomputed.

It is versioned by schema/generator fields rather than one opaque version field.

## 4. Root artifact fields

Required root fields:

- `artifact_type`: `sensitivity`
- `schema_version`
- `generator_version`
- `simulation_id`
- `ensemble_id`
- `driver_count`
- `driver_rankings`
- `methodology`
- `quality_summary`
- `source_artifacts`
- `generated_at`

## 5. Methodology contract

Current live values:

- `analysis_mode`: `observational_resolved_values`
- `driver_source`: manifest resolved values with resolved-config fallback
- `outcome_source`: numeric `metrics.json` metric values
- `grouping_policy`: observed identical resolved values
- `effect_size_definition`: max group mean minus min group mean
- `causal_interpretation`: `not_supported`

Consumer rule:

- UI, docs, and reports must describe this artifact as observational and empirical
- consumers must not rename it into perturbation proof, calibrated sensitivity, or causal importance

## 6. Driver ranking fields

Each `driver_rankings[]` entry currently includes:

- `driver_id`
- `field_path`
- `driver_kind`
- `sample_count`
- `distinct_value_count`
- `overall_effect_score`
- `metric_impacts`

Compatibility note:

- `field_path` and `driver_id` currently carry the same value so in-flight consumers can normalize safely
- `metric_effects` is retained as a compatibility alias for `metric_impacts`

Each `metric_impacts[]` entry currently includes:

- `metric_id`
- `effect_size`
- `relative_effect`
- `strongest_groups`
- `group_summaries`

Each `group_summaries[]` entry currently includes:

- `value_label`
- `sample_count`
- `mean`
- `min`
- `max`

## 7. Quality and warning semantics

`quality_summary.status` is:

- `complete` when analyzable runs all have complete metrics plus resolved values
- `partial` when required inputs are missing, degraded, unreadable, or there are no shared numeric metrics

Current warning vocabulary includes:

- `observational_only`
- `thin_sample`
- `missing_run_metrics`
- `invalid_run_metrics`
- `degraded_run_metrics`
- `invalid_run_manifest`
- `missing_resolved_values`
- `no_shared_numeric_metrics`
- `no_varying_drivers`

Consumer rule:

- warnings must be rendered or otherwise preserved for operators
- missing warnings must never be converted into silence or optimistic copy

## 8. API contract

Route:

`GET /api/simulation/<simulation_id>/ensembles/<ensemble_id>/sensitivity`

Response shape:

- success envelope under `data`
- `data` contains the `sensitivity.json` payload

Current guardrails:

- route is gated by probabilistic ensemble storage enablement
- missing simulations or ensembles return explicit resource errors
- route does not fabricate results when artifacts are thin or partial; it returns warnings inside the artifact instead

## 9. Explicit non-goals

This slice does not yet provide:

- controlled perturbation run orchestration
- causal claims
- calibration
- report-context packaging
- frontend Step 4/Step 5 consumers
- tail-risk semantics beyond what later consumers may derive carefully from explicit artifact fields

## 10. Next dependencies

This contract now feeds:

- H3 aggregate analytics packaging
- Step 3 or Step 4 aggregate consumers
- future probabilistic report-context work

The next follow-on work should keep the current warning semantics intact and avoid upgrading the language beyond what the artifact actually proves.
