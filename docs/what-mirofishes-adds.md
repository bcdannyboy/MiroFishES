# What MiroFishES Adds

This file is the plain-language fork delta. It describes what is actually present in this repo now, not an audited comparison against some external upstream at a matching commit.

## The Real Delta

### 1. Step 2 is no longer only transient setup

The original flow mostly moved from graph build into one simulation run. MiroFishES adds a Step 2 artifact layer:

- `forecast_brief.json`
- `uncertainty_spec.json`
- `outcome_spec.json`
- `prepared_snapshot.json`
- `grounding_bundle.json`

That matters because Step 2 can now prepare a forecast-oriented control packet before any Step 3 run is launched.

### 2. Step 2 handoff and Step 3 operate on stored shells

The next change is operational, not rhetorical.

Step 2 handoff creates or reopens stored Step 3 run shells. Step 3 then lets the operator launch, stop, retry, clean up, or branch those shells. A prepared shell is still passive until launch.

That is different from the old single-run path, but it is still bounded. The repo is not claiming some larger automated forecasting certainty here than the stored-shell contract supports.

### 3. The repo keeps a bounded upstream grounding layer

MiroFishES persists:

- `source_manifest.json`
- `graph_build_summary.json`
- `grounding_bundle.json`

That gives later steps a durable record of what source and graph-build evidence was attached. It does not mean the system has comprehensive research grounding or exhaustive code-analysis grounding.

### 4. Reporting and interaction now understand scope

The repo treats `ensemble`, `cluster`, and `run` as explicit scope levels across Step 4 and the Report Agent lane in Step 5.

That scope travels through saved report metadata, history replay, and scoped report-agent requests. It is a real contract, not just prompt wording.

### 5. Analytics are more inspectable

The forecasting layer adds persisted analytics artifacts such as:

- `aggregate_summary.json`
- `scenario_clusters.json`
- `sensitivity.json`
- `simulation_market_manifest.json`
- `runtime_graph_state.json`
- `probabilistic_report_context.json`

Those artifacts let the UI surface support counts, representative runs, selected family context, compare choices, and explicit evidence boundaries.

The boundary still matters:

- aggregate and cluster summaries are empirical
- selected runs are observed
- sensitivity is descriptive or designed-comparison evidence, not causal proof

### 6. There is a narrow confidence lane

The repo can persist:

- `backtest_summary.json`
- `calibration_summary.json`

and expose `answer_confidence_status` in saved report context.

That does not make the whole system calibrated. It only means a supported binary, categorical, or numeric answer lane can pass the confidence gate when the type-correct calibration artifact, backtest artifact, and provenance checks all pass.

### 7. History and compare are better, but still bounded

Compared with the fork-era baseline, the repo now supports:

- reopening saved probabilistic Step 3 state
- reopening saved probabilistic Step 4 and Step 5 state
- one bounded compare workspace inside a saved report context

It still does not support cross-report or cross-simulation compare.

## What Still Does Not Exist

MiroFishES still does not truthfully support:

- comprehensive research grounding
- comprehensive code-analysis grounding
- causal scenario analysis
- broad calibrated forecasting beyond the supported evaluated binary, categorical, and numeric answer lanes with validated provenance
- release-grade live operator proof

## Where To Go Next

- [Root README](../README.md): setup, verification ladder, and readiness terms
- [Local probabilistic operator runbook](local-probabilistic-operator-runbook.md): local operator behavior and recovery paths
- [Forecast readiness chain ledger](plans/2026-03-31-forecast-readiness-chain.md): current implementation contract, phase handoffs, and final readiness evidence
- [Forecast readiness status](plans/2026-03-31-forecast-readiness-status.json): machine-readable phase status and verification record
- [Forecasting integration hardening wave](plans/2026-03-29-forecasting-integration-hardening-wave.md): historical integration hardening context
