# Stochastic Probabilistic Simulation Frontend Workstreams

**Date:** 2026-03-08

## 1. Purpose

This document decomposes frontend delivery into phases, tasks, and subtasks with explicit dependencies and parallelization guidance.

Detailed execution reference:

- for user goal, entry point, state model, edge cases, acceptance criteria, QA, and detailed sequencing, use `docs/plans/2026-03-08-stochastic-probabilistic-frontend-task-register.md`

## 2. Frontend scope

Primary files in scope:

- `frontend/src/components/Step2EnvSetup.vue`
- `frontend/src/components/Step3Simulation.vue`
- `frontend/src/components/Step4Report.vue`
- `frontend/src/components/Step5Interaction.vue`
- `frontend/src/views/SimulationView.vue`
- `frontend/src/views/SimulationRunView.vue`
- `frontend/src/views/ReportView.vue`
- `frontend/src/views/InteractionView.vue`
- `frontend/src/api/simulation.js`
- `frontend/src/api/report.js`
- `frontend/src/router/index.js`
- `frontend/src/components/HistoryDatabase.vue`

## 3. Current implementation constraints

These constraints materially affect sequencing and should be treated as first-order planning inputs rather than incidental details.

### C1: Step 2 is auto-prepare oriented

Current behavior:

- Step 2 automatically drives `/api/simulation/prepare` and expects one scalar config plus generated profiles.

Implication:

- probabilistic mode needs a pre-prepare control surface before the current flow can remain coherent.

### C2: Step 3 is single-run by design

Current behavior:

- Step 3 assumes one `simulation_id`, one status object, and one global action feed.

Implication:

- ensemble monitoring requires a dual-mode model rather than a simple additive widget.

### C3: Step 4 rebuilds from report logs

Current behavior:

- Step 4 reconstructs the report from agent logs and streaming sections rather than consuming a structured probabilistic report context.

Implication:

- advanced probabilistic cards should not be finalized until the backend exposes report-ready aggregate context.

### C4: Step 5 has no run semantics

Current behavior:

- Step 5 chats and interviews against `simulation_id` only.

Implication:

- representative-run or cluster-aware interaction is a real product and API decision, not just a UI ticket.

### C5: Frontend QA is thin

Current behavior:

- the frontend package does not currently have a strong test harness.

Implication:

- manual smoke baselines and regression checklists should be treated as mandatory early deliverables.

## 4. Phase F0: UX contract and information architecture

### Task F0.1: Define probabilistic UX vocabulary

**Depends on:** Phase 0 backend/integration contract ratification

**Parallelizable:** yes

**Blocks:** F1.1, F2.1, F3.1

**Deliverables:**

- approved labels for ensemble, run, scenario family, tail risk, empirical probability, calibrated probability, and representative run.

**Subtasks:**

- F0.1.a Define terminology users will actually see.
- F0.1.b Define provenance copy rules.
- F0.1.c Define how uncertainty warnings are phrased.

### Task F0.2: Define new UI surfaces and placement

**Depends on:** F0.1

**Parallelizable:** yes

**Blocks:** F1.1, F2.1, F4.1

**Subtasks:**

- F0.2.a Decide which controls live in Step 2.
- F0.2.b Decide which ensemble progress elements live in Step 3.
- F0.2.c Decide which probabilistic report cards live in Step 4.
- F0.2.d Decide whether comparison gets its own route or stays in existing views.

## 5. Phase F1: Step 2 probabilistic setup experience

### Task F1.0: Add Step 2 probabilistic prepare orchestration

**Depends on:** F0.2, backend B1.3 API contract

**Parallelizable:** no

**Blocks:** F1.1, F1.2, F1.3, user-visible probabilistic prepare flow

**Subtasks:**

- F1.0.a Add explicit probabilistic prepare CTA behavior.
- F1.0.b Define draft-vs-prepared state ownership.
- F1.0.c Wire `/prepare` trigger semantics.
- F1.0.d Preserve legacy auto-prepare fallback.

### Task F1.1: Add probabilistic mode controls to Step 2

**Depends on:** F1.0

**Parallelizable:** yes

**Blocks:** user-visible entry into ensemble mode

**Files:**

- modify `frontend/src/components/Step2EnvSetup.vue`
- modify `frontend/src/api/simulation.js`

**Subtasks:**

- F1.1.a Add probabilistic mode toggle.
- F1.1.b Add run-count control.
- F1.1.c Add uncertainty profile selector.
- F1.1.d Add outcome metric selection UI.

### Task F1.2: Add prepared artifact preview to Step 2

**Depends on:** F1.1, backend B1.2 artifact output

**Parallelizable:** yes

**Blocks:** none

**Subtasks:**

- F1.2.a Show baseline config summary.
- F1.2.b Show uncertainty summary cards.
- F1.2.c Show which fields are deterministic vs uncertain.
- F1.2.d Show artifact timestamps and versions.

### Task F1.3: Add Step 2 validation and guardrails

**Depends on:** F1.1

**Parallelizable:** yes

**Blocks:** none

**Subtasks:**

- F1.3.a Validate missing outcome metrics.
- F1.3.b Validate missing run count or bad run count.
- F1.3.c Disable unsupported combinations gracefully.
- F1.3.d Surface backend preparation errors clearly.

## 6. Phase F2: Step 3 ensemble monitoring

### Task F2.1: Add ensemble progress header and status summary

**Depends on:** backend B2.5

**Parallelizable:** yes

**Blocks:** F2.2, F2.3

**Files:**

- modify `frontend/src/components/Step3Simulation.vue`
- modify `frontend/src/views/SimulationRunView.vue`
- modify `frontend/src/api/simulation.js`

**Subtasks:**

- F2.1.a Show total runs, running runs, completed runs, failed runs.
- F2.1.b Show current ensemble stage.
- F2.1.c Preserve legacy single-run display path.

### Task F2.2: Add run-level drilldown in Step 3

**Depends on:** F2.1, backend run detail endpoint

**Parallelizable:** yes

**Blocks:** none

**Subtasks:**

- F2.2.a Add run list panel.
- F2.2.b Add selected-run timeline view.
- F2.2.c Add per-run status and seed summary.

### Task F2.3: Add early aggregation widgets in Step 3

**Depends on:** backend B3.2, B3.3, and B3.4

**Parallelizable:** yes

**Blocks:** Step 3 probabilistic completeness

**Subtasks:**

- F2.3.a Show top provisional outcomes.
- F2.3.b Show early scenario-cluster emergence.
- F2.3.c Show convergence or spread indicators where available.

**Implementation note:**

- partially implemented on 2026-03-09 with read-only Step 3 cards for aggregate summary, scenario clusters, and observational sensitivity plus frontend unit coverage for artifact normalization

## 7. Phase F3: Step 4 probabilistic report experience

### Task F3.1: Add probabilistic report summary cards

**Depends on:** backend B4.2 and F0.2

**Parallelizable:** yes

**Blocks:** F3.2, F3.3

**Files:**

- modify `frontend/src/components/Step4Report.vue`
- modify `frontend/src/views/ReportView.vue`
- modify `frontend/src/api/report.js`

**Subtasks:**

- F3.1.a Add top outcomes card.
- F3.1.b Add probability band and run-count display.
- F3.1.c Add provenance labels for empirical vs calibrated values.

### Task F3.2: Add scenario-cluster rendering

**Depends on:** F3.1, backend B3.3 and B4.1

**Parallelizable:** yes

**Blocks:** none

**Subtasks:**

- F3.2.a Show scenario family cards.
- F3.2.b Show prototype run reference.
- F3.2.c Show key drivers and early indicators per cluster.

### Task F3.3: Add sensitivity and tail-risk views

**Depends on:** F3.1, backend B3.4

**Parallelizable:** yes

**Blocks:** none

**Subtasks:**

- F3.3.a Render sensitivity ranking.
- F3.3.b Render most likely vs tail-risk futures.
- F3.3.c Render evidence-quality or thin-evidence warnings.

### Task F3.4: Preserve current report-generation experience

**Depends on:** F3.1

**Parallelizable:** yes

**Blocks:** none

**Subtasks:**

- F3.4.a Keep section-by-section report streaming behavior intact.
- F3.4.b Ensure probabilistic cards do not break legacy report logs.
- F3.4.c Keep the report usable when only single-run artifacts exist.

## 8. Phase F4: Step 5 interaction and history surfaces

### Task F4.1: Add ensemble-aware interaction context

**Depends on:** backend B4.3

**Parallelizable:** yes

**Blocks:** none

**Files:**

- modify `frontend/src/components/Step5Interaction.vue`
- modify `frontend/src/views/InteractionView.vue`
- modify `frontend/src/api/report.js`

**Subtasks:**

- F4.1.a Display whether the chat answer is ensemble-level, cluster-level, or run-level.
- F4.1.b Add selected cluster or prototype run context where available.
- F4.1.c Surface probability provenance in chat answers.

### Task F4.2: Add history and comparison entry points

**Depends on:** backend ensemble summary APIs

**Parallelizable:** yes

**Blocks:** optional compare workflow

**Files:**

- modify `frontend/src/components/HistoryDatabase.vue`
- modify `frontend/src/router/index.js`

**Subtasks:**

- F4.2.a Add ensemble records to history.
- F4.2.b Add entry point into probabilistic report view.
- F4.2.c Add compare route only if cross-ensemble analysis becomes large enough.

### Task F4.3: Add frontend feature-flag and off-state handling

**Depends on:** governance flag policy

**Parallelizable:** yes

**Blocks:** final rollout

**Subtasks:**

- F4.3.a Wire per-surface feature flags.
- F4.3.b Define hidden-vs-disabled off-state behavior.
- F4.3.c Add route guards and fallbacks.
- F4.3.d Enforce calibration-off fallback behavior.

## 9. Phase F5: Frontend QA and release hardening

### Task F5.1: Create frontend probabilistic QA fixtures and smoke matrix

**Depends on:** F1.0, F2.1, F3.1, F4.1, F4.3

**Parallelizable:** partially

**Blocks:** rollout readiness

**Subtasks:**

- F5.1.a Define fixture-state catalog.
- F5.1.b Build manual smoke checklist.
- F5.1.c Define browser and device matrix.
- F5.1.d Define evidence capture rules.

### Task F5.2: Produce frontend release-evidence bundle

**Depends on:** F4.3, F5.1

**Parallelizable:** no

**Blocks:** broader rollout

**Subtasks:**

- F5.2.a Assemble Step 2 through Step 5 QA evidence.
- F5.2.b Document known UI limits and off-states.
- F5.2.c Obtain frontend rollout signoff.

## 10. Frontend critical path

The frontend critical path is:

- F0.1
- F0.2
- F1.0
- F1.1
- F2.1
- F3.1
- F4.1
- F4.3
- F5.1
- F5.2

The rest is important, but those items determine whether users can access, understand, trust, and safely ship the probabilistic flow.

## 11. Frontend work that can be parallelized safely

- F1.2 and F1.3 can run in parallel once F1.1 scaffold exists.
- F2.2 and F2.3 can run in parallel once ensemble status endpoints stabilize.
- F3.2 and F3.3 can run in parallel after F3.1 cards and aggregate artifact formats exist.
- F4.1 and F4.2 can run in parallel after report context and history API contracts are stable.
- F4.3 can overlap with late Step 4 and Step 5 work once feature-flag policy is ratified.
- F5.1 can start fixture definition before all Step 4 and Step 5 polish is done.

## 12. Frontend readiness gates

### Gate FG1

Before Step 2 work is merged:

- probabilistic mode toggle and controls degrade gracefully in legacy mode.

### Gate FG2

Before Step 3 work is merged:

- ensemble status payloads are stable,
- run drilldown does not regress single-run monitoring.

### Gate FG3

Before Step 4 work is merged:

- aggregate summary and scenario cluster payload shapes are stable,
- probability provenance rules are locked.

### Gate FG4

Before Step 5 work is merged:

- chat context artifacts clearly distinguish ensemble vs run vs cluster grounding.

### Gate FG5

Before broader rollout:

- feature-flag off-states work across Step 2 through Step 5
- frontend smoke matrix is complete
- rollout evidence bundle exists
