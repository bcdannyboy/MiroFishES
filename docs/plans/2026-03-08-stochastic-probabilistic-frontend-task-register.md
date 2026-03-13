# Stochastic Probabilistic Simulation Frontend Detailed Task Register

**Date:** 2026-03-10

## 1. Purpose

This document is the second-pass frontend execution register for the stochastic probabilistic simulation program. It expands each UI and UX task into implementation-ready work with explicit user goal, entry point, state model, API dependency, edge cases, acceptance criteria, QA, and sequencing.

Use this document together with:

- `docs/plans/2026-03-08-stochastic-probabilistic-status-audit.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-readiness-dashboard.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-frontend-workstreams.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-api-contracts.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-program-roadmap.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-delivery-governance.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-test-and-release-plan.md`

Live-status rule:

- use this register for intended UI execution detail
- use the status audit and readiness dashboard for current repo-grounded status

## Current verified execution snapshot

Verified in this session:

| Task block | Current status | Verified note |
| --- | --- | --- |
| F0.1 | `implemented` | the frontend UX contract now locks glossary, provenance, and forbidden-language rules in addition to Step 2 copy discipline |
| F0.2 | `implemented` | the frontend UX contract now locks state ownership for `mode`, `ensemble_id`, `run_id`, and `cluster_id` while Step 2 owns the live prepare state |
| F1.0 | `partially implemented` | Step 2 performs capability discovery, legacy fallback, explicit probabilistic prepare, and March 10 stale-state clearing before Step 3 handoff |
| F1.1 | `partially implemented` | mode toggle, prepared-run-count input, uncertainty profile selector, and outcome metric selection are live |
| F1.2 | `partially implemented` | compact prepared-artifact summary panel is live |
| F1.3 | `partially implemented` | disabled-state copy, CTA gating, error rendering, and active-prepare stale-ready-state suppression are live |
| F2.1 | `partially implemented` | Step 3 now has a dual-mode header plus a probabilistic ensemble browser with status counts, selected-run launch/retry, stop, cleanup, child-rerun actions, operator guidance, and the legacy single-run path preserved |
| F2.2 | `partially implemented` | Step 3 now supports stored-run browsing, selected-run status/seed/raw-action drilldown, recent timeline rows, deterministic selected-run recovery, and child-rerun re-selection inside the probabilistic runtime shell |
| F3.1 | `partially implemented` | Step 4 now renders an additive observed aggregate-summary card from saved report metadata or direct artifact fallback while preserving the legacy report stream |
| F3.2 | `partially implemented` | the same Step 4 report-context addendum now renders an observed scenario-cluster card with cluster count, lead-family mass, and prototype-run reference |
| F3.3 | `partially implemented` | Step 4 now renders an observed sensitivity card with top-driver wording and warning chips, but no tail-risk view exists yet |
| F3.4 | `partially implemented` | probabilistic Step 4 cards now coexist with the legacy report/log stream without breaking the current `report_id` route |
| F4.1 | `partially implemented` | Step 5 report-agent chat now sends `report_id`, reloads the exact saved report, and can reuse saved `probabilistic_context`, but interviews/surveys remain legacy-scoped and no run/cluster selector exists yet |
| F4.2 | `partially implemented` | history can now reopen a bounded Step 3 stored-run shell when durable probabilistic runtime scope exists, and it still reopens the exact saved Step 4 and Step 5 report through deterministic ordering, stable selectors, and an explicit expand/collapse control that keeps collapsed stacks overview-only, but no ensemble-history rows or compare route exist |
| F4.3 | `partially implemented` | Step 2 consumes the backend flag/capability surface, Step 3 now has explicit probabilistic runtime handoff, Step 4 now consumes saved report metadata plus capability state for the first probabilistic addendum, and Step 5 now renders an explicit banner that distinguishes report-agent chat from legacy interviews/surveys |
| F5.1 | `partially implemented` | `npm run verify` now includes 42 frontend route/runtime unit tests plus the frontend build, `npm run verify:smoke` now covers seven deterministic fixture-backed browser checks across Step 2, Step 3, Step 4, Step 5, Step 5 history re-entry, and the bounded Step 3 history re-entry seam, `npm run verify:operator:local` now provides a repo-owned local-only mutating operator path, one local-only non-fixture browser pass reached a live Step 5 interaction view, and six March 10 local-only browser/operator reruns re-proved first-click Step 2 -> Step 3 plus Step 3 operator recovery success |

Immediate frontend follow-on:

- broader browser/device coverage and repeatable non-fixture evidence beyond the current repo-owned fixture-backed Step 2 through Step 5 smoke matrix plus the repo-owned local-only operator path, one full live Step 1 -> Step 5 pass, and six March 10 reruns
- Step 4 report-context depth beyond the initial observed summary/cluster/sensitivity cards
- Step 3 compare/reload/history/operator-state hardening on top of the stored-run browser, bounded history re-entry, and selected-run recovery
- broader Step 5 probabilistic surfaces beyond the current report-agent lane

## 2. Task block template

Each frontend task answers the same questions:

- User goal: what the user is trying to accomplish.
- Entry point: where the user enters the flow.
- Feature flag / route: which surface or route is affected and how off-states work.
- State model: what UI state must exist and how it changes.
- API dependency or decision artifact: what backend contract or design artifact it depends on.
- Edge cases / off-states: what must happen when data is missing, thin, disabled, or still loading.
- Acceptance criteria: concrete done-when behavior.
- QA: minimum verification evidence.
- Sequencing: predecessor tasks, blocked tasks, and safe parallel work.

## 3. Phase F0: UX contract and information architecture

### Task F0.1: Define probabilistic UX vocabulary

User goal:
- Let users understand new probabilistic concepts without needing internal terminology.

Entry point:
- shared copy system across Step 2, Step 3, Step 4, Step 5, and history.

Feature flag / route:
- no direct flag; this is a prerequisite copy contract.

State model:
- terminology dictionary and provenance label rules used by all later states.

API dependency or decision artifact:
- depends on Phase 0 concept and contract ratification.

Edge cases / off-states:
- calibration-off mode must not introduce calibrated-language affordances.

Acceptance criteria:
- each user-visible term has one approved definition
- provenance labels for empirical vs calibrated values are defined
- warning copy exists for thin evidence and unsupported claims

QA:
- copy review by product and report/backend leads
- terminology checklist attached to Step 2-5 designs

Sequencing:
- Depends on: Phase 0 contract ratification
- Blocks: F0.2, F1.1, F2.1, F3.1, F4.1
- Parallelizable: yes

Subtasks:
- F0.1.a Define visible terms. Depends on: none. Output: term glossary. Done when: ensemble, run, scenario family, tail risk, empirical probability, calibrated probability, and representative run have stable definitions.
- F0.1.b Define provenance copy rules. Depends on: F0.1.a. Output: copy rule set. Done when: empirical vs calibrated labeling rules are explicit.
- F0.1.c Define thin-evidence and unsupported-claim wording. Depends on: F0.1.a. Output: warning copy. Done when: report and chat warnings share one wording policy.

### Task F0.2: Define new UI surfaces and placement

User goal:
- Make the probabilistic flow discoverable without fragmenting the current Step 2 to Step 5 experience.

Entry point:
- `SimulationView`, `SimulationRunView`, `ReportView`, `InteractionView`, and history.

Feature flag / route:
- determines where probabilistic controls and views appear when feature flags are on.

State model:
- screen-level information architecture, including where `mode`, `ensemble_id`, `run_id`, and `cluster_id` live.

API dependency or decision artifact:
- depends on F0.1 and Phase 0 backend contracts.

Edge cases / off-states:
- legacy mode must preserve current layout without empty probabilistic shells.

Acceptance criteria:
- Step 2, Step 3, Step 4, Step 5, and history placement decisions are recorded
- state ownership of `mode`, `ensemble_id`, `run_id`, and `cluster_id` is explicit

QA:
- route and component ownership review
- design review notes captured

Sequencing:
- Depends on: F0.1
- Blocks: F1.0, F1.1, F2.1, F3.1, F4.2
- Parallelizable: yes

Subtasks:
- F0.2.a Decide Step 2 control placement. Depends on: F0.1. Output: Step 2 IA note. Done when: probabilistic pre-prepare controls have a stable home.
- F0.2.b Decide Step 3 monitor placement. Depends on: F0.1. Output: Step 3 IA note. Done when: ensemble status and run drilldown placement are fixed.
- F0.2.c Decide Step 4 report card placement. Depends on: F0.1. Output: Step 4 IA note. Done when: probabilistic cards coexist with streaming report sections cleanly.
- F0.2.d Decide history and compare placement. Depends on: F0.1. Output: route decision. Done when: history-only vs compare-route scope is fixed.

## 4. Phase F1: Step 2 probabilistic setup and prepare experience

### Task F1.0: Add Step 2 probabilistic prepare orchestration

User goal:
- Let a user choose probabilistic mode, configure it, and intentionally trigger prepare without losing the existing legacy flow.

Entry point:
- `frontend/src/components/Step2EnvSetup.vue`

Feature flag / route:
- gated by `probabilistic_prepare_enabled`

State model:
- draft state, validating state, preparing state, prepared state, and error state
- separate legacy auto-prepare path from probabilistic explicit-prepare path

API dependency or decision artifact:
- backend B1.3 prepare payload and response contract

Edge cases / off-states:
- flag off: current legacy auto-prepare path remains
- invalid draft: prepare CTA disabled or server error rendered clearly
- prepare error: user can revise and retry
- active probabilistic re-prepare must not reopen the Step 3 handoff from stale config polling or stale prepared data

Acceptance criteria:
- probabilistic mode uses an explicit prepare CTA
- legacy mode still behaves like today unless design intentionally changes it
- prepared state stores artifact summary and selected probabilistic options
- a new probabilistic prepare clears stale prepared-state handoff before the next Step 3 launch attempt becomes available

QA:
- manual smoke checklist for legacy and probabilistic prepare
- state-transition checklist for draft, loading, success, and error
- stale-response and active-task race checks

Sequencing:
- Depends on: F0.2, backend B1.3
- Blocks: F1.1, F1.2, F1.3, ensemble creation launch flow
- Parallelizable: no

Subtasks:
- F1.0.a Add explicit probabilistic prepare CTA behavior. Depends on: F0.2. Output: Step 2 trigger model. Done when: probabilistic mode no longer relies on ambiguous auto-prepare behavior.
- F1.0.b Define draft-vs-prepared state ownership. Depends on: F1.0.a. Output: component state model. Done when: selected options and prepared artifact summary do not overwrite each other.
- F1.0.c Wire `/prepare` trigger semantics. Depends on: backend B1.3. Output: API call flow. Done when: prepare request includes probabilistic inputs and consumes the new response.
- F1.0.d Preserve legacy fallback. Depends on: F1.0.c. Output: dual-mode Step 2 behavior. Done when: legacy path still works when probabilistic mode is off.

### Task F1.1: Add probabilistic mode controls to Step 2

User goal:
- Specify the key setup choices for a probabilistic run family.

Entry point:
- probabilistic panel in `Step2EnvSetup.vue`

Feature flag / route:
- gated by `probabilistic_prepare_enabled`

State model:
- draft controls for mode, run count, uncertainty profile, and outcome metrics

API dependency or decision artifact:
- B1.3 request contract

Edge cases / off-states:
- unsupported uncertainty profile
- run count outside allowed budget
- outcome metrics absent or invalid

Acceptance criteria:
- controls have defined defaults and reset rules
- control values serialize into the prepare request correctly
- unsupported selections are blocked or explained

QA:
- state and serialization checks
- manual budget-cap validation cases

Sequencing:
- Depends on: F1.0
- Blocks: F1.2, F1.3
- Parallelizable: yes once F1.0 exists

Subtasks:
- F1.1.a Add probabilistic mode toggle. Depends on: F1.0. Output: mode control. Done when: the user can switch between legacy and probabilistic setup paths.
- F1.1.b Add run-count control. Depends on: F1.0. Output: run-count input. Done when: control honors backend min/max rules and resets cleanly.
- F1.1.c Add uncertainty profile selector. Depends on: F1.0. Output: profile selector. Done when: supported profiles map to backend request values.
- F1.1.d Add outcome metric selection UI. Depends on: F1.0. Output: metric selector. Done when: selected metrics persist across validation and prepare.

### Task F1.2: Add prepared artifact preview to Step 2

User goal:
- Understand what the prepare step produced before launching an ensemble.

Entry point:
- Step 2 prepared-state panel

Feature flag / route:
- gated by `probabilistic_prepare_enabled`

State model:
- reads the prepared artifact summary from Step 2 prepared state

API dependency or decision artifact:
- backend B1.2 artifact output and B1.3 response summary

Edge cases / off-states:
- prepare succeeded but some artifacts are degraded or version-mismatched

Acceptance criteria:
- baseline config summary, uncertainty summary, deterministic-vs-uncertain split, and versions are visible
- preview updates only when the latest prepare request succeeds

QA:
- preview freshness checks
- stale-response protection checks

Sequencing:
- Depends on: F1.0, F1.1, backend B1.2
- Blocks: none
- Parallelizable: yes with F1.3

Subtasks:
- F1.2.a Show baseline config summary. Depends on: F1.0. Output: baseline card. Done when: core prepared simulation state is legible.
- F1.2.b Show uncertainty summary cards. Depends on: backend B1.2. Output: uncertainty cards. Done when: the user can see what is being sampled.
- F1.2.c Show deterministic vs uncertain fields. Depends on: F1.2.b. Output: split view. Done when: users can tell what stays fixed and what varies per run.
- F1.2.d Show artifact timestamps and versions. Depends on: F1.2.a. Output: provenance metadata. Done when: version and freshness info is visible.

### Task F1.3: Add Step 2 validation and guardrails

User goal:
- Prevent invalid or misleading probabilistic prepare requests.

Entry point:
- Step 2 inline validation and error surfaces

Feature flag / route:
- gated by `probabilistic_prepare_enabled`

State model:
- draft validation state, server-validation error state, and unsupported-combination state

API dependency or decision artifact:
- B1.3 request validation contract

Edge cases / off-states:
- empty metric set
- excessive run count
- incompatible option combinations
- backend prepare failure
- stale ready-state promotion while a probabilistic prepare task is still active

Acceptance criteria:
- invalid drafts cannot be launched silently
- server-side validation errors are rendered clearly and non-destructively
- probabilistic controls degrade gracefully when unsupported
- Step 3 handoff remains disabled until current probabilistic prepare state is genuinely ready

QA:
- validation matrix covering client and server errors

Sequencing:
- Depends on: F1.0, F1.1
- Blocks: none
- Parallelizable: yes

Subtasks:
- F1.3.a Validate missing outcome metrics. Depends on: F1.1. Output: client validation. Done when: empty metric sets are blocked or warned as designed.
- F1.3.b Validate missing or invalid run count. Depends on: F1.1. Output: count validation. Done when: invalid counts cannot pass silently.
- F1.3.c Disable unsupported combinations gracefully. Depends on: F1.1. Output: off-state behavior. Done when: impossible or non-MVP combinations are visibly blocked.
- F1.3.d Surface backend preparation errors. Depends on: F1.0.c. Output: server error UI. Done when: failed prepares preserve draft state and show actionable feedback.

## 5. Phase F2: Step 3 ensemble monitoring

### Task F2.1: Add ensemble progress header and status summary

User goal:
- Monitor overall ensemble progress without losing the current run-monitoring affordance.

Entry point:
- `Step3Simulation.vue` and `SimulationRunView.vue`

Feature flag / route:
- gated by `ensemble_runtime_enabled`

State model:
- ensemble status state plus legacy single-run status state
- polling or refresh state is explicit

API dependency or decision artifact:
- backend B2.5 ensemble status contract

Edge cases / off-states:
- ensemble not started
- partial failure
- refresh during in-flight status update
- large ensemble summary truncation

Acceptance criteria:
- users can see total, running, completed, and failed runs
- legacy single-run view still renders correctly
- loading and stale states are understandable

QA:
- polling/refresh smoke test
- partial-failure display checklist

Sequencing:
- Depends on: backend B2.5
- Blocks: F2.2, F2.3
- Parallelizable: yes

Subtasks:
- F2.1.a Show run counts by status. Depends on: backend B2.5. Output: status header. Done when: total, running, completed, and failed runs display consistently.
- F2.1.b Show current ensemble stage. Depends on: backend B2.5. Output: stage label. Done when: users can tell whether the ensemble is preparing, running, aggregating, or complete.
- F2.1.c Preserve legacy single-run display. Depends on: F2.1.a. Output: dual-mode UI. Done when: existing Step 3 monitoring still works for legacy runs.

### Task F2.2: Add run-level drilldown in Step 3

User goal:
- Inspect one run in detail while still understanding it as part of a larger ensemble.

Entry point:
- run list and selected-run panel in Step 3

Feature flag / route:
- gated by `ensemble_runtime_enabled`

State model:
- selected `run_id`, selected run detail loading state, and no-run-selected fallback

API dependency or decision artifact:
- backend B2.5 run list and run detail contracts

Edge cases / off-states:
- failed run
- deleted or unavailable run
- large run list

Acceptance criteria:
- run selection is explicit and stable across refreshes
- selected run shows seed, status, and timeline context
- no selection or missing selection has a safe fallback state

QA:
- run selection persistence checks
- failed-run drilldown smoke test

Sequencing:
- Depends on: F2.1, backend B2.5
- Blocks: none
- Parallelizable: yes

Subtasks:
- F2.2.a Add run list panel. Depends on: F2.1. Output: list UI. Done when: users can browse run members without entering a new route.
- F2.2.b Add selected-run timeline view. Depends on: F2.2.a. Output: drilldown panel. Done when: one run can be inspected in Step 3.
- F2.2.c Add per-run status and seed summary. Depends on: backend B2.5. Output: metadata UI. Done when: each run visibly exposes its identity and reproducibility metadata.

### Task F2.3: Add early aggregation widgets in Step 3

User goal:
- See emerging outcome patterns before the full report is generated.

Entry point:
- Step 3 ensemble monitor sidebar or summary region

Feature flag / route:
- gated by `probabilistic_report_enabled` or a dedicated ensemble-monitor flag

State model:
- provisional aggregation state distinct from final report state

API dependency or decision artifact:
- backend B3.2, B3.3, and B3.4 aggregate contracts

Edge cases / off-states:
- not enough completed runs
- provisional clusters unstable
- thin evidence, degraded-run warnings, or observational-only sensitivity warnings

Acceptance criteria:
- provisional outcomes, cluster emergence, and spread indicators are shown only when data quality is sufficient
- provisional state is clearly labeled as non-final

QA:
- small-sample smoke checks
- warning-state checklist
- frontend artifact-normalization unit checks

Sequencing:
- Depends on: F2.1, backend B3.2, backend B3.3
- Blocks: Step 3 probabilistic completeness
- Parallelizable: yes

Subtasks:
- F2.3.a Show top provisional outcomes. Depends on: backend B3.2. Output: provisional outcomes widget. Done when: users can see emerging outcome distribution safely.
- F2.3.b Show early scenario-cluster emergence. Depends on: backend B3.3. Output: provisional cluster widget. Done when: early scenario families appear with uncertainty labeling.
- F2.3.c Show convergence or spread indicators. Depends on: backend B3.2. Output: spread widget. Done when: users can tell whether runs are clustering or diverging.

Implementation note:

- partially implemented on 2026-03-09 through `frontend/src/components/Step3Simulation.vue`, `frontend/src/api/simulation.js`, `frontend/src/utils/probabilisticRuntime.js`, and `frontend/tests/unit/probabilisticRuntime.test.mjs`; the live Step 3 slice now renders read-only observed ensemble analytics cards for summary, clusters, and sensitivity with explicit warning chips, but richer trend/spread drilldown and broader browsing remain open

## 6. Phase F3: Step 4 probabilistic report experience

### Task F3.1: Add probabilistic report summary cards

User goal:
- Understand top outcomes and their empirical support immediately when opening the report.

Entry point:
- `Step4Report.vue` and `ReportView.vue`

Feature flag / route:
- gated by `probabilistic_report_enabled`

State model:
- coexists with streaming report section state
- consumes report summary context when present

API dependency or decision artifact:
- backend B4.2 report summary contract

Edge cases / off-states:
- report exists but probabilistic artifacts do not
- thin evidence
- calibration disabled

Acceptance criteria:
- top outcomes, probability bands, run counts, and provenance labels render from artifacts
- legacy reports still render without broken cards

QA:
- fixture-based rendering checks
- empirical-only and no-probabilistic-context states

Sequencing:
- Depends on: backend B4.2, F0.2
- Blocks: F3.2, F3.3, F3.4
- Parallelizable: yes

Subtasks:
- F3.1.a Add top outcomes card. Depends on: backend B4.2. Output: summary card. Done when: report shows the leading outcome distribution.
- F3.1.b Add probability band and run-count display. Depends on: F3.1.a. Output: support metadata. Done when: report makes sample support visible.
- F3.1.c Add provenance labels for empirical vs calibrated values. Depends on: F0.1, backend B4.2. Output: provenance UI. Done when: users can distinguish empirical values from calibrated ones or see that calibration is off.

### Task F3.2: Add scenario-cluster rendering

User goal:
- Explore the major scenario families that emerged across the ensemble.

Entry point:
- Step 4 scenario-family section

Feature flag / route:
- gated by `probabilistic_report_enabled`

State model:
- list of scenario clusters plus selected prototype run or expanded card state

API dependency or decision artifact:
- backend B3.3 and B4.1 cluster/report-context contracts

Edge cases / off-states:
- no stable clusters
- low-confidence clustering
- missing prototype run

Acceptance criteria:
- scenario family cards show mass, prototype reference, drivers, and early indicators
- unstable clustering has a clear fallback state

QA:
- cluster-card fixture checks
- missing-prototype fallback check

Sequencing:
- Depends on: F3.1, backend B3.3, backend B4.1
- Blocks: none
- Parallelizable: yes

Subtasks:
- F3.2.a Show scenario family cards. Depends on: F3.1. Output: family cards. Done when: users can scan distinct plausible futures.
- F3.2.b Show prototype run reference. Depends on: backend B4.1. Output: representative-run UI. Done when: each cluster can point to a prototype run or say none is available.
- F3.2.c Show key drivers and early indicators. Depends on: backend B4.1. Output: supporting metadata. Done when: each cluster includes the fields needed for decision support.

### Task F3.3: Add sensitivity and tail-risk views

User goal:
- See which variables matter most and how tail-risk futures differ from likely futures.

Entry point:
- Step 4 advanced analysis section

Feature flag / route:
- gated by `probabilistic_report_enabled`

State model:
- sensitivity view state and tail-risk panel state

API dependency or decision artifact:
- backend B3.4 and B4.2 report-context contracts

Edge cases / off-states:
- no report-context sensitivity consumer yet
- too few analyzable runs
- calibration off

Acceptance criteria:
- sensitivity ranking and most-likely-vs-tail-risk views render only when supported by artifacts
- thin-evidence warnings are explicit

QA:
- sensitivity fixture checks
- thin-evidence warning checks

Sequencing:
- Depends on: F3.1, backend B3.4
- Blocks: none
- Parallelizable: yes

Subtasks:
- F3.3.a Render sensitivity ranking. Depends on: backend B3.4. Output: ranked driver view. Done when: users can see the major drivers of distribution change.
- F3.3.b Render most likely vs tail-risk futures. Depends on: F3.1. Output: comparison view. Done when: likely and adverse scenario families are contrasted clearly.
- F3.3.c Render thin-evidence warnings. Depends on: F0.1, backend B4.2. Output: warning UI. Done when: weak support is clearly visible.

### Task F3.4: Preserve current report-generation experience

User goal:
- Keep current report generation usable while probabilistic cards are added incrementally.

Entry point:
- existing report stream and report-log rendering path

Feature flag / route:
- always relevant

State model:
- streaming section state remains independent from probabilistic summary state

API dependency or decision artifact:
- B4.2 report generation behavior

Edge cases / off-states:
- no probabilistic artifacts
- legacy report only
- streaming still in progress

Acceptance criteria:
- probabilistic cards do not break report logs or section streaming
- legacy reports remain readable and complete

QA:
- regression checklist against current Step 4 behavior

Sequencing:
- Depends on: F3.1
- Blocks: none
- Parallelizable: yes

Subtasks:
- F3.4.a Keep section-by-section streaming intact. Depends on: F3.1. Output: preserved stream behavior. Done when: users still see report sections stream as before.
- F3.4.b Prevent probabilistic cards from breaking legacy logs. Depends on: F3.1. Output: compatibility logic. Done when: old reports render safely.
- F3.4.c Keep single-run artifact fallback. Depends on: F3.1. Output: fallback UI. Done when: report remains usable with only single-run evidence.

## 7. Phase F4: Step 5 interaction and history surfaces

### Task F4.1: Add ensemble-aware interaction context

User goal:
- Ask questions about the ensemble, one scenario family, or one representative run and know which scope the answer refers to.

Entry point:
- `Step5Interaction.vue` and `InteractionView.vue`

Feature flag / route:
- gated by `probabilistic_interaction_enabled`

State model:
- selected conversation scope: ensemble, cluster, or run
- sticky scope state plus per-message scope display

API dependency or decision artifact:
- backend B4.3 chat/report-context contract

Edge cases / off-states:
- no representative run
- cluster unavailable
- probabilistic interaction disabled

Acceptance criteria:
- UI states the current answer scope
- user can switch scope where supported
- missing scopes degrade cleanly

QA:
- scope-switching checklist
- no-representative-run fallback check

Sequencing:
- Depends on: backend B4.3
- Blocks: none
- Parallelizable: yes

Subtasks:
- F4.1.a Display ensemble-vs-cluster-vs-run scope. Depends on: backend B4.3. Output: scope label UI. Done when: every answer shows its grounding scope.
- F4.1.b Add selected cluster or prototype run context. Depends on: F4.1.a. Output: context selector. Done when: users can inspect cluster or run grounded responses where available.
- F4.1.c Surface probability provenance in chat answers. Depends on: F0.1, backend B4.3. Output: provenance cues. Done when: chat visibly distinguishes evidence-backed probabilities from unsupported claims.

Implementation note:

- partially implemented on 2026-03-09 through `frontend/src/components/Step5Interaction.vue`, `frontend/src/views/InteractionView.vue`, `frontend/src/utils/probabilisticRuntime.js`, `backend/app/api/report.py`, `backend/app/services/report_agent.py`, `frontend/tests/unit/probabilisticRuntime.test.mjs`, and `backend/tests/unit/test_probabilistic_report_api.py`; the current H4 slice now grounds report-agent chat on the exact saved `report_id` plus saved `probabilistic_context`, but interviews/surveys still use the legacy interaction path and no run-vs-cluster-vs-ensemble selector or answer-level provenance UI exists yet

### Task F4.2: Add history and comparison entry points

User goal:
- Revisit probabilistic runs later and optionally compare ensembles without forcing MVP scope creep.

Entry point:
- `HistoryDatabase.vue` and router entry points

Feature flag / route:
- history enabled in MVP
- compare route only if explicitly approved beyond MVP

State model:
- history list state, selected record state, and optional compare-selection state

API dependency or decision artifact:
- existing history API plus the bounded `latest_probabilistic_runtime` summary contract and route decision from F0.2

Edge cases / off-states:
- mixed legacy and probabilistic history entries
- compare route disabled

Acceptance criteria:
- history can reopen the bounded Step 3 stored-run shell when durable probabilistic runtime scope exists
- users can re-enter Step 4 or Step 5 from history safely
- ensemble-history rows and compare remain explicitly out of MVP unless promoted later

QA:
- mixed-history smoke test
- route navigation checks

Sequencing:
- Depends on: F0.2, backend ensemble summary APIs
- Blocks: optional compare workflow
- Parallelizable: yes

Subtasks:
- F4.2.a Add ensemble records to history. Depends on: backend ensemble summary APIs. Output: history row type. Done when: probabilistic runs appear in history.
- F4.2.b Add bounded history replay entry points. Depends on: existing history records with durable probabilistic scope. Output: navigation path. Done when: users can reopen bounded Step 3 plus Step 4/Step 5 from history without implying full ensemble-history support.
- F4.2.c Keep compare route optional. Depends on: F0.2. Output: scope control. Done when: compare stays explicitly out of MVP unless approved later.

Implementation note:

- partially implemented on 2026-03-10 through `backend/app/api/simulation.py`, `backend/tests/unit/test_probabilistic_report_api.py`, `frontend/src/components/HistoryDatabase.vue`, `frontend/src/views/ReportView.vue`, `frontend/src/views/InteractionView.vue`, `frontend/src/utils/probabilisticRuntime.js`, `frontend/tests/unit/probabilisticRuntime.test.mjs`, and `tests/smoke/probabilistic-runtime.spec.mjs`; the current history model is still simulation/report centric, but users can now reopen the newest bounded Step 3 stored-run shell through `latest_probabilistic_runtime` when durable `ensemble_id` plus `run_id` evidence exists, reopen the newest saved Step 4 and Step 5 report through deterministic ordering and stable replay selectors, and use an explicit expand/collapse history control that keeps only the newest card interactive until the stack is expanded, while ensemble-history rows and compare remain deferred

### Task F4.3: Add frontend feature-flag and off-state handling

User goal:
- Never see broken or misleading probabilistic UI when the backend or rollout state does not support it.

Entry point:
- Step 2 to Step 5 and history surfaces

Feature flag / route:
- `probabilistic_prepare_enabled`
- `probabilistic_ensemble_storage_enabled`
- `probabilistic_report_enabled`
- `probabilistic_interaction_enabled`
- `calibrated_probability_enabled`

State model:
- hidden, disabled, and degraded surface states

API dependency or decision artifact:
- governance flag policy

Edge cases / off-states:
- backend endpoints available but feature flag off
- calibration flag off but empirical artifacts present

Acceptance criteria:
- every probabilistic surface has a defined off-state
- calibrated labels never render when calibration is disabled
- route entry into disabled surfaces is guarded

QA:
- flag matrix checklist

Sequencing:
- Depends on: governance flag policy
- Blocks: F5.2
- Parallelizable: yes

Subtasks:
- F4.3.a Wire per-surface feature flags. Depends on: governance flag policy. Output: flag-aware components. Done when: Step 2-5 surfaces respond correctly to flag state.
- F4.3.b Define hidden vs disabled behavior. Depends on: F4.3.a. Output: off-state rules. Done when: each surface has one explicit off-state strategy.
- F4.3.c Add route guards and fallbacks. Depends on: F4.3.a. Output: routing protection. Done when: disabled probabilistic routes redirect or degrade safely.
- F4.3.d Enforce calibration-off fallback. Depends on: F0.1. Output: calibration guard. Done when: UI only shows empirical labeling when calibration is off.

## 8. Phase F5: Frontend QA and release hardening

### Task F5.1: Create frontend probabilistic QA fixtures and smoke matrix

User goal:
- Give implementers and reviewers repeatable ways to verify the new probabilistic surfaces.

Entry point:
- frontend QA workflow

Feature flag / route:
- covers all probabilistic surfaces and their off-states

State model:
- fixture-backed states for draft, preparing, running, partial failure, complete, thin evidence, and legacy fallback

API dependency or decision artifact:
- stable API fixtures from backend and integration handoffs

Edge cases / off-states:
- mixed legacy/probabilistic history
- no probabilistic artifacts
- partial failure

Acceptance criteria:
- smoke matrix covers Step 2, Step 3, Step 4, Step 5, and history
- fixture states exist for off-state, degraded-state, and happy-path coverage

QA:
- this task is QA infrastructure itself

Sequencing:
- Depends on: F1.0, F2.1, F3.1, F4.1, F4.3
- Blocks: F5.2, wider rollout
- Parallelizable: partially

Subtasks:
- F5.1.a Define fixture state catalog. Depends on: F1.0, F2.1, F3.1. Output: fixture matrix. Done when: all core UI states are named and mapped to fixtures.
- F5.1.b Build smoke checklist. Depends on: F5.1.a. Output: manual QA checklist. Done when: reviewers can execute one repeatable pass across probabilistic surfaces.
- F5.1.c Define browser and device matrix. Depends on: F5.1.a. Output: compatibility matrix. Done when: minimum supported browsers and responsive checks are explicit.
- F5.1.d Define evidence capture rules. Depends on: F5.1.b. Output: QA evidence rules. Done when: screenshots, logs, and notes required for signoff are defined.

Implementation note:

- partially implemented on 2026-03-10 through `backend/app/services/probabilistic_smoke_fixture.py`, `backend/scripts/create_probabilistic_smoke_fixture.py`, `playwright.config.mjs`, `playwright.live.config.mjs`, `tests/smoke/probabilistic-runtime.spec.mjs`, `tests/live/probabilistic-operator-local.spec.mjs`, the Step 2 through Step 5 data-testid/copy hardening, the Step 3 operator-surface hardening, and the March 10 Step 2 handoff regressions: the repo now has a reusable/browser-scripted fixture-backed matrix covering the Step 2 prepared state, the Step 3 missing-handoff off-state, the Step 3 stored-run shell, the bounded Step 3 history re-entry seam, the Step 4 observed addendum, the Step 5 report-context banner, and exact-selector saved-report Step 5 history re-entry; it also has a separate repo-owned local-only operator path that captures Step 2 handoff, stop, retry, cleanup, and child rerun behavior plus browser/network output for `sim_7a6661c37719`; repo-root and smoke backend launches now prefer the backend virtualenv interpreter when present, frontend probabilistic runtime coverage has grown to `42` tests, and the first-click Step 2 -> Step 3 handoff plus Step 3 recovery actions now have repeatable local-only proof with the latest capture at `ensemble 0008` / `run 0001` / child `run 0009`, but broader browser/device coverage, ensemble-history coverage, repeatability, and release-grade non-fixture evidence are still missing

### Task F5.2: Produce frontend release-evidence bundle

User goal:
- Turn frontend completion into a signoff-ready package for rollout gates.

Entry point:
- release and readiness review

Feature flag / route:
- all probabilistic frontend flags

State model:
- none; this is a delivery artifact

API dependency or decision artifact:
- depends on completed UI work and QA evidence

Edge cases / off-states:
- unresolved non-MVP compare scope
- calibration still off

Acceptance criteria:
- frontend signoff package exists for FG1-FG4 and governance G4-G5
- known limitations and off-state behavior are documented

QA:
- collected from F5.1

Sequencing:
- Depends on: F4.3, F5.1
- Blocks: broader rollout
- Parallelizable: no

Subtasks:
- F5.2.a Assemble step-by-step QA evidence. Depends on: F5.1. Output: signoff packet. Done when: Step 2-5 evidence is collected.
- F5.2.b Document known UI limits and off-states. Depends on: F4.3. Output: limitations note. Done when: rollout reviewers can see what remains disabled or non-MVP.
- F5.2.c Obtain frontend signoff. Depends on: F5.2.a, F5.2.b. Output: approval record. Done when: accountable reviewers approve rollout progression.
