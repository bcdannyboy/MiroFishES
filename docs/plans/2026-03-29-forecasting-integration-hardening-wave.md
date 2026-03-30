# Forecasting Integration Hardening Wave

This note is the current contract for the bounded forecasting slice. It exists so the README, the runbook, and the code all describe the same thing.

Use it for the current implementation contract, not for ambition or roadmap language.

## Current Contract

The forecasting layer is built around persisted artifacts and bounded scope, not around broad claims of predictive certainty.

### Artifact ladder

1. Step 1 persists `source_manifest.json` and `graph_build_summary.json`.
2. Step 2 prepare emits `forecast_brief.json`, `uncertainty_spec.json`, `outcome_spec.json`, `prepared_snapshot.json`, and `grounding_bundle.json`.
3. Step 2 handoff and Step 3 shell creation persist `ensemble_spec.json`, `ensemble_state.json`, `run_manifest.json`, and `resolved_config.json` for stored shells.
4. Launching a shell in Step 3 produces runtime state, timelines, action traces, and run metrics.
5. Ensemble analytics persist `aggregate_summary.json`, `scenario_clusters.json`, and `sensitivity.json`.
6. Historical scoring and calibration persist `backtest_summary.json` and `calibration_summary.json` when those artifacts exist.
7. Step 4 and Step 5 consume `probabilistic_report_context.json`, which always carries `grounding_context` and `confidence_status`, and only carries `calibrated_summary` or `calibration_provenance` when the confidence gate is actually ready.

### Semantic boundaries

- aggregate and family summaries are empirical
- selected runs are observed
- sensitivity is observational, not causal
- the report body is still legacy-shaped
- only the Report Agent lane in Step 5 is scope-aware
- calibration remains binary-only and metric-specific

## Step 2 Through Step 5 Behavior

- Step 2 prepare writes artifacts and readiness state. It does not launch a run.
- Step 2 handoff creates or reopens stored Step 3 shells.
- Step 3 stays passive until the operator launches a selected shell.
- Step 4 consumes saved context and keeps the probabilistic layer descriptive.
- Step 5 can use saved or route-scoped probabilistic context for the Report Agent lane, but interviews and surveys remain legacy-scoped.

## Readiness Semantics

These terms have distinct meanings in code and tests:

- `artifact completeness`: the required Step 2 probabilistic artifacts exist
- `grounding readiness`: `grounding_bundle.json` exists and reports `status == ready`
- `forecast readiness`: the Step 2 handoff gate that combines artifact completeness and grounding readiness
- `confidence readiness`: a Step 4 and Step 5 gate that requires a supported binary metric, valid calibration and backtest artifacts, and provenance that links calibration back to the stored backtest artifact

`confidence_status` is intentionally narrow:

- `absent`: no usable calibration artifact is attached
- `not_ready`: artifacts may exist, but readiness or provenance still blocks calibrated language
- `ready`: the metric-specific confidence gate has passed

## Verification Snapshot

Fresh verification for this audit was rerun on 2026-03-30.

Passed:

- `npm run verify`
- `npm run verify:confidence`
- `npm run verify:smoke`
- `npm run verify:forecasting`

What that means:

- broad repo health is green
- confidence and provenance contracts are green
- the active forecasting artifact scan found no conformance failures in non-archived saved simulations
- the deterministic Step 2 through Step 5 smoke route is green

What it does not mean:

- live Step 2 prepare is self-contained in a fresh environment
- live operator mutation is safe to run by default
- release-grade readiness exists
- broad calibrated forecasting exists

## Live Operator Boundary

The live operator suite is still the strongest local proof, but it is intentionally gated:

```bash
PLAYWRIGHT_LIVE_ALLOW_MUTATION=true npm run verify:operator:local
```

That command mutates a real local simulation family. It was not run during this audit because the mutation gate was not enabled in the current shell.

When it is run, the suite can auto-select the newest non-archived forecast-ready local simulation if `PLAYWRIGHT_LIVE_SIMULATION_ID` is unset. Archived records and smoke fixtures are excluded from that selection logic.

## Archived vs Active Evidence

Archived historical simulations remain readable, but they are not counted as active forecasting evidence by default.

- `npm run verify:forecasting:artifacts` scans active non-archived simulations
- `npm run verify:forecasting:artifacts:all` includes archived history too
- `npm run forecasting:archive:historical` writes `forecast_archive.json` markers for stale saved simulations
- `/api/simulation/history?include_archived=true` exposes archived records again for manual review

## Related Docs

- [Root README](../../README.md)
- [Documentation guide](../README.md)
- [Local probabilistic operator runbook](../local-probabilistic-operator-runbook.md)
- [North-star forecast upgrades](2026-03-28-mirofish-high-impact-forecasting-upgrades.md)
