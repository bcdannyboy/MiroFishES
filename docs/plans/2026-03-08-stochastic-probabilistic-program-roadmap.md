# Stochastic Probabilistic Simulation Program Roadmap

**Date:** 2026-03-08

**Primary references:**

- `docs/plans/2026-03-08-stochastic-probabilistic-simulation-design.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-simulation-implementation-plan.md`

## 1. Purpose of this document

This document is the master project-management roadmap for delivering stochastic probabilistic simulation in MiroFishES.

It is intended to answer five questions:

1. What are the delivery phases?
2. Which workstreams belong to backend, frontend, and integration?
3. Which tasks are on the critical path?
4. Which tasks can be parallelized safely?
5. What are the readiness gates for moving from one phase to the next?

## 2. Documentation pack

This roadmap is the index document for the full PM packet:

- `docs/plans/2026-03-08-stochastic-probabilistic-program-roadmap.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-status-audit.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-readiness-dashboard.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-execution-log.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-h0-contract-baseline.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-h1-prepare-path-contract.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-h2-ensemble-storage-contract.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-h2-runtime-contract-draft.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-gate-evidence-ledger.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-decision-log.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-run-metrics-contract.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-aggregate-summary-contract.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-scenario-clusters-contract.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-sensitivity-contract.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-frontend-ux-contract.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-schema-and-artifact-contracts.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-api-contracts.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-runtime-and-seeding-spec.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-step2-smoke-baseline.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-backend-workstreams.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-backend-task-register.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-frontend-workstreams.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-frontend-task-register.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-integration-dependency-map.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-integration-task-register.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-delivery-governance.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-test-and-release-plan.md`

Detailed task execution rule:

- the `*-workstreams.md` documents define phase structure and summary dependencies
- the `*-task-register.md` documents are the implementation-handoff source of truth for task-level purpose, inputs, outputs, acceptance criteria, QA evidence, and subtask completion conditions
- the status audit and readiness dashboard are the live repo-grounded source of truth for implementation status
- the execution log and gate ledger are the live source of truth for current evidence and gate posture
- the dedicated artifact/API contracts now include run metrics, aggregate summary, scenario clusters, and observational sensitivity

## 3. Product boundary for this program

This roadmap is optimized for the current MiroFishES product that exists in the repository today:

- uploaded source documents,
- ontology generation,
- Zep graph construction,
- entity filtering,
- OASIS agent profile generation,
- scalar simulation config generation,
- dual-platform social simulation,
- report generation,
- and report-agent interaction.

This program does **not** assume a greenfield rewrite into a general forecasting framework.

## 4. Program objective

Deliver an explicit, versioned, seeded, ensemble-based probabilistic simulation capability on top of the existing MiroFishES pipeline so the product can move from single-trajectory exploration toward decision-useful forecasting.

## 5. Workstream model

The program is organized into three execution lanes and one governance lane.

### Lane A: Backend foundation

Scope:

- schema,
- storage,
- seeded run resolution,
- ensemble orchestration,
- metrics extraction,
- aggregation,
- report backend integration.

### Lane B: Frontend and report surfaces

Scope:

- probabilistic controls in Step 2,
- ensemble monitoring in Step 3,
- uncertainty-aware report rendering in Step 4,
- interaction context in Step 5,
- history and comparison entry points.

### Lane C: Integration and delivery

Scope:

- API contracts,
- milestone sequencing,
- dependency management,
- test strategy,
- rollout gates,
- operational readiness.

### Lane D: Governance and risk

Scope:

- risk register,
- feature-flag policy,
- readiness gates,
- release criteria,
- and documentation hygiene.

## 6. Phase structure

### Phase 0: Program setup and contracts

Purpose:

- define the contracts that every later phase depends on.

Deliverables:

- artifact taxonomy,
- run and ensemble identifiers,
- seed policy,
- outcome metric catalog,
- API payload conventions,
- feature-flag plan,
- test-harness plan.

Exit criteria:

- backend and frontend teams agree on JSON artifact names and endpoint payload shapes,
- probabilistic mode is feature-flagged conceptually,
- phase-level dependency map is signed off.

Critical path:

- yes

Parallelization:

- documentation work is parallelizable across backend and frontend leads,
- final contract ratification is not.

### Phase 1: Backend probabilistic foundation

Purpose:

- make uncertainty, seeds, and run manifests first-class in the backend.

Deliverables:

- probabilistic schema layer,
- baseline config split,
- uncertainty spec persistence,
- resolved per-run config generation,
- prepared snapshot artifacts.

Exit criteria:

- one prepared simulation can emit baseline and uncertainty artifacts,
- identical seeds resolve identical concrete configs,
- legacy single-run mode still works.

Critical path:

- yes

Parallelization:

- parts of schema work and API-shape work can run in parallel,
- resolver work is blocked on schema finalization.

### Phase 2: Ensemble runtime and analytics

Purpose:

- convert the single-run runtime into a run-family capable execution model.

Deliverables:

- ensemble manager,
- run-scoped storage,
- seeded runtime execution,
- per-run metrics,
- aggregate summaries,
- scenario clusters,
- sensitivity outputs.

Exit criteria:

- many run members can execute under one prepared simulation,
- their outputs do not collide,
- aggregate artifacts can be produced from completed runs.

Critical path:

- yes

Parallelization:

- storage management and metrics extraction can overlap partially,
- runtime refactor is the main blocker.

### Phase 3: UI and report integration

Purpose:

- expose the new probabilistic capabilities to users in a controlled and explainable way.

Deliverables:

- Step 2 probabilistic controls,
- Step 3 ensemble monitor,
- Step 4 uncertainty-aware report cards,
- Step 5 ensemble-aware interaction context,
- history entry points for ensemble summaries.

Exit criteria:

- users can prepare, launch, monitor, and inspect probabilistic runs without using internal files,
- reports display empirical probabilities and scenario clusters with provenance labels.

Critical path:

- partially

Parallelization:

- Step 2 and Step 3 UI work can overlap,
- Step 4 is blocked on aggregate artifact format,
- Step 5 is blocked on report backend context format.

### Phase 4: Hardening and rollout readiness

Purpose:

- make the probabilistic path stable enough for broad internal use.

Deliverables:

- integration tests,
- performance budgets,
- failure-recovery behavior,
- observability,
- rollout gates,
- support documentation.

Exit criteria:

- the probabilistic path is operationally supportable,
- performance and failure modes are understood,
- team can safely enable the feature beyond internal development.

Critical path:

- yes before public or broad release

Parallelization:

- observability and UI polish can overlap,
- release gate signoff cannot.

### Phase 5: Advanced confidence and calibration

Purpose:

- add graph-confidence propagation, calibration artifacts, and later-stage world-state modeling.

Deliverables:

- graph-side confidence metadata,
- calibration artifact management,
- benchmark-ready recurring target definitions,
- optional targeted latent-state extensions.

Exit criteria:

- calibration is based on real benchmark targets and not just design intent,
- graph uncertainty is propagated end-to-end where needed.

Critical path:

- no for MVP

Parallelization:

- yes, mostly independent of MVP UI work once the data contracts are stable.

## 7. Milestones

| Milestone | Meaning | Depends on | Blocking? |
| --- | --- | --- | --- |
| M0 | Contract package ratified | None | Yes |
| M1 | Probabilistic artifacts persist in prepare flow | M0 | Yes |
| M2 | Seeded single-run resolution works | M1 | Yes |
| M3 | Multi-run ensemble execution works | M2 | Yes |
| M4 | Aggregate summaries and scenario clusters exist | M3 | Yes |
| M5 | Step 2 through Step 5 probabilistic UI path is usable | M4 | Yes |
| M6 | Operational hardening and rollout readiness complete | M5 | Yes |
| M7 | Calibration and graph-confidence work complete | M6 | No for MVP |

## 8. Critical path summary

The critical path is:

1. Phase 0 contract ratification
2. probabilistic schema and artifact persistence
3. uncertainty resolver
4. run-scoped ensemble orchestration
5. seeded runtime refactor
6. per-run outcome extraction
7. aggregate summary generation
8. report backend consumption of aggregate artifacts
9. Step 4 probabilistic report rendering
10. operational hardening

If any of those slip, the MVP slips.

## 8.1. Milestone crosswalk

| Roadmap milestone | Primary integration milestone | Primary handoff | Primary governing gate | Earliest release stage |
| --- | --- | --- | --- | --- |
| M0 | I0 | H0 | G1 | R0 |
| M1 | I1 | H1 | G1 | R0 |
| M2 | I2 draft | H2 draft | G2 | R0 |
| M3 | I2 final | H2 final | G2 | R0 |
| M4 | I3 | H3 | G3 | R1 |
| M5 | I4 | H4 | G4 | R1 |
| M6 | I5 | H5 | G5 | R2 to R3 |
| M7 | I7 | H6 | post-MVP policy gate | post-MVP only |

## 9. Parallel work summary

The following work can run in parallel once Phase 0 contracts are fixed:

- backend schema persistence and frontend Step 2 control scaffolding
- run storage planning and report artifact wireframe planning
- metrics extractor implementation and frontend Step 3 monitor scaffolding
- history/comparison design and Step 5 interaction-context design
- governance, risk, and rollout documentation

The following work must not run without settled contracts:

- Step 4 final report rendering against unstable aggregate artifacts
- Step 5 final chat context integration against unstable report context artifacts
- calibration implementation against unstable target definitions

## 10. Team handoff points

### Handoff 1: after M0

From:

- architecture and PM planning

To:

- backend schema and API work
- frontend control scaffolding

### Handoff 2: after M2

From:

- backend schema team

To:

- runtime and ensemble orchestration team
- frontend Step 2 and Step 3 teams

### Handoff 3: after M4

From:

- backend analytics team

To:

- report backend team
- Step 4 and Step 5 frontend teams

### Handoff 4: after M5

From:

- implementation teams

To:

- QA, rollout, and calibration planning

## 11. Recommended implementation order by lane

### Backend lane

Start first.

Reason:

- frontend and report work cannot stabilize until the artifact model is stable.

### Frontend lane

Start Step 2 and Step 3 scaffolding as soon as Phase 0 contracts exist.

Reason:

- those screens can consume early metadata before the full report pipeline is ready.

### Integration lane

Run continuously from Phase 0 onward.

Reason:

- dependency mistakes are the largest schedule risk in this program.

## 12. MVP definition

The MVP is complete when:

- one prepared simulation can generate probabilistic artifacts,
- an ensemble can launch many seeded runs under one simulation,
- per-run metrics and aggregate summaries exist,
- the report presents top outcomes, scenario clusters, and driver summaries with provenance,
- and the legacy single-run path still operates.

The MVP explicitly does **not** require:

- calibrated probabilities,
- graph-confidence enrichment,
- checkpoint branching,
- or world-state Bayesian submodels.

## 13. Immediate next actions

1. Maintain the H0 baseline, status audit, readiness dashboard, execution log, and gate ledger as the control system for this program.
2. Create the backend test harness and legacy regression baseline.
3. Implement backend Phase 1 probabilistic schema and prepare-artifact work while preserving legacy `simulation_config.json`.
4. Lock frontend state ownership and QA baselines before probabilistic UI wiring.
