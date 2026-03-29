# Forecasting Integration Hardening Wave

This note is the current architecture and verification snapshot after the 2026-03-29 forecasting-control-plane waves.

It exists to prevent drift between the repo's implementation, the operator runbook, the root README, and older plan documents.

Use this document for the **current contract**, not for the high-level "what is MiroFishES" story.

If you need framing first, read:

- [Root README](../../README.md)
- [Documentation guide](../README.md)
- [What MiroFishES adds](../what-mirofishes-adds.md)

If you need the higher-level ambition rather than the current bounded contract, read:

- [North-star forecast upgrades](2026-03-28-mirofish-high-impact-forecasting-upgrades.md)

## Current architecture

The forecasting stack is now organized around an explicit artifact ladder:

1. Step 1 persists `source_manifest.json` and `graph_build_summary.json` as durable upstream provenance.
2. Step 2 prepare emits control artifacts such as `forecast_brief.json`, `uncertainty_spec.json`, `outcome_spec.json`, `prepared_snapshot.json`, and `grounding_bundle.json`.
3. Ensemble creation persists `ensemble_spec.json`, `ensemble_state.json`, `run_manifest.json`, and `resolved_config.json`.
4. Observed run truth is extracted into `metrics.json`.
5. Shared analytics produce `aggregate_summary.json`, `scenario_clusters.json`, and `sensitivity.json`.
6. Historical scoring produces `backtest_summary.json`, and binary-only calibration produces `calibration_summary.json`.
7. Step 4 and Step 5 consume assembled `probabilistic_report_context.json`, which now always exposes `confidence_status` and only exposes `calibrated_summary` when a named metric is actually ready.

## Truth boundaries

- Aggregate summaries and scenario families are empirical.
- Selected runs are observed.
- Sensitivity is observational, not causal.
- Calibration artifacts are artifact-gated and binary-only; they provide backtested provenance only for the ready metric they name.
- Upstream grounding is bounded to uploaded project sources, persisted graph-build outputs, and repo-local code-analysis artifacts only when explicitly attached.
- The report body is still legacy-shaped; probabilistic context is an evidence layer around it.
- Interviews and surveys remain legacy-scoped even when report-agent chat is probabilistic-context-aware.

## Current Step 2 through Step 5 control-plane contract

- Step 2 is now forecast-first when probabilistic prepare is available; it no longer auto-starts legacy prepare in that case.
- Step 3 remains the stored-run monitor, but it is now also the operator source of report scope selection.
- The active report-context scope is explicit: `ensemble`, `cluster`, or `run`.
- `cluster_id` is now part of the route, saved-report, and report-agent request contract when scenario-family scope is in play.

## Current Step 4 and Step 5 contract

Step 4 now surfaces:

- upstream grounding status, boundary note, and stable citations separately from downstream analytics
- scope (`ensemble`, `cluster`, or `run`)
- support counts
- warnings
- representative runs
- selected scenario-family evidence when cluster membership is known
- selected-run assumption-ledger details where present
- `confidence_status` as `absent`, `not_ready`, or `ready`
- calibration provenance when valid artifacts exist
- one dedicated bounded compare workspace with inspectable left/right scope snapshots and one session-local compare handoff

Step 5 now supports:

- report-agent chat using saved report context
- report-agent chat using explicit route-scoped or manually switched `ensemble|cluster|run` scope
- one optional `compareId` handoff for a bounded compare pair from the current saved report context
- bounded compare starter prompts for run-vs-run, family-vs-family, and run-vs-ensemble questions

Still deferred:

- calibrated forecast claims beyond explicit backtested provenance
- scope-aware interviews or surveys
- cross-report or cross-simulation compare

## Verification status

Strong practical verification for the current surfaces is:

- targeted backend report/report-context tests
- `npm run verify:confidence`
- targeted frontend probabilistic runtime tests
- `npm run verify`
- `npm run verify:smoke`
- `PLAYWRIGHT_LIVE_ALLOW_MUTATION=true npm run verify:operator:local` when local env keys and mutation are acceptable

Current local-evidence truth:

- `npm run verify` and `npm run verify:smoke` are the fresh repo-level evidence for Step 2 through Step 5 contracts.
- the live operator suite is now fail-fast and truthful, but the current default local family `sim_7a6661c37719` is not forecast-ready because `grounding_bundle.json` is missing
- until a forecast-ready local family is supplied through `PLAYWRIGHT_LIVE_SIMULATION_ID`, live operator evidence is fresh only for readiness blocking, not for Step 2 handoff through Step 3 recovery success

Not implied by the current evidence:

- release-grade readiness
- self-contained live probabilistic prepare in a fresh environment without keys
- broad calibrated forecasting support
- causal or globally calibrated compare conclusions
