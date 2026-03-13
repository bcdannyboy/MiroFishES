# Stochastic Probabilistic Report Context Contract

**Date:** 2026-03-09

## 1. Purpose

Define the first live H4 report-context artifact plus the current Step 4 and bounded Step 5 integration seams.

This contract is intentionally additive:

- it does not replace the legacy report body or section-streaming flow
- it packages already-persisted ensemble analytics into one report-ready sidecar
- it keeps empirical, observed, and observational evidence labels explicit
- it does not imply calibrated probabilities or full ensemble/run/cluster Step 5 grounding

## 2. Current producer and consumers

Current producer:

- `backend/app/services/probabilistic_report_context.py`

Current report integration seam:

- `backend/app/api/report.py`
- `backend/app/services/report_agent.py`

Current frontend consumers:

- `frontend/src/views/ReportView.vue`
- `frontend/src/components/Step4Report.vue`
- `frontend/src/components/ProbabilisticReportContext.vue`
- `frontend/src/views/InteractionView.vue`
- `frontend/src/components/Step5Interaction.vue`

Current non-consumers:

- Step 5 interview and survey lanes inside `frontend/src/components/Step5Interaction.vue`
- `backend/app/api/simulation.py` interaction endpoints

## 3. Artifact location and persistence

Primary persisted artifact:

- `uploads/simulations/<simulation_id>/ensemble/ensemble_<ensemble_id>/probabilistic_report_context.json`

Current report embedding behavior:

- when `POST /api/report/generate` receives `ensemble_id`, the backend builds the report-context artifact and also stores the resulting payload in `uploads/reports/<report_id>/meta.json` as `probabilistic_context`

Legacy compatibility:

- legacy report generation without `ensemble_id` or `run_id` still works
- legacy reports keep `ensemble_id = null`, `run_id = null`, and `probabilistic_context = null`

## 4. Root fields

Current root fields:

- `artifact_type`: `probabilistic_report_context`
- `schema_version`: `probabilistic.report_context.v1`
- `generator_version`: `probabilistic.report_context.generator.v1`
- `simulation_id`
- `ensemble_id`
- `run_id`
- `scope`
- `probability_mode`
- `probability_semantics`
- `prepared_artifact_summary`
- `ensemble_facts`
- `top_outcomes`
- `scenario_families`
- `representative_runs`
- `selected_run`
- `sensitivity_overview`
- `quality_summary`
- `aggregate_summary`
- `scenario_clusters`
- `sensitivity`
- `source_artifacts`
- `generated_at`

Current scope semantics:

- `scope.level = "ensemble"` when no explicit run was requested
- `scope.level = "run"` when a selected run is part of the report request and can be resolved

## 5. Evidence semantics

Current provenance rules:

- `ensemble_facts` and `top_outcomes` are `empirical`
- `scenario_families` are `empirical`
- `selected_run` and `representative_runs` are `observed`
- `sensitivity_overview` is `observational`

Current probability-language rule:

- no field in this artifact may imply calibration unless a future calibrated artifact and flag-backed contract land first

Current warning behavior:

- thin-sample, degraded-run, missing-metrics, invalid-artifact, and observational-only warnings are preserved from the underlying aggregate artifacts instead of being rewritten into optimistic prose

## 6. Current Step 4 and bounded Step 5 behavior

Current Step 4 and Step 5 consumer behavior:

- Step 3 now includes `ensemble_id` and `run_id` when starting probabilistic report generation
- `ReportView.vue` reconstructs probabilistic Step 4 state from saved report metadata instead of relying only on route query state
- `ProbabilisticReportContext.vue` prefers the embedded `probabilistic_context` payload and falls back to direct `/summary`, `/clusters`, and `/sensitivity` fetches only when the embedded context is absent
- `InteractionView.vue` now reconstructs probabilistic Step 5 state from saved report metadata instead of relying only on route query state
- `POST /api/report/chat` now accepts optional `report_id`, validates that it belongs to the requested `simulation_id`, loads the exact saved report when present, and injects saved `probabilistic_context` into the report-agent prompt
- the legacy report body, section streaming, and log timeline remain intact

Current UI scope:

- Step 4 renders additive observed analytics cards for aggregate summary, scenario clusters, and sensitivity
- those cards are report-scoped addenda, not proof that the generated markdown report body itself is ensemble-aware
- Step 5 now shows an explicit banner when saved probabilistic context exists, and the report-agent chat lane can use that saved report context without implying that interviews or surveys are ensemble-aware
- history can reopen Step 4 and Step 5 through a saved `report_id`, but that is still report-rooted re-entry rather than ensemble-history support

## 7. Known gaps and explicit deferrals

Still absent:

- report markdown sections generated directly from report-context fields
- calibrated probability presentation
- cluster drilldown beyond summary-card level
- tail-risk comparison views
- Step 5 run-vs-cluster-vs-ensemble scope selection
- Step 5 answer-level provenance display for report-agent answers
- Step 5 interview and survey grounding on saved probabilistic context
- ensemble-history replay that is independent of the current simulation/report history model

Current H4 status:

- partially implemented

Reason:

- the artifact, report metadata persistence, the initial Step 4 consumer, exact-report Step 5 chat grounding, and saved-report Step 5 re-entry are now real, but broader Step 5 scope semantics and the fuller unsupported-claim package are still deferred
