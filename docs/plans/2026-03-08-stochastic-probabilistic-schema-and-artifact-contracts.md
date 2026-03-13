# Stochastic Probabilistic Simulation Schema and Artifact Contracts

**Date:** 2026-03-08

## 1. Purpose

Define the new artifact set, who produces it, who consumes it, and whether it is mutable.

## 2. Artifact table

| Artifact | Producer | Consumers | Mutable | Notes |
| --- | --- | --- | --- | --- |
| `simulation_config.base.json` | prepare flow | resolver, UI, report | no | canonical baseline config |
| `uncertainty_spec.json` | prepare flow or user override | resolver, UI | yes by version, no in-place | uncertainty model |
| `outcome_spec.json` | prepare flow or user override | extractor, UI, report | yes by version, no in-place | outcome metric contract |
| `prepared_snapshot.json` | prepare flow | report, audit, support | no | provenance anchor |
| `ensemble_spec.json` | ensemble manager | runtime orchestrator, UI | no after launch | run-family contract |
| `run_manifest.json` | resolver and orchestrator | runtime, analytics, support | append-only | seed and sample trace |
| `resolved_config.json` | resolver | runtime | no | one concrete run config |
| `metrics.json` | outcome extractor | analytics, report, UI | no | run-level structured outputs; current B3.1 contract is documented in `docs/plans/2026-03-08-stochastic-probabilistic-run-metrics-contract.md` |
| `aggregate_summary.json` | analytics | report, UI | replaceable by version | ensemble-level outputs; current B3.2 contract is documented in `docs/plans/2026-03-08-stochastic-probabilistic-aggregate-summary-contract.md` |
| `scenario_clusters.json` | analytics | report, UI, interaction | replaceable by version | cluster view; current B3.3 contract is documented in `docs/plans/2026-03-08-stochastic-probabilistic-scenario-clusters-contract.md` |
| `sensitivity.json` | analytics | report, UI | replaceable by version | observational driver ranking; current B3.4 contract is documented in `docs/plans/2026-03-08-stochastic-probabilistic-sensitivity-contract.md` |
| `probabilistic_report_context.json` | report backend | report agent, UI | replaceable by version | report-ready aggregate context |

## 3. Versioning rules

- every artifact must carry `schema_version` and `generator_version` fields; the live repo does not currently use one single `version` key
- every artifact must carry creation timestamp
- every artifact must carry upstream dependency references
- artifacts may be superseded by new versions, but existing versions should not be overwritten silently

## 4. Directory layout

```text
uploads/simulations/<simulation_id>/
  state.json
  prepared_snapshot.json
  simulation_config.base.json
  uncertainty_spec.json
  outcome_spec.json
  ensemble/
    ensemble_<ensemble_id>/
      ensemble_state.json
      ensemble_spec.json
      aggregate_summary.json
      scenario_clusters.json
      sensitivity.json
      calibration.json
      runs/
        run_<run_id>/
          run_manifest.json
          resolved_config.json
          run_state.json
          simulation.log
          metrics.json
```

## 5. Immutability rules

- `prepared_snapshot.json`: immutable
- `simulation_config.base.json`: immutable
- `resolved_config.json`: immutable
- `run_manifest.json`: append-only or immutable after completion
- `metrics.json`: immutable after extraction
- aggregate artifacts: may be recomputed, but version bump required

## 6. Current implemented note

Implemented today:

- `metrics.json` is now real for stored ensemble runs through B3.1
- `aggregate_summary.json` is now real for stored ensembles through B3.2
- `scenario_clusters.json` is now real for stored ensembles through B3.3
- `sensitivity.json` is now real for stored ensembles through B3.4
- the live root fields and quality semantics are documented in:
  - `docs/plans/2026-03-08-stochastic-probabilistic-run-metrics-contract.md`
  - `docs/plans/2026-03-08-stochastic-probabilistic-aggregate-summary-contract.md`
  - `docs/plans/2026-03-08-stochastic-probabilistic-scenario-clusters-contract.md`
  - `docs/plans/2026-03-08-stochastic-probabilistic-sensitivity-contract.md`

Still absent:

- `probabilistic_report_context.json`
