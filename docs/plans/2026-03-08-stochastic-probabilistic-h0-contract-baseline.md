# Stochastic Probabilistic Simulation H0 Contract Baseline

**Date:** 2026-03-10

This document is the H0 baseline package for the stochastic probabilistic simulation program. It captures the repo-grounded control state that the current implementation is extending from.

## 1. Purpose

H0 exists to give backend, frontend, integration, and release work one shared baseline package for:

- current implemented IDs
- current implemented artifacts
- current implemented routes and state ownership
- known gaps between legacy implementation and the probabilistic target

## 2. Current implemented identity model

Implemented IDs:

- `project_id`
- `graph_id`
- `simulation_id`
- `mode` as Step 2/Step 3 route and runtime metadata for the current dual-mode handoff
- `ensemble_id` in backend storage/API scope under one simulation
- `run_id` in backend storage/API scope under one ensemble
- `report_id`

Planned but not yet implemented IDs:

- `cluster_id`

Current ownership:

| Field / ID | Current owner | Current meaning | Notes |
| --- | --- | --- | --- |
| `project_id` | graph/project APIs + frontend process flow | uploaded-document and graph-build project root | stable |
| `graph_id` | graph build + simulation prepare | graph used to derive entities and report context | stable |
| `simulation_id` | backend prepare/runtime/report lookup + frontend Step 2/3 | single prepared simulation and runtime root | overloaded today; will remain parent identity after ensemble work |
| `mode` | frontend Step 2 state, Step 3 through Step 5 route/query state, and prepared-artifact summary | current legacy-vs-probabilistic handoff metadata | implemented as read-only handoff metadata through Step 5; still not a history primary identity |
| `ensemble_id` | backend ensemble storage/runtime APIs plus frontend Step 2 through Step 5 route handoff | one stored family of resolved runs under a simulation | implemented for storage/API scope, `SimulationRunner` runtime scope, Step 3 route/query reload, and Step 4/Step 5 read-only handoff; `report_id` still remains the canonical report/interaction route identity |
| `run_id` | backend resolver/storage/runtime scope plus frontend Step 2 through Step 5 route handoff | one concrete stored run under an ensemble | implemented for storage/API scope, `SimulationRunner`, the current Step 3 probabilistic browser, and Step 4/Step 5 read-only handoff; still not a history durable owner |
| `report_id` | report backend + frontend Step 4/5 | one generated report rooted in one simulation | stable for legacy flow |

## 3. Current implemented artifact set

Prepare-path artifacts actually present today:

- `state.json`
- `simulation_config.json`
- `simulation_config.base.json` in probabilistic mode
- `uncertainty_spec.json` in probabilistic mode
- `outcome_spec.json` in probabilistic mode
- `prepared_snapshot.json` in probabilistic mode
- `reddit_profiles.json`
- `twitter_profiles.csv`

Runtime/report artifacts actually present today:

- `run_state.json`
- `simulation.log`
- `twitter/actions.jsonl`
- `reddit/actions.jsonl`
- `metrics.json` for stored ensemble runs
- `aggregate_summary.json` for stored ensembles
- `scenario_clusters.json` for stored ensembles
- `reports/<report_id>/meta.json`
- `reports/<report_id>/outline.json`
- `reports/<report_id>/full_report.md`
- `reports/<report_id>/agent_log.jsonl`
- `reports/<report_id>/console_log.txt`

Probabilistic analytics artifacts now implemented:
- `sensitivity.json`
- `probabilistic_report_context.json`

Probabilistic storage artifacts now implemented:

- `ensemble/ensemble_<ensemble_id>/ensemble_spec.json`
- `ensemble/ensemble_<ensemble_id>/ensemble_state.json`
- `ensemble/ensemble_<ensemble_id>/runs/run_<run_id>/resolved_config.json`
- `ensemble/ensemble_<ensemble_id>/runs/run_<run_id>/run_manifest.json`

## 4. Current route and surface baseline

Implemented backend endpoints in the legacy plus additive probabilistic flow:

- `/api/simulation/create`
- `/api/simulation/prepare/capabilities`
- `/api/simulation/prepare`
- `/api/simulation/prepare/status`
- `/api/simulation/start`
- `/api/simulation/<simulation_id>`
- `/api/simulation/<simulation_id>/ensembles`
- `/api/simulation/<simulation_id>/ensembles/<ensemble_id>`
- `/api/simulation/<simulation_id>/ensembles/<ensemble_id>/runs`
- `/api/simulation/<simulation_id>/ensembles/<ensemble_id>/runs/<run_id>`
- `/api/simulation/<simulation_id>/ensembles/<ensemble_id>/runs/<run_id>/actions`
- `/api/simulation/<simulation_id>/ensembles/<ensemble_id>/runs/<run_id>/timeline`
- `/api/simulation/<simulation_id>/ensembles/<ensemble_id>/runs/<run_id>/start`
- `/api/simulation/<simulation_id>/ensembles/<ensemble_id>/runs/<run_id>/stop`
- `/api/simulation/<simulation_id>/ensembles/<ensemble_id>/runs/<run_id>/run-status`
- `/api/simulation/<simulation_id>/ensembles/<ensemble_id>/start`
- `/api/simulation/<simulation_id>/ensembles/<ensemble_id>/status`
- `/api/simulation/<simulation_id>/ensembles/<ensemble_id>/summary`
- `/api/simulation/<simulation_id>/ensembles/<ensemble_id>/clusters`
- `/api/simulation/<simulation_id>/ensembles/<ensemble_id>/sensitivity`
- `/api/simulation/<simulation_id>/run-status`
- `/api/simulation/<simulation_id>/actions`
- `/api/simulation/history`
- `/api/report/generate`
- `/api/report/generate/status`
- `/api/report/<report_id>`
- `/api/report/chat`

Implemented frontend route baseline:

- `/process/:projectId`
- `/simulation/:simulationId`
- `/simulation/:simulationId/start` with `mode`, `ensembleId`, and `runId` query-state support for the current probabilistic Step 3 browser
- `/report/:reportId` with read-only `mode`, `ensembleId`, and `runId` query-state handoff for the bounded probabilistic addendum
- `/interaction/:reportId` with read-only `mode`, `ensembleId`, and `runId` query-state handoff for the explicit unsupported probabilistic banner

Missing probabilistic route/state surface:

- Step 3 still owns the live probabilistic browser state, while Step 4 and Step 5 now preserve that context only as read-only handoff metadata rather than durable route identity
- no dedicated compare/history route for ensembles
- no cluster-aware interaction scope
- history still cannot replay live Step 3 probabilistic state, but Step 4 and Step 5 can now reopen a saved probabilistic report through the existing report-centric history flow

## 5. Legacy compatibility rule

The legacy single-run path remains the current production truth and must keep working throughout the probabilistic rollout.

Compatibility implications:

- `simulation_config.json` remains supported until all runtime consumers can use the probabilistic artifact set
- Step 2 auto-prepare remains available when probabilistic prepare is disabled or capability discovery fails
- when probabilistic prepare is enabled, Step 2 still auto-starts the legacy baseline prepare and then offers an explicit probabilistic re-prepare path
- legacy Step 3 monitoring must remain available until probabilistic runtime work is explicitly flagged and verified
- reports must not claim probabilities that are unsupported by aggregate artifacts

## 6. Remaining gaps after prepare-plus-storage slices

Still missing after the current prepare, runtime, and first analytics slices:

- backend-advertised run-budget limits for the new Step 2 prepared-run control
- broader Step 3 history/replay and operator recovery controls beyond the current browser
- fuller Step 4 report-body probabilistic integration and grounded Step 5 interaction scope
- ensemble-aware history/replay
- repeatable non-fixture happy-path Step 1 -> Step 5 browser evidence beyond the deterministic fixture-backed smoke matrix
- release-grade rollout and telemetry evidence

## 7. Package members

This H0 package consists of:

- `docs/plans/2026-03-08-stochastic-probabilistic-status-audit.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-readiness-dashboard.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-h1-prepare-path-contract.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-h2-ensemble-storage-contract.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-h2-runtime-contract-draft.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-frontend-ux-contract.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-report-context-contract.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-sensitivity-contract.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-gate-evidence-ledger.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-decision-log.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-execution-log.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-delivery-governance.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-integration-dependency-map.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-backend-task-register.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-frontend-task-register.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-integration-task-register.md`

## 8. Review owners

| Area | Owner lane | Current review need |
| --- | --- | --- |
| artifact and runtime identities | Backend | high |
| UX vocabulary and state ownership | Frontend | high |
| handoffs, gates, rollout evidence | Integration | high |
| PM consistency and decision log | Program/PM | high |
