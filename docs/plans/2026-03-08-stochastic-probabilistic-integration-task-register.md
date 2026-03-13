# Stochastic Probabilistic Simulation Integration Detailed Task Register

**Date:** 2026-03-10

## 1. Purpose

This document is the second-pass integration, governance, and release execution register for the stochastic probabilistic simulation program. It turns milestones, handoffs, gates, and rollout stages into implementation-ready coordination tasks with explicit owners, dependencies, evidence, and signoff rules.

Use this document together with:

- `docs/plans/2026-03-08-stochastic-probabilistic-status-audit.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-readiness-dashboard.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-h0-contract-baseline.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-h2-ensemble-storage-contract.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-gate-evidence-ledger.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-program-roadmap.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-integration-dependency-map.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-delivery-governance.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-test-and-release-plan.md`

## Current verified execution snapshot

Verified in this session:

| Task block | Current status | Verified note |
| --- | --- | --- |
| I0.1 | `implemented` | H0 baseline package now exists and is referenced by the control docs |
| I0.2 | `implemented` | the frontend UX/state-ownership contract now locks vocabulary and future ID ownership against repo truth |
| I1.1 | `partially implemented` | H1 prepare-path contract package now exists in `docs/plans/2026-03-08-stochastic-probabilistic-h1-prepare-path-contract.md` |
| I2.1 | `partially implemented` | H2 runtime contract draft now covers the live storage/API slice, the verified run-scoped runner seam, the explicit script CLI/runtime seam, ensemble-level launch/status orchestration, run-scoped detail/action/timeline inspection, rerun plus cleanup semantics, lifecycle plus lineage manifests, the Step 2 -> Step 3 probabilistic ensemble-browser handoff, the bounded `latest_probabilistic_runtime` history seam, the repo-owned fixture-backed smoke matrix, the repo-owned local-only operator path, the bounded local operator runbook plus README/.env enablement docs, one local-only non-fixture Step 1 -> Step 5 browser pass, six March 10 local-only operator/browser reruns, and the March 10 handoff mitigation for the first-click ensemble-create `400` |
| I2.2 | `blocked` | final H2 still lacks fuller operator handbook depth and broader repeatable non-fixture evidence even though the underlying retry/rerun/cleanup plus batch admission-control semantics now exist in code, a repo-owned local-only operator path now exists, a bounded local operator runbook package now exists, one local-only live Step 1 -> Step 5 pass now exists, six March 10 local-only operator/browser reruns now exist, and the bounded Step 3 history seam is now repo-real |
| I4.1 | `partially implemented` | the H4 report-context contract, persisted `probabilistic_report_context.json`, the first additive Step 4 consumer, and the bounded Step 5 report-scoped chat/history seam now exist, but run/cluster grounding and deeper Step 4 report-body work remain open |
| I6.1 | `implemented` | gate-evidence ledger exists and now records verified code/test evidence |
| I7.1 | `partially implemented` | rollout stages remain doc-backed, but backend/frontend flag discovery now exists for prepare and ensemble runtime/storage gating |

Immediate integration follow-on:

- durable H1 fixture/examples package
- H2 storage/runtime handoff maintenance as the probabilistic browser expands into fuller operator handbooks and broader repeatable non-fixture evidence
- broader history, compare, reload, and re-entry guidance on top of the now-live bounded Step 3 plus Step 4/Step 5 fixture-backed smoke baseline
- release-ops package after runtime work lands

## 2. Control-system crosswalk

The program uses five control layers. This table makes their relationship explicit.

| Roadmap milestone | Integration milestone | Required handoff package | Governing gate | Earliest release stage unlocked |
| --- | --- | --- | --- | --- |
| M0 Contract package ratified | I0 Contract lock point | H0 Contract baseline | G1 Schema and artifact readiness | R0 developer-only |
| M1 Prepare flow emits probabilistic artifacts | I1 Prepare-path readiness | H1 Prepare-path contract | G1 Schema and artifact readiness | R0 developer-only |
| M2 Seeded single-run resolution works | I2 Runtime contract draft-ready | H2 Runtime contract draft | G2 Runtime readiness | R0 developer-only |
| M3 Multi-run ensemble execution works | I2 Runtime contract finalized | H2 Runtime contract final | G2 Runtime readiness | R0 developer-only |
| M4 Aggregate summaries and scenario clusters exist | I3 Analytics contract readiness | H3 Aggregate analytics contract | G3 Analytics readiness | R1 internal pilot |
| M5 Step 2 through Step 5 probabilistic UI path is usable | I4 Report and interaction readiness | H4 Report and interaction contract | G4 UX readiness | R1 internal pilot |
| M6 Operational hardening and rollout readiness complete | I5 Release-ops readiness | H5 Release-ops handoff | G5 Rollout readiness | R2 controlled beta / R3 broader rollout |
| M7 Calibration and graph-confidence work complete | I7 Post-MVP expansion readiness | H6 Calibration and confidence handoff | post-MVP gate by policy | later-stage rollout |

## 3. Normalized task template

Every integration task in this register uses the same fields:

- Lane: Integration, Governance, or Release/Ops
- Control mapping: milestone, handoff, gate, and release-stage alignment
- Purpose: one-sentence delivery outcome
- Depends on / Unblocks: task linkage
- Handoff in / out: required artifacts and packages
- Definition of ready / done: start and finish criteria
- Acceptance criteria: consumer-verifiable behavior
- Evidence required: documents, fixtures, tests, screenshots, metrics, or signoff
- Approver: single accountable approver plus required reviewers
- Rollback / degrade plan: what happens if this item is not ready

## 4. Phase I0: Contract lock and baseline planning

### Task I0.1: Produce H0 contract baseline package

Lane:
- Integration

Control mapping:
- M0, I0, H0, G1, R0

Purpose:
- Establish one baseline package for identifiers, artifacts, payloads, and state vocabulary.

Depends on:
- none

Unblocks:
- B0.1, B0.2, F0.1, F0.2

Handoff in / out:
- In: existing architecture and implementation docs
- Out: H0 contract baseline package linking schema, API, runtime, and UX vocabulary docs

Definition of ready:
- core design intent exists

Definition of done:
- all Phase 0 contract docs are linked, versioned, and reviewed as one package

Acceptance criteria:
- backend and frontend can point to one baseline package instead of scattered docs

Evidence required:
- linked baseline package index
- approval notes

Approver:
- technical product lead

Rollback / degrade plan:
- if not complete, implementation remains Phase 0 only

Subtasks:
- I0.1.a Gather the Phase 0 contract docs into one package index. Depends on: none. Done when: one doc or section links all baseline contracts.
- I0.1.b Record version and review owners. Depends on: I0.1.a. Done when: every contract has an accountable owner.
- I0.1.c Record unresolved contract questions. Depends on: I0.1.a. Done when: open issues are visible before implementation.

### Task I0.2: Lock cross-team terminology and state ownership

Lane:
- Integration

Control mapping:
- M0, I0, H0, G1, R0

Purpose:
- Prevent drift between backend identity semantics and frontend state ownership.

Depends on:
- I0.1

Unblocks:
- F0.2, B2.2, B2.5, F4.1

Handoff in / out:
- In: H0 contract baseline
- Out: state-ownership note for `mode`, `simulation_id`, `ensemble_id`, `run_id`, `cluster_id`

Definition of ready:
- baseline identifier semantics exist

Definition of done:
- ownership and lifecycle of key IDs are documented

Acceptance criteria:
- backend and frontend agree where each ID is created, stored, and displayed

Evidence required:
- state ownership matrix

Approver:
- backend lead and frontend lead jointly

Rollback / degrade plan:
- if unresolved, Step 3 to Step 5 implementation stays blocked

Subtasks:
- I0.2.a Define backend creation points for each ID. Depends on: I0.1. Done when: ID producers are explicit.
- I0.2.b Define frontend ownership and persistence rules. Depends on: I0.1. Done when: route and component state rules are explicit.
- I0.2.c Define history and interaction reuse rules. Depends on: I0.2.b. Done when: state handoff into Step 4 and Step 5 is explicit.

## 5. Phase I1: Prepare-path contract handoff

### Task I1.1: Produce H1 prepare-path contract package

Lane:
- Integration

Control mapping:
- M1, I1, H1, G1, R0

Purpose:
- Turn prepare-path backend output into a frontend-consumable contract package.

Depends on:
- B1.2, B1.3

Unblocks:
- F1.0, F1.1, F1.2, F1.3

Handoff in / out:
- In: prepare artifacts and API behavior
- Out: H1 package with request/response examples, error cases, versions, and fixture paths

Definition of ready:
- backend prepare artifacts and API changes exist

Definition of done:
- frontend can build Step 2 probabilistic flow against a stable package

Acceptance criteria:
- H1 includes payload examples, artifact summary shape, null/error semantics, and compatibility notes

Evidence required:
- JSON fixtures
- endpoint examples
- review signoff

Approver:
- frontend lead

Rollback / degrade plan:
- Step 2 stays behind scaffolding only; no final wiring

Subtasks:
- I1.1.a Capture example prepare request and response payloads. Depends on: B1.3. Done when: fixtures exist by path.
- I1.1.b Capture artifact summary examples. Depends on: B1.2. Done when: baseline, uncertainty, and snapshot summary examples are documented.
- I1.1.c Capture error and compatibility behavior. Depends on: B1.3. Done when: legacy, invalid, and flagged-off behavior are documented.

## 6. Phase I2: Runtime and ensemble handoff

### Task I2.1: Produce H2 runtime contract draft

Lane:
- Integration

Control mapping:
- M2, I2, H2 draft, G2, R0

Purpose:
- Expose seeded run-resolution and lifecycle semantics early enough for Step 3 scaffolding.

Depends on:
- B2.1, B2.2

Unblocks:
- F2.1 scaffolding

Handoff in / out:
- In: resolver and ensemble manager behavior
- Out: H2 draft covering run state machine, seed semantics, and directory layout

Definition of ready:
- resolver and ensemble storage work exist

Definition of done:
- draft package is sufficient for Step 3 scaffolding, but marked pre-final where runtime lifecycle details remain open

Acceptance criteria:
- H2 draft names lifecycle states, seed behavior, and run manifest fields

Evidence required:
- draft package
- open issues list

Approver:
- backend lead

Rollback / degrade plan:
- frontend may scaffold visuals only, not final lifecycle behavior

Subtasks:
- I2.1.a Capture seed and run-manifest semantics. Depends on: B2.1. Done when: draft documents run seed lineage.
- I2.1.b Capture ensemble/run directory semantics. Depends on: B2.2. Done when: frontend and QA know artifact lookup rules.
- I2.1.c Record open runtime lifecycle questions. Depends on: I2.1.a. Done when: stop/retry/rerun gaps are explicit.

Implementation note:

- partially implemented on 2026-03-10 through `docs/plans/2026-03-08-stochastic-probabilistic-h2-runtime-contract-draft.md`, `backend/app/api/simulation.py`, the backend runtime/API slice, the repo-owned Playwright smoke harness, the bounded local operator runbook plus README/.env enablement docs, one local-only non-fixture Step 1 -> Step 5 browser pass, six March 10 local-only browser/operator reruns, and the March 10 Step 2/prepare-status plus bounded history-reentry hardening: the draft now records retry via `/start`, child-run reruns, ensemble-scoped cleanup, lifecycle plus lineage manifests, real batch admission-control semantics, the bounded `latest_probabilistic_runtime` history seam, bounded Step 3 through Step 5 frontend adoption, the fixture-backed smoke baseline, the root cause and mitigation for the transient first-click Step 2 -> Step 3 ensemble-create `400`, a live Step 1 -> Step 5 operator pass, repeated first-click-success reruns, and the zero-context local enablement inputs needed to turn the bounded operator path on, but it still defers fuller operator runbooks, repeatable non-fixture evidence, and broader Step 3 replay/history/compare semantics

### Task I2.2: Produce H2 runtime contract final

Lane:
- Integration

Control mapping:
- M3, I2, H2 final, G2, R0

Purpose:
- Finalize the runtime contract once run-scoped execution and APIs are stable.

Depends on:
- B2.3, B2.4, B2.5

Unblocks:
- F2.1 finalization, F2.2, B6.3

Handoff in / out:
- In: runtime refactor, script refactor, API endpoints
- Out: final H2 package with lifecycle, retry, rerun, cleanup, error, and pagination semantics

Definition of ready:
- runtime APIs and run-scoped behavior exist

Definition of done:
- consumers can rely on stable status, run detail, and lifecycle behaviors

Acceptance criteria:
- H2 final includes create, launch, status, run list, run detail, stop, retry, rerun, and cleanup semantics or explicitly defers them

Evidence required:
- endpoint examples
- lifecycle test results
- signoff note

Approver:
- frontend lead and backend lead jointly

Rollback / degrade plan:
- keep Step 3 on the current runtime shell and block further Step 4/Step 5 probabilistic adoption

Subtasks:
- I2.2.a Capture runtime lifecycle state machine. Depends on: B2.3. Done when: state transitions are documented.
- I2.2.b Capture script and seed semantics. Depends on: B2.4. Done when: runtime reproducibility contract is explicit.
- I2.2.c Capture status, list, detail, `actions`, and `timeline` endpoint behavior. Depends on: B2.5. Done when: payloads and error semantics are fixture-backed.
- I2.2.d Capture retry/rerun/cleanup semantics. Depends on: B2.3, B2.5. Done when: operator actions are documented or explicitly deferred.

Implementation note:

- still blocked after the 2026-03-10 operator-hardening continuation: the underlying retry/rerun/cleanup semantics, real batch admission-control semantics, the bounded `latest_probabilistic_runtime` history seam, fixture-backed Step 2 through Step 5 smoke evidence, the repo-owned local-only `npm run verify:operator:local` path, the bounded local operator runbook plus README/.env enablement docs, one local-only live Step 1 -> Step 5 browser pass, six March 10 local-only browser/operator reruns, and root-cause plus code mitigation for the transient first-click Step 2 -> Step 3 ensemble-create `400` now exist, but final H2 still needs fuller operator handbook depth, broader repeatable non-fixture runtime/browser evidence, and broader Step 3 replay/history/compare guidance before it can be promoted from draft to final

## 7. Phase I3: Analytics handoff

### Task I3.1: Produce H3 aggregate analytics package

Lane:
- Integration

Control mapping:
- M4, I3, H3, G3, R1

Purpose:
- Provide one stable analytics package for Step 3 provisional widgets, Step 4 report cards, and report backend consumption.

Depends on:
- B3.1, B3.2, B3.3, B3.4

Unblocks:
- F2.3, F3.1, F3.2, F3.3, B4.1

Handoff in / out:
- In: metrics, summary, cluster, and sensitivity artifacts
- Out: H3 package with schemas, fixture files, provenance rules, and quality-warning behavior

Definition of ready:
- analytics artifacts exist

Definition of done:
- frontend and report consumers can build against stable analytics fixtures

Acceptance criteria:
- H3 includes aggregate summary, scenario cluster, and sensitivity examples with field-by-field provenance notes

Evidence required:
- fixture artifacts
- artifact schema versions
- consumer signoff

Approver:
- report/backend lead

Rollback / degrade plan:
- Step 4 advanced cards stay blocked; Step 3 shows status-only monitoring

Subtasks:
- I3.1.a Capture aggregate summary example and schema. Depends on: B3.2. Done when: summary fixture is reviewed.
- I3.1.b Capture scenario cluster example and schema. Depends on: B3.3. Done when: cluster fixture is reviewed.
- I3.1.c Capture sensitivity example and schema. Depends on: B3.4. Done when: sensitivity fixture is reviewed.
- I3.1.d Record thin-evidence and degraded-run rules. Depends on: B3.1, B3.2. Done when: consumers know how to handle weak or partial analytics.

## 8. Phase I4: Report and interaction handoff

### Task I4.1: Produce H4 probabilistic report and interaction package

Lane:
- Integration

Control mapping:
- M5, I4, H4, G4, R1

Purpose:
- Finalize the contract for probabilistic report cards and ensemble-aware interaction.

Depends on:
- B4.1, B4.2, B4.3

Unblocks:
- F3.1 finalization, F4.1

Handoff in / out:
- In: report context, ensemble-aware report generation, chat grounding
- Out: H4 package with context artifact examples, scope rules, and unsupported-claim behavior

Definition of ready:
- report backend can build probabilistic context and responses

Definition of done:
- Step 4 and Step 5 can finalize against stable context and grounding rules

Acceptance criteria:
- H4 includes run-vs-cluster-vs-ensemble grounding rules, provenance requirements, and null/degraded behavior

Evidence required:
- context fixtures
- reviewed answer examples

Approver:
- product lead

Rollback / degrade plan:
- Step 5 remains ensemble-blind or report-only if H4 is not stable

Subtasks:
- I4.1.a Capture probabilistic report-context fixture. Depends on: B4.1. Done when: fixture path is documented.
- I4.1.b Capture report output rules. Depends on: B4.2. Done when: empirical vs calibrated labeling and representative-run citation rules are documented.
- I4.1.c Capture chat grounding rules. Depends on: B4.3. Done when: scope behavior and unsupported-claim handling are documented.

Implementation note:

- partially implemented on 2026-03-09 through `docs/plans/2026-03-08-stochastic-probabilistic-report-context-contract.md`, `backend/app/api/report.py`, `backend/app/services/report_agent.py`, `frontend/src/components/Step5Interaction.vue`, `frontend/src/views/InteractionView.vue`, `frontend/src/components/HistoryDatabase.vue`, `backend/tests/unit/test_probabilistic_report_api.py`, and `tests/smoke/probabilistic-runtime.spec.mjs`; the H4 package now covers exact-report Step 5 chat grounding plus saved-report Step 5 re-entry, but it still lacks run-vs-cluster-vs-ensemble interaction rules, reviewed answer examples, and interview/survey grounding

## 9. Phase I5: Release-ops handoff

### Task I5.1: Produce H5 release-ops package

Lane:
- Release/Ops

Control mapping:
- M6, I5, H5, G5, R2

Purpose:
- Convert engineering completion into a supportable, operable release package.

Depends on:
- B6.1, B6.2, B6.3, B6.4, F5.1, F5.2

Unblocks:
- R2 controlled beta

Handoff in / out:
- In: backend and frontend release evidence
- Out: H5 package with feature flags, dashboards, alerts, runbooks, rollback steps, and support ownership

Definition of ready:
- backend and frontend have release-evidence bundles

Definition of done:
- support and release reviewers can operate and roll back the feature safely

Acceptance criteria:
- H5 names feature flags, owner, monitoring path, stuck-run procedure, rollback procedure, and support escalation path

Evidence required:
- runbook
- alert/dashboard list
- rollback checklist
- signoff note

Approver:
- engineering lead

Rollback / degrade plan:
- remain at R1 internal pilot

Subtasks:
- I5.1.a Gather flag and rollout-state documentation. Depends on: B6.1, F4.3. Done when: all feature flags and defaults are documented.
- I5.1.b Gather observability and incident docs. Depends on: B6.2, B6.3. Done when: dashboard, alert, and stuck-run procedures are documented.
- I5.1.c Gather frontend and support guidance. Depends on: F5.2. Done when: user-visible limits and support scripts are documented.
- I5.1.d Record rollback procedure and owners. Depends on: I5.1.a, I5.1.b. Done when: one rollback path exists for each probabilistic surface.

## 10. Phase I6: Gate evidence and signoff management

### Task I6.1: Maintain gate-evidence ledger

Lane:
- Governance

Control mapping:
- G1 through G5 across all milestones

Purpose:
- Keep one auditable place where gate evidence and signoff status are recorded.

Depends on:
- I0.1 onward

Unblocks:
- all gate reviews

Handoff in / out:
- In: evidence from backend, frontend, and ops
- Out: gate ledger with current status and evidence links

Definition of ready:
- at least one gate is approaching review

Definition of done:
- ledger exists and is updated at every gate review

Acceptance criteria:
- every gate has evidence links, approver, date, and unresolved issues

Evidence required:
- gate ledger itself

Approver:
- technical product lead

Rollback / degrade plan:
- no release-stage advancement without ledger completeness

Subtasks:
- I6.1.a Create ledger structure. Depends on: I0.1. Done when: one ledger format exists.
- I6.1.b Add evidence-link rules. Depends on: I6.1.a. Done when: contributors know what to attach for review.
- I6.1.c Record signoff and exceptions. Depends on: I6.1.a. Done when: approvals and exceptions are durable and visible.

### Task I6.2: Run weekly dependency and escalation review

Lane:
- Governance

Control mapping:
- supports all milestones and release stages

Purpose:
- Prevent backend/frontend drift and surface blocked handoffs before they delay delivery.

Depends on:
- I0.1

Unblocks:
- all downstream coordination

Handoff in / out:
- In: task status from backend, frontend, and release lanes
- Out: dependency review notes with actions and escalations

Definition of ready:
- implementation work has started

Definition of done:
- recurring review exists for the duration of the program

Acceptance criteria:
- blocked items, owners, and next actions are recorded weekly

Evidence required:
- meeting notes or action logs

Approver:
- engineering lead

Rollback / degrade plan:
- if skipped, release-stage advancement requires ad hoc review before signoff

Subtasks:
- I6.2.a Define review agenda. Depends on: I0.1. Done when: handoffs, blockers, and gate readiness are standard agenda items.
- I6.2.b Define escalation path. Depends on: I6.2.a. Done when: blocked contract or handoff issues have named escalation owners.
- I6.2.c Record weekly action items. Depends on: I6.2.a. Done when: reviews produce concrete next steps.

## 11. Phase I7: Rollout sequencing and post-MVP expansion

### Task I7.1: Manage staged rollout from R0 to R3

Lane:
- Release/Ops

Control mapping:
- R0, R1, R2, R3

Purpose:
- Make release progression explicit instead of subjective.

Depends on:
- I5.1
- I6.1

Unblocks:
- broader rollout

Handoff in / out:
- In: gate evidence and release-ops package
- Out: release decision record per stage

Definition of ready:
- current stage evidence is complete

Definition of done:
- each stage progression or hold decision is recorded with rationale

Acceptance criteria:
- every stage transition names owner, date, evidence, and rollback trigger

Evidence required:
- release decision record

Approver:
- engineering lead and product lead jointly

Rollback / degrade plan:
- hold at current stage or revert to prior stage

Subtasks:
- I7.1.a Define measurable stage criteria. Depends on: I5.1. Done when: R0-R3 criteria are explicit and testable.
- I7.1.b Record go/no-go decision format. Depends on: I6.1. Done when: each stage has a consistent decision record template.
- I7.1.c Record rollback triggers. Depends on: I5.1. Done when: each stage has named rollback conditions.

### Task I7.2: Prepare post-MVP handoff for calibration and graph confidence

Lane:
- Integration

Control mapping:
- M7, I7, H6, post-MVP

Purpose:
- Keep post-MVP calibration and graph-confidence work from contaminating MVP delivery while preserving a clean handoff.

Depends on:
- B5.1, B5.2, B5.3

Unblocks:
- later-stage expansion

Handoff in / out:
- In: graph confidence and calibration readiness notes
- Out: H6 package for post-MVP planning

Definition of ready:
- MVP has exited critical rollout work

Definition of done:
- post-MVP owners inherit a stable package rather than scattered notes

Acceptance criteria:
- H6 states what is implemented, what is only designed, and what evidence is still missing

Evidence required:
- post-MVP handoff package

Approver:
- technical product lead

Rollback / degrade plan:
- keep calibration and graph-confidence features disabled

Subtasks:
- I7.2.a Capture graph-confidence status. Depends on: B5.1, B5.2. Done when: the team knows what graph-side uncertainty work is implemented.
- I7.2.b Capture calibration readiness. Depends on: B5.3. Done when: eligible targets, missing data, and gating rules are documented.
- I7.2.c Record explicit non-MVP boundary. Depends on: I7.2.a, I7.2.b. Done when: rollout reviewers can see that these items stay out of MVP.
