# What MiroFishES Adds

This document explains how the current MiroFishES repo differs from the fork-era MiroFish baseline.

It is intentionally phrased in terms of the repo you are holding, not a live audited comparison against an external upstream repository. Where the repo is still bounded or partial, it says so explicitly.

## Fork-Era Baseline

The fork-era baseline can be summarized as:

1. ingest source material
2. build a graph-backed world
3. configure and run a simulation
4. produce a report
5. explore the result through an interaction surface

That baseline is still present in this repo as the legacy single-run path.

## How MiroFishES Has Diverged

MiroFishES extends that baseline into an artifact-first forecasting stack.

### 1. Forecast control plane

The repo now supports a bounded forecast-first path with durable artifacts instead of only transient setup state.

Key additions:

- `forecast_brief.json`
- `uncertainty_spec.json`
- `outcome_spec.json`
- `prepared_snapshot.json`
- `ensemble_spec.json`
- `ensemble_state.json`
- `run_manifest.json`
- `resolved_config.json`

Meaning:

- Step 2 can prepare a forecast-oriented control packet.
- Step 3 can operate on stored runs and explicit ensemble state rather than only one ephemeral run.

### 2. Upstream grounding layer

The repo now preserves a durable upstream evidence layer:

- `source_manifest.json`
- `graph_build_summary.json`
- `grounding_bundle.json`

Meaning:

- later forecast steps can point to uploaded-source and graph-build provenance
- report and interaction surfaces can cite bounded upstream evidence instead of only simulation outputs

Boundary:

- this is not comprehensive research grounding
- this is not exhaustive external code-analysis grounding

### 3. Scope-aware analytics

The repo now treats `ensemble`, `cluster`, and `run` as explicit scope levels across reporting and interaction.

Key additions:

- `aggregate_summary.json`
- `scenario_clusters.json`
- `sensitivity.json`
- explicit `cluster_id` and scope routing in downstream report and chat flows

Meaning:

- scenario-family analysis is no longer just an implicit prompt concept
- operators can inspect ensemble-wide, family-level, and run-level evidence separately

Boundary:

- scenario families are empirical, not causal
- sensitivity is observational, not intervention-proof

### 4. Confidence lane

The repo now has a narrow, inspectable confidence layer:

- `observed_truth_registry.json`
- `backtest_summary.json`
- `calibration_summary.json`

Meaning:

- the repo can preserve observed truth and backtesting results
- a named binary metric can surface backtested calibration provenance when all readiness gates are satisfied

Boundary:

- this does not make the whole system calibrated
- non-binary metrics remain empirical or observed only

### 5. Probabilistic report and interaction surfaces

The repo now has additive report-context and report-agent layers that understand the forecast artifacts.

Key addition:

- `probabilistic_report_context.json`

Meaning:

- Step 4 and Step 5 can surface explicit scope, grounding status, support, warnings, scenario-family evidence, run evidence, and confidence status
- Step 5 report-agent chat can use bounded scope-aware context and one bounded compare handoff

Boundary:

- the report body is still legacy-shaped
- interviews and surveys remain legacy-scoped

### 6. Compare and operator surfaces

The repo now includes:

- a stored-run Step 3 operator shell
- a bounded Step 4 compare workspace
- Step 5 compare-aware report-agent prompts
- smoke and live operator verification surfaces

Meaning:

- MiroFishES is no longer only a “generate one report and inspect it” flow
- operators can recover, rerun, compare, and reopen saved probabilistic state

Boundary:

- compare is still bounded to one saved report context at a time
- cross-report and cross-simulation compare remain unsupported
- the strongest fresh live proof still depends on having a forecast-ready local simulation family

## Summary Table

| Area | Fork-era baseline | MiroFishES now |
| --- | --- | --- |
| Simulation flow | single-run oriented | legacy path plus bounded forecast-first control plane |
| Upstream provenance | mostly transient or implicit | durable source, graph, and forecast-facing grounding artifacts |
| Scope model | mostly one active run/report | explicit `ensemble`, `cluster`, and `run` scope |
| Analytics | direct run outputs | aggregate summaries, scenario families, observational sensitivity |
| Confidence | implicit probability language risk | observed truth, backtests, bounded binary calibration provenance |
| Report/interaction | legacy report and interaction | additive probabilistic report context and scope-aware report-agent lane |
| Compare/operator | limited | stored-run operations, compare workspace, history re-entry |

## What Still Does Not Exist

MiroFishES still does **not** truthfully support:

1. comprehensive research grounding
2. comprehensive code-analysis grounding
3. causal scenario analysis
4. broad calibrated forecasting beyond the named ready binary metric artifacts
5. release-grade local operator proof

## Where To Look Next

- [Root README](../README.md): front door and fresh-start workflow
- [Documentation guide](README.md): audience-based reading paths
- [Forecasting integration hardening wave](plans/2026-03-29-forecasting-integration-hardening-wave.md): current implementation contract
- [Local probabilistic operator runbook](local-probabilistic-operator-runbook.md): operational usage and recovery guidance
