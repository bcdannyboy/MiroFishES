# Stochastic Probabilistic Simulation Integration and Dependency Map

**Date:** 2026-03-09

## 1. Purpose

This document captures the cross-team dependency structure, critical path, handoffs, and milestone gates required to implement probabilistic simulation without backend/frontend drift.

Detailed execution reference:

- for milestone-to-handoff ownership, evidence, and signoff requirements, use `docs/plans/2026-03-08-stochastic-probabilistic-integration-task-register.md`
- for live delivery status and gate posture, use the status audit, readiness dashboard, H0 baseline, and gate-evidence ledger

## 2. Integration principles

- Backend contracts must stabilize before Step 4 final rendering.
- Legacy single-run functionality must remain supported throughout the program.
- No UI surface should invent probability semantics that the backend cannot support.
- No calibrated probability labels should appear until calibration artifacts exist.

## 3. Shared artifacts that drive cross-team coordination

The following artifacts are the primary handoff objects between teams:

- `simulation_config.base.json`
- `uncertainty_spec.json`
- `ensemble_spec.json`
- `run_manifest.json`
- `resolved_config.json`
- `metrics.json`
- `aggregate_summary.json`
- `scenario_clusters.json`
- `sensitivity.json`
- `probabilistic_report_context.json`

## 4. Integration milestones and cross-team readiness

| Milestone | Backend dependency | Frontend dependency | Integration note |
| --- | --- | --- | --- |
| I0 | Artifact taxonomy approved | UX vocabulary approved | Contract lock point |
| I1 | Prepare flow emits probabilistic artifacts | Step 2 scaffolding can begin | First visible probabilistic mode |
| I2 | Ensemble and run endpoints exist | Step 3 ensemble monitor can begin | Runtime still single-view fallback safe |
| I3 | Aggregate summary exists | Step 4 top outcome cards can begin | First meaningful probabilistic report UI |
| I4 | Scenario clusters and sensitivity exist | Step 4 advanced cards can begin | Cluster provenance rules must be stable |
| I5 | Probabilistic report context exists | Step 5 interaction context can begin | Chat grounding must be explicit |
| I6 | Hardening complete | Broad rollout can begin | Release gate |

## 4.1. Control-system crosswalk

| Roadmap milestone | Integration milestone | Handoff package | Governing gate | Earliest release stage |
| --- | --- | --- | --- | --- |
| M0 | I0 | H0 | G1 | R0 |
| M1 | I1 | H1 | G1 | R0 |
| M2 | I2 draft | H2 draft | G2 | R0 |
| M3 | I2 final | H2 final | G2 | R0 |
| M4 | I3 | H3 | G3 | R1 |
| M5 | I4 | H4 | G4 | R1 |
| M6 | I5 | H5 | G5 | R2 to R3 |
| M7 | I7 | H6 | post-MVP policy gate | post-MVP only |

## 5. Cross-team dependency table

| Item | Producing lane | Consuming lane | Dependency type |
| --- | --- | --- | --- |
| Probabilistic schema definitions | Backend | Frontend, Integration | Hard |
| Prepare API payload | Backend | Frontend Step 2 | Hard |
| Ensemble status payload | Backend | Frontend Step 3 | Hard |
| Aggregate summary artifact | Backend | Frontend Step 3 and Step 4 | Hard |
| Scenario cluster artifact | Backend | Frontend Step 4 and Step 5 | Hard |
| Sensitivity artifact | Backend | Frontend Step 4 | Hard |
| Report context artifact | Backend | Frontend Step 4 and Step 5 | Hard |
| UX copy and labeling rules | Frontend | Backend report language | Soft but important |
| Feature-flag policy | Integration | Backend, Frontend | Hard |

## 6. Critical path

The program critical path is:

1. artifact taxonomy approval
2. prepare-path artifact persistence
3. uncertainty resolver
4. ensemble manager
5. run-scoped runtime
6. metrics extractor
7. aggregate summary
8. probabilistic report context
9. Step 4 report rendering
10. release hardening

If Step 4 begins before items 7 and 8 are stable, rework risk is high.

## 7. Parallel workstreams

### Parallel stream P1

Can begin after I0:

- backend schema module,
- frontend Step 2 control scaffolding,
- governance and rollout planning.

### Parallel stream P2

Can begin after I1:

- uncertainty resolver,
- history-view design,
- Step 2 artifact preview work.

### Parallel stream P3

Can begin after I2:

- Step 3 ensemble monitor,
- metrics-extractor implementation,
- report-card wireframes.

### Parallel stream P4

Can begin after I3:

- scenario cluster UI,
- sensitivity UI,
- Step 5 interaction copy and provenance patterns.

## 8. Handoffs and acceptance packages

### Handoff package H0: contract baseline

Producer:

- integration/program management

Consumers:

- backend
- frontend
- release/ops

Must include:

- current implemented identity model
- current implemented artifact set
- legacy compatibility rules
- current blockers between legacy reality and H1
- links to the status audit, readiness dashboard, and gate ledger

### Handoff package H1: prepare-path contract

Producer:

- backend

Consumers:

- frontend Step 2
- integration QA

Must include:

- example request payload,
- example response payload,
- artifact summary payload,
- error cases,
- feature-flag behavior.

### Handoff package H2: ensemble runtime contract

Producer:

- backend

Consumers:

- frontend Step 3

Must include:

- ensemble status payload,
- batch-start admission-control payload with `started_run_ids`, `deferred_run_ids`, and active-run context,
- run detail payload,
- run list payload,
- failed-run payload,
- legacy single-run fallback behavior.

### Handoff package H3: aggregate analytics contract

Producer:

- backend

Consumers:

- frontend Step 4
- report backend

Must include:

- aggregate summary example,
- scenario cluster example,
- sensitivity example,
- field-level provenance rules.

### Handoff package H4: probabilistic report context contract

Producer:

- backend report team

Consumers:

- frontend Step 5

Must include:

- report-rooted chat context example,
- run-vs-cluster-vs-ensemble grounding rules,
- unsupported claim rules,
- saved-report re-entry rules for Step 4 and Step 5.

### Handoff package H5: release-ops handoff

Producer:

- backend and frontend delivery teams

Consumers:

- engineering lead
- support and rollout owners

Must include:

- feature-flag defaults and rollout order,
- dashboards and alert locations,
- stuck-run and failure-recovery runbook,
- rollback checklist,
- support ownership and escalation path.

### Handoff package H6: calibration and confidence handoff

Producer:

- integration/program management

Consumers:

- post-MVP backend and product owners

Must include:

- graph-confidence status
- calibration readiness status
- explicit non-MVP boundary
- missing evidence and remaining blockers

## 9. Readiness gates

### Gate G1: Contract lock

Required before Phase 1 implementation:

- artifact names locked
- identifier semantics locked
- endpoint naming direction locked

### Gate G2: Runtime lock

Required before Phase 3 UI finalization:

- run-scoped orchestration stable
- no collisions in run artifact storage
- restart and cleanup semantics defined

### Gate G3: Report lock

Required before Step 4 and Step 5 finalization:

- aggregate summary field shapes stable
- scenario cluster field shapes stable
- provenance labels and copy rules approved

### Gate G4: UX/report lock

Required before wider rollout:

- legacy path regression suite passes
- probabilistic path smoke suite passes
- performance and failure budgets understood
- support runbook exists

### Gate G5: Rollout lock

Required before controlled beta and broader rollout:

- feature-flag defaults set
- release evidence bundle reviewed
- rollback checklist reviewed
- operational ownership confirmed

## 10. Recommended sequence for implementation management

1. Lock contracts and artifact names.
2. Build backend preparation artifacts.
3. Build backend run orchestration.
4. Start Step 2 and Step 3 UI scaffolding.
5. Build backend analytics artifacts.
6. Start Step 4 report integration.
7. Build probabilistic report context.
8. Finish Step 5 interaction support.
9. Run hardening and release readiness.

## 11. Integration anti-patterns to avoid

- Frontend building final cards against unstable aggregate JSON.
- Backend exposing probability values without provenance labels.
- Teams treating single-run telemetry charts as ensemble sensitivity analysis.
- Report surfaces rendering prototype-run narratives as if they were the most likely outcome.
- Parallel runtime refactor and UI finalization happening without a stable run identifier contract.
