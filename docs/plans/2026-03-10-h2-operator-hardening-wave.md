# 2026-03-10 H2 Operator Hardening Wave

**Date:** 2026-03-10
**Scope:** H2 runtime/operator hardening, evidence-boundary cleanup, and PM truth repair
**Status:** materially advanced on 2026-03-10; later the same day this became one historical input to the broader hybrid truthful-local hardening wave, so use the March 8 control packet plus `docs/plans/2026-03-10-hybrid-h2-truthful-local-hardening-wave.md` for current truth

## 1. Why this wave outranks the alternatives

The next highest-leverage unblocked lane is still H2, not deeper Step 4 or Step 5 work.

Repo-grounded reasons:

- `I2.2` remains blocked because the repo has real retry, rerun, cleanup, lineage, and lifecycle semantics in backend code, but the operator package is still incomplete.
- `B6.3` is only partially closed because the backend semantics exist, yet the operator-facing runbook layer and higher-level evidence package still lag the code.
- `I5.1` and broader H5 work cannot be packaged honestly while runtime evidence is still split between unit/contract tests, deterministic fixtures, and two local-only live passes.
- Step 4 and Step 5 remain intentionally bounded. Expanding them before Step 3 operator semantics are fully documented and evidenced would widen the rollout surface while a critical runtime lane is still under-explained.

## 2. Entry truth from the repository on 2026-03-10

### 2.1 Backend/runtime truth that already exists

The backend already implements the following H2 seams:

- full-sidecar probabilistic readiness gating for ensemble creation under `backend/app/api/simulation.py`
- simulation-scoped ensemble create/list/detail plus run list/detail APIs
- same-run `start`/`stop` routes for stored ensemble members
- child-run `rerun` creation through `POST /api/simulation/<simulation_id>/ensembles/<ensemble_id>/runs/<run_id>/rerun`
- targeted ensemble cleanup through `POST /api/simulation/<simulation_id>/ensembles/<ensemble_id>/cleanup`
- active-run cleanup refusal with `409` plus explicit `active_run_ids`
- persisted `run_manifest.json` lifecycle counters and lineage fields under `backend/app/models/probabilistic.py`
- persisted cleanup/reset semantics that return a cleaned run to `prepared` without deleting `resolved_config.json`
- status aggregation that may trust stored terminal statuses when runner state is absent, but does not treat storage-only `running` as proof of an active process

### 2.2 Frontend/operator truth at wave entry

The current Step 3 browser is real, but the operator surface is not yet aligned with backend semantics.

Repo-grounded entry mismatch:

- `frontend/src/components/Step3Simulation.vue` currently exposes selected-run `start` and `stop` controls, but not explicit Step 3 `rerun` or `cleanup` controls.
- The same file currently labels terminal same-run restart as `Rerun selected run`, even though the backend `start` path with `force=true` restarts the same `run_id`; child-run creation is a separate backend `rerun` endpoint.
- Existing Step 3 copy references rerun/cleanup availability more broadly than the current UI actually exposes.

This mismatch makes H2 operator-usable in backend/API scope, but not yet operator-clear in the primary frontend runtime surface.

### 2.3 Verification truth at wave entry

Current evidence is real but stratified:

- unit/contract evidence: backend tests cover lifecycle counters, rerun lineage, cleanup behavior, active-run cleanup refusal, and runtime-scope manifest updates
- fixture-backed browser evidence: `npm run verify:smoke` now covers six deterministic Playwright checks across the bounded Step 2 through Step 5 path
- local-only non-fixture evidence: one March 9 live Step 1 through Step 5 pass and one March 10 live Step 2 through Step 3 rerun succeeded on the same simulation family
- release-grade evidence: still absent

This wave exists partly to stop those evidence classes from being described interchangeably.

## 3. Explicit wave objectives

This wave should close the next set of H2 truth gaps without widening the product surface prematurely.

### 3.1 H2 operator semantics

- make Step 3 distinguish same-run retry from child-run rerun
- expose cleanup as an explicit recovery action
- preserve the active-run cleanup refusal as a hard safety rule
- add operator guidance for stop, retry, rerun, cleanup, and stuck-run handling

### 3.2 Evidence and truth repair

- separate unit/contract, fixture-backed browser, local-only non-fixture, and release-grade claims everywhere they are referenced
- refresh the stale H2 storage contract so it matches live manifest lifecycle/lineage behavior
- stop overclaiming Step 3 operator support where the frontend surface is still narrower than the backend

### 3.3 H5 groundwork

- define a repeatable local-only non-fixture capture path for one existing simulation family
- record exactly what still blocks promotion from local-only proof to release-grade proof

## 4. In-scope deliverables for the code-and-doc wave

The intended implementation wave should produce all of the following if no blocker intervenes:

1. Step 3 operator-surface hardening in `frontend/src/components/Step3Simulation.vue` and related helpers:
   - same-run retry wording for the existing `start` path
   - explicit child-run rerun control
   - explicit cleanup control
   - honest off-state and helper text when cleanup is refused because a run is active
2. Higher-level backend operator-flow coverage on top of existing unit seams:
   - stop -> cleanup -> retry of the same `run_id`
   - rerun lineage to a child `run_id`
   - cleanup refusal for active runs at an app/API path
3. A repeatable local-only operator evidence recipe that captures:
   - `simulation_id`
   - `ensemble_id`
   - `run_id`
   - console and network outcome
   - operator action taken
   - resulting recovery state
4. PM/control truth refresh across the March 8 control packet so those docs stop mixing evidence classes or overstating Step 3 support

## 5. Evidence model for this wave

| Evidence class | What currently exists | What it proves | What it does not prove |
| --- | --- | --- | --- |
| Unit/contract | `backend/tests/unit/test_probabilistic_ensemble_api.py`, `backend/tests/unit/test_simulation_runner_runtime_scope.py`, related probabilistic schema/storage tests | lifecycle, lineage, cleanup refusal, rerun cloning, run-scoped manifest updates, API payload behavior | browser UX clarity, operator comprehension, real-project runtime stability |
| Fixture-backed browser | `npm run verify:smoke` deterministic Playwright matrix | the bounded Step 2 through Step 5 probabilistic shell still renders and routes correctly against seeded fixtures | real upload/runtime behavior, release readiness, concurrency realism |
| Local-only non-fixture | March 9 live Step 1 through Step 5 pass on `sim_7a6661c37719`; March 10 first-click-success Step 2 through Step 3 rerun on the same simulation family | the path can work against a real local project and the March 10 handoff mitigation has at least one live success case | repeatability, operator package completeness, release-grade confidence |
| Release-grade | none | nothing yet | rollout readiness, supportability, or final H2/H5 closure |

## 6. Known mismatches and tensions entering the wave

These are live repo tensions, not hypotheticals:

- the old H2 ensemble storage contract under-described `run_manifest.json` and still implied that lifecycle state was absent; that is now false in the repo
- the backend/runtime contract is broader than the current Step 3 UI surface, especially around rerun versus retry semantics
- the bounded Step 4 and Step 5 probabilistic seams are real, but they should not absorb more scope until Step 3 operator recovery semantics are explicit and evidenced
- the March 10 first-click-success live rerun reduces the severity of the March 9 handoff race, but the evidence is still local-only and too thin to count as release-grade

## 7. Explicit non-goals for this wave

This wave should not claim or attempt any of the following:

- Step 4 or Step 5 probabilistic depth beyond the already-bounded report-context and exact-report chat seams
- Step 3 history/compare/re-entry expansion beyond what is needed for truthful operator recovery
- release-grade signoff
- calibrated probability claims; this wave is runtime/operator work, not a calibration wave

## 8. Proposed execution order

1. Repair H2 storage/runtime truth docs first so the code-and-doc baseline is honest.
2. Add backend operator-flow coverage where behavior is already implemented but only partially packaged.
3. Harden Step 3 operator controls and copy to match the backend contract.
4. Run full verification plus one documented local-only non-fixture operator pass if the UI semantics change.
5. Refresh the March 8 control packet and task registers using the new evidence classes.

## 9. Exit criteria for this wave

This wave should be considered materially advanced only when all of the following are true:

- Step 3 clearly distinguishes retry, rerun, cleanup, and stop
- backend tests cover the main operator recovery paths at an app/API layer, not only in isolated helper seams
- the docs separate fixture-backed, local-only, and release-grade evidence without ambiguity
- one repeatable local-only non-fixture operator path is written down precisely enough for a fresh session to reproduce
- `I2.2` is either advanced with fresh evidence or remains explicitly blocked with named reasons

## 10. What Was Still Blocked When The Wave Opened

The following items were still blocked at wave entry before the implementation and verification work below landed:

- no Step 3 code/UI change has landed yet in this slice
- no new backend operator-flow tests have landed yet in this slice
- no new non-fixture runtime/browser pass has been executed yet in this slice
- no March 8 control docs have been refreshed yet in this slice
- H5 remains groundwork-only until the operator package and evidence bundle are real

## 11. What landed in the current session

The code-and-doc wave is no longer docs-only.

Landed deliverables:

1. Step 3 now distinguishes same-run launch/retry from child-run rerun and explicit cleanup in `frontend/src/components/Step3Simulation.vue`, `frontend/src/utils/probabilisticRuntime.js`, and `frontend/src/api/simulation.js`.
2. Backend now has an app-level operator-flow suite in `backend/tests/integration/test_probabilistic_operator_flow.py` covering stop -> cleanup -> retry on the same run, rerun lineage to a child run, and active-run cleanup refusal.
3. The repo now has a repeatable local-only non-fixture operator pass via `tests/live/probabilistic-operator-local.spec.mjs`, `playwright.live.config.mjs`, and `npm run verify:operator:local`.
4. The local-only operator pass now writes structured evidence to `output/playwright/live-operator/latest.json` plus a timestamped sibling capture.
5. The H2 ensemble storage contract now matches live lifecycle/lineage persistence, and the March 8 control packet now distinguishes fixture-backed, local-only non-fixture, and release-grade evidence more explicitly.

## 12. Fresh evidence from this wave

Fresh current-session verification:

- `pytest backend/tests/integration/test_probabilistic_operator_flow.py` passed with `3` tests
- `pytest backend/tests/unit/test_probabilistic_ensemble_api.py backend/tests/integration/test_probabilistic_operator_flow.py` passed with `33` tests
- `npm run verify` passed on 2026-03-10 with `41` frontend route/runtime unit tests, `vite build`, and `117` backend tests
- `npm run verify:smoke` passed on 2026-03-10 with `6` deterministic fixture-backed Playwright checks
- `PLAYWRIGHT_LIVE_ALLOW_MUTATION=true npm run verify:operator:local` passed on 2026-03-10 with `1` local-only non-fixture operator pass

Fresh local-only operator capture:

- simulation family: `sim_7a6661c37719`
- current latest Step 2 handoff result in `output/playwright/live-operator/latest.json`: `ensemble 0007`, `run 0001`
- operator actions proven in one pass: stop, retry on the same `run_id`, stop again, cleanup, child rerun creation to `run 0009`
- API/network outcome: every captured `POST` in the current latest flow returned `200`
- console/runtime outcome: `output/playwright/live-operator/latest.json` recorded zero console errors and zero page errors

## 13. Repeatable local-only evidence path

The repo now has one repeatable local-only operator recipe:

- command: `PLAYWRIGHT_LIVE_ALLOW_MUTATION=true npm run verify:operator:local`
- config: `playwright.live.config.mjs`
- test: `tests/live/probabilistic-operator-local.spec.mjs`
- evidence output: `output/playwright/live-operator/latest.json`

Capture rules implemented by the script:

- record `simulationId`, `ensembleId`, `initialRunId`, and `childRunId`
- record each operator action and its response status
- record relevant simulation API network traffic
- record browser console messages and uncaught page errors

Evidence boundary:

- this path is explicitly local-only and mutating
- it is not part of `npm run verify`
- it is not release-grade evidence

## 14. Remaining blockers after the implemented wave

This wave materially advances H2, but it does not close H2 final or H5.

Still open:

- broader stuck-run/operator guidance is still incomplete; the repo now has a first local-only recipe, not a full operator handbook
- live Step 2 local readiness is still bounded by Zep/LLM prerequisites; the deterministic smoke fixture remains separate fixture-backed QA evidence
- repeatable release-grade non-fixture evidence is still absent
- Step 3 history/compare/re-entry depth is still missing
- Step 4 report-body depth and broader Step 5 grounding remain deferred
