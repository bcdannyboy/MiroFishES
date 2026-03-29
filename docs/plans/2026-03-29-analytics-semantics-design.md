# Analytics Semantics And Defensible Scenario Analysis Design

## Goal

Unify analytics semantics across aggregate summary, scenario clustering, sensitivity analysis, and report context so the probabilistic outputs share one interpretable notion of run eligibility, support, and warning propagation. At the same time, replace the current lossy clustering and exact-value sensitivity heuristics with stronger but still transparent methods.

## Current Problems

The current analytics stack is internally coherent enough to work, but it is not yet defensible enough for forecast-centric use:

- `ensemble_manager.py` decides aggregate inclusion one way.
- `scenario_clusterer.py` separately filters runs and then buckets standardized metrics into `low` / `mid` / `high` signatures.
- `sensitivity_analyzer.py` separately filters runs and groups continuous drivers only by exact resolved value identity.
- `probabilistic_report_context.py` consumes those artifacts but does not yet expose a unified support policy.

This creates three issues:

1. Similar artifacts can refer to different implicit sample sets.
2. Scenario families are too lossy because z-score bucket signatures collapse nearby but meaningfully different runs.
3. Continuous-driver sensitivity is too brittle because numeric values only form groups when they match exactly.

## Design Choice

Use one shared analytics-policy layer plus interpretable heuristic upgrades:

- a shared run-eligibility / sample-policy service
- deterministic medoid-radius clustering for scenario families
- support-aware numeric driver banding for sensitivity

This is the right v1 because it improves defensibility without introducing opaque model-based analytics or rewriting the runtime.

## Shared Analytics Policy

Add a small shared service, likely `backend/app/services/analytics_policy.py`.

Responsibilities:

- load ensemble runs in one consistent way
- classify run eligibility for different analysis modes
- expose support-count and thin-sample defaults
- attach explicit exclusion reasons and warning hints

The policy should be mode-aware because the analyses do not truly need identical inclusion rules:

- `aggregate`: a run may contribute to a metric if the metric exists and is non-null, even if other metrics are absent
- `scenario`: a run must have complete metrics and the shared numeric feature set required for clustering
- `sensitivity`: a run must have complete metrics plus resolved-value driver data
- `report_context`: should surface the support and warning metadata already computed by the source artifacts

The important part is not forcing one eligibility rule everywhere. The important part is forcing one explicit policy framework everywhere.

## Aggregate Summary Changes

`aggregate_summary.json` should stay empirical, but it should gain clearer sample-policy semantics:

- metric-level support counts
- minimum-support warnings
- explicit eligible/ineligible run counts where helpful
- artifact-level sample-policy metadata describing how counts were computed

This remains an empirical summary, not a calibrated or causal one.

## Scenario Families

Replace z-score bucket signatures with deterministic medoid-radius clustering on standardized numeric outcome vectors.

### Why

The current bucket signature method is easy to explain, but it is overly lossy because many distinct numeric configurations collapse into the same three-bin label vector.

### Proposed method

1. Use the shared analytics policy to select eligible runs and the shared numeric feature space.
2. Standardize the vector with persisted means and standard deviations.
3. Build deterministic clusters using an interpretable distance rule:
   - sort runs deterministically
   - start a cluster from an unassigned seed
   - absorb nearby runs whose standardized distance stays within a fixed radius
   - choose the medoid as the prototype run
4. Persist:
   - the standardized feature schema
   - the radius threshold
   - per-cluster support counts and probability mass
   - cluster dispersion / stability hints
   - medoid prototype and distinguishing metrics

This is still heuristic, but it is less lossy and more faithful than the current bucket grouping while staying traceable.

## Sensitivity

Keep the methodology observational, but change numeric driver grouping from exact identity to support-aware ordered bands.

### Proposed grouping

- binary drivers: group by identity
- categorical drivers: group by identity
- numeric drivers: bin deterministically into 2-3 ordered groups using quantile-style cut points, while enforcing a minimum-support floor

Each driver impact should persist:

- driver kind
- grouping policy
- bin boundaries or category values
- support counts and support shares
- effect size and relative effect
- stability warnings when the support floor is barely met or one group dominates

This makes continuous-variable analysis much more defensible without pretending it is causal.

## Warnings And Support Rules

Support and stability metadata should be visible in every artifact, not reconstructed later.

Common warning families:

- `thin_sample`
- `minimum_support_not_met`
- `unstable_grouping`
- `partial_feature_space`
- `degraded_run_metrics`
- `observational_only`

Each artifact should also expose explicit support counts, not just warnings.

## Report Context

`probabilistic_report_context.py` should remain honest:

- aggregate outcomes are empirical
- scenario families are empirical clusters
- sensitivity is observational only

The report context should surface the improved support counts, minimum-support flags, and stability warnings from the source artifacts rather than inventing stronger interpretations.

## Versioning

Version where methodology meaning changes:

- `scenario_clusters` should move to a new schema version because the core grouping method changes
- `sensitivity` should move to a new schema version because numeric grouping semantics change

`aggregate_summary` can stay additive if the current contract survives with added support metadata. If implementation shows a hard semantic break, version it too.

## What This Wave Will Not Do

- causal inference
- black-box clustering with no traceable artifact logic
- SHAP-like or model-driven sensitivity
- counterfactual claims
- recalibration or forecasting changes

## Success Criteria

This wave succeeds if:

- all four analytics consumers reuse one explicit sample-policy layer
- cluster artifacts are less lossy and retain interpretable prototypes
- sensitivity no longer relies on exact-value identity for continuous drivers
- support counts and stability warnings are visible throughout the pipeline
- report context keeps the semantics empirical or observational, never causal
