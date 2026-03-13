# Stochastic Probabilistic Simulation H2 Runtime Contract Draft

**Date:** 2026-03-10

## 1. Purpose

This document now serves as the forward-looking runtime draft that sits on top of the implemented storage contract, the verified B2.3 runner seam, and the explicit B2.4 script-launch seam.

Current implemented truth lives in:

- `docs/plans/2026-03-08-stochastic-probabilistic-h2-ensemble-storage-contract.md`

This draft exists to record what still must land before H2 can be considered runtime-complete.

## 2. Current implemented base

As of 2026-03-09, the repo already has:

- probabilistic prepare artifacts
- seeded uncertainty resolution
- storage-only ensemble creation under one `simulation_id`
- simulation-scoped storage APIs for ensemble create/list/detail and run list/detail
- public member-run `start`, `stop`, and `run-status` routes under the same simulation-scoped ensemble namespace
- public ensemble-level `start` and `status` routes for batch launch and poll-safe summary state
- batch-start admission control that now enforces stored `max_concurrency` with stable `run_id` order plus explicit `started_run_ids`, `deferred_run_ids`, and active-run context
- public member-run `rerun` and ensemble-scoped `cleanup` routes under the same simulation namespace
- runtime-backed `GET /api/simulation/<simulation_id>/ensembles/<ensemble_id>/runs/<run_id>` detail semantics, including `runtime_status`
- raw run `actions` and `timeline` inspection routes under the same ensemble namespace
- Step 2 route/runtime handoff helpers for probabilistic Step 3 shells using `mode`, `ensembleId`, and `runId`
- a Step 3 probabilistic runtime browser that uses explicit Step 2 handoff (`mode`, `ensembleId`, `runId`) to load one stored ensemble, browse member runs, start/stop or rerun one selected run, inspect the selected run's `actions` plus `timeline`, surface selection recovery and failure states honestly, and keep Step 4 wording aligned with the current capability-gated addendum path
- run-scoped `SimulationRunner` bookkeeping using composite `(simulation_id, ensemble_id, run_id)` keys
- run-local `run_state.json`, `simulation.log`, and per-platform `actions.jsonl` roots when the runner is invoked with run scope
- run-local staging of legacy profile inputs before script launch
- explicit `--run-id`, `--seed`, and `--run-dir` plumbing across all three runtime entrypoints
- `close_environment_on_complete` launch support so probabilistic stored runs can exit cleanly instead of staying in command-wait mode
- explicit RNG objects for runtime scheduling helpers, including separate platform RNG streams in the parallel script
- targeted run cleanup without deleting sibling run roots, and active runs are now refused until operators stop them explicitly
- persisted `run_manifest.json` lifecycle counters plus rerun lineage so initial starts, retries, reruns, and cleanup operations are distinguishable without overwriting prior evidence
- status aggregation that can still surface persisted `completed`/`failed` storage truth when runtime state is unavailable, without treating storage-only `running` as proof of an active process
- a repo-owned Playwright smoke harness now covers the Step 2 prepared state, the Step 3 missing-handoff off-state, one stored-run Step 3 shell path, the Step 4 observed addendum, and the Step 5 honesty banner on a deterministic fixture-backed path
- one local-only non-fixture browser pass now exists for the live probabilistic operator path: a real upload of `README.md` progressed through Step 1 graph build, Step 2 probabilistic prepare, Step 3 stored-run launch, Step 4 report generation, and a Step 5 interaction view for `sim_7a6661c37719`, `ensemble 0002`, `run 0001`, and `report_aa7d1002a422`
- probabilistic prepare status and ensemble creation now require the full sidecar set (`simulation_config.base.json`, `uncertainty_spec.json`, `outcome_spec.json`, and `prepared_snapshot.json`) and surface explicit missing-artifact detail instead of overclaiming probabilistic readiness from any one sidecar file
- the Step 2 probabilistic handoff now clears stale config/task/progress state when re-prepare starts and refuses to promote itself back to ready from config polling while an active prepare task still exists
- dedicated backend gating through `Config.PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED` with `ENSEMBLE_RUNTIME_ENABLED` as a compatibility alias

That base contract is real and should be treated as the current backend/runtime truth for H2.

## 3. Still missing for runtime-final H2

The final H2 package still requires:

- final written operator lifecycle/runbook semantics for stuck, partial, failed, retried, rerun, and cleaned runs
- explicit support guidance for when `/start` is a retry versus when `/rerun` should be used to create a new child run
- fuller frontend adoption guidance beyond the current Step 3 browser, including history/re-entry semantics plus Step 4 and Step 5 deferrals
- repeatable non-fixture runtime evidence beyond the current March 9 Step 1 -> Step 5 browser pass and the March 10 first-click-success Step 2 -> Step 3 rerun
- non-fixture concurrency and isolation evidence beyond the current unit/contract coverage plus one local-only browser pass
- release-grade evidence that the new lifecycle semantics remain stable outside deterministic fixtures

## 4. Draft runtime rules that remain to be implemented

- `simulation_id` remains the parent compatibility identity
- `ensemble_id` and `run_id` remain simulation-scoped until a deliberate global-ID migration changes the API contract
- storage-only routes must remain additive and must not break `/api/simulation/start`
- internal run-scoped launches must preserve the legacy single-run path behind compatibility adapters
- retry means restarting the same stored run through the existing `/start` path after targeted cleanup policy is applied; it must not overwrite lineage or spawn a new `run_id`
- rerun means creating a new child run through `/api/simulation/<simulation_id>/ensembles/<ensemble_id>/runs/<run_id>/rerun`; it must preserve the source run and record parent/source lineage in the new manifest
- cleanup means removing volatile runtime artifacts while preserving resolved-config lineage inputs by default; it may target one explicit run subset through `/api/simulation/<simulation_id>/ensembles/<ensemble_id>/cleanup`, but it must refuse runs that still have active runtime state until they are stopped first
- active-run cleanup refusal is an operator safety rule, not a soft warning: cleanup must wait for an explicit stop or terminal runtime state before retry can reuse the same `run_id`
- ensemble batch start must treat stored `max_concurrency` as a real ceiling across the ensemble, use stable `run_id` ordering for requested launches, and return explicit active/start/defer reporting rather than claiming all requested runs started
- probabilistic Step 3 must error honestly when `ensemble_id` or `run_id` are missing instead of silently guessing another stored run before handoff
- once the explicit handoff exists, probabilistic Step 3 may recover from a disappeared selected run by choosing another stored run deterministically and mirroring that change back into query state
- no Step 3 through Step 5 probabilistic shell may claim full runtime support until it consumes the current contract behind explicit off-states and truthful copy
- the March 9 live operator evidence showed one transient first-click ensemble-create `400` immediately after probabilistic prepare, followed by a successful retried create and a continued Step 3 -> Step 5 flow; the current repo attributes that race to Step 2 stale ready-state promotion during active re-prepare plus backend partial-sidecar probabilistic overclaim, both mitigations landed on 2026-03-10, and one fresh non-fixture rerun on the same simulation family has since reproduced a first-click `200` into Step 3, but H2 remains operator-usable rather than runtime-final until that evidence is repeatable and backed by runbooks

## 5. Promotion criteria to final H2

This draft can be promoted to a runtime-final H2 package only when all of the following are true:

- the B2.4 script/runtime seam is implemented and verified without overstating downstream deterministic guarantees
- B2.5 public launch/status/detail/action/timeline semantics are implemented and verified
- runtime-backed ensemble and run status semantics are documented
- batch admission-control semantics are documented and verified
- targeted run cleanup/stop semantics are documented
- retry/rerun/cleanup semantics are documented or explicitly deferred
- verification evidence covers seeded reproducibility, isolation, legacy compatibility, and the Step 2 -> Step 3 stored-run browser handoff plus failure/off-state and happy-path behavior through the repo-owned smoke harness, with any remaining non-fixture gaps named explicitly
