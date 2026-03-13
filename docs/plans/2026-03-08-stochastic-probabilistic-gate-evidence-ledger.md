# Stochastic Probabilistic Simulation Gate Evidence Ledger

**Date:** 2026-03-10

This ledger tracks the concrete evidence used to open, hold, or close readiness gates for the stochastic probabilistic simulation program.

## 1. Gate ledger

| Gate | Status | Current evidence | Missing evidence | Owner | Last updated |
| --- | --- | --- | --- | --- | --- |
| G1 Schema and artifact readiness | `partial` | PM packet, H0 baseline, status audit, backend pytest harness, `backend/app/models/probabilistic.py`, probabilistic prepare sidecar artifacts, `backend/app/services/ensemble_manager.py`, `backend/app/services/probabilistic_report_context.py`, prepare/storage/report-context validation tests, and legacy-to-probabilistic re-prepare regression coverage | richer runtime-lifecycle schemas, example fixtures, committed release evidence | Backend + Integration | 2026-03-09 |
| G2 Runtime readiness | `partial` | legacy single-run runner and scripts, standalone uncertainty resolver, ensemble manager, simulation-scoped ensemble APIs, verified run-scoped runner bookkeeping, explicit script `--run-id`/`--seed`/`--run-dir` controls, run-local input staging, public ensemble launch/status plus member-run rerun and ensemble cleanup APIs, cleanup now refusing active runs, manifest lifecycle plus lineage tracking, `close_environment_on_complete` support for stored-run launches, the ensemble-status fallback for persisted terminal storage states when runtime state is missing, batch-start admission control with explicit active/start/defer reporting, full-sidecar probabilistic readiness checks, runner tests, script-contract tests, `backend/tests/integration/test_probabilistic_operator_flow.py`, the bounded `latest_probabilistic_runtime` history summary, the repo-owned local-only `npm run verify:operator:local` path plus `output/playwright/live-operator/latest.json`, one local-only non-fixture browser pass from live upload through Step 5, and six March 10 local-only browser/operator reruns on `sim_7a6661c37719` including the latest `ensemble 0008` / `run 0001` / child `run 0009` capture, plus the bounded local operator runbook and README/.env enablement docs | fuller stuck-run/artifact-inspection handbook depth, a complete release-ops package, and broader repeatable non-fixture runtime verification | Backend | 2026-03-10 |
| G3 Analytics readiness | `partial` | raw action logs, timelines, agent stats, `backend/app/services/outcome_extractor.py`, persisted `metrics.json` artifacts for stored runs, `backend/app/services/ensemble_manager.py` aggregate summaries, `backend/app/services/scenario_clusterer.py`, `backend/app/services/sensitivity_analyzer.py`, the `/summary`, `/clusters`, and `/sensitivity` API routes, and analytics/unit-runtime tests covering partial-log quality flags plus manifest linkage | aggregate consumer fixtures, H3 provenance packaging, and report-facing analytics surfaces | Backend + Report | 2026-03-09 |
| G4 UX readiness | `partial` | Step 2 capability discovery, explicit probabilistic prepare controls including prepared-run sizing, flag-disabled fallback, prepared-artifact summary panel, careful provenance wording, active-prepare stale-state suppression in the Step 2 -> Step 3 handoff, Step 2 runtime-shell-off handoff gating, a Step 3 probabilistic ensemble browser with lifecycle/timeline/failure-state handling plus deterministic selected-run recovery and explicit retry/cleanup/rerun guidance, read-only observed analytics cards for summary/clusters/sensitivity, bounded History -> Step 3 replay when durable probabilistic runtime scope exists, an initial Step 4 probabilistic report-context addendum, a bounded Step 5 report-context banner plus exact-report chat grounding, Step 4/Step 5 escape-first limited-markdown rendering for generated content, saved-report Step 4/Step 5 history re-entry with stable history selectors plus explicit expand/collapse history controls, 42 frontend route/runtime unit tests, a repo-owned `npm run verify:smoke` matrix covering 7 deterministic fixture-backed checks, a separate repo-owned `npm run verify:operator:local` path, one local-only non-fixture browser pass through Step 5, and six March 10 local-only browser/operator reruns that succeeded on the first click | deeper Step 4 surfaces, broader Step 5 interaction grounding beyond the report-agent lane, broader Step 3 history/compare/re-entry, ensemble/history compare entry points, broader browser/device coverage, and repeatable release-grade non-fixture evidence | Frontend | 2026-03-10 |
| G5 Rollout readiness | `partial` | governance intent, root verify script, CI verify workflow now installs Playwright browsers and runs `npm run verify:smoke`, stable local verify behavior that now prefers `backend/.venv/bin/python` when present, backend prepare/runtime-storage flags surfaced through capabilities, deterministic smoke-fixture plus synthetic probabilistic-report seeding paths, the repo-owned local-only `npm run verify:operator:local` command with JSON evidence output, March 10 code mitigation for the transient Step 2 -> Step 3 handoff race, one local-only non-fixture browser pass through Step 5, and six March 10 first-click-success/operator reruns on `sim_7a6661c37719` including the latest `ensemble 0008` capture, plus `.env.example` probabilistic-flag scaffolding, the README local enablement notes, and the bounded local operator runbook | release-grade dashboards/alerts, release decision record, rollback checklist, support ownership, broader report/interaction/calibration flags, and repeatable release-grade non-fixture evidence | Integration + Release | 2026-03-10 |

## 2. Milestone to gate mapping

| Milestone | Gate | Current status | Evidence note |
| --- | --- | --- | --- |
| M0 | G1 | `partial` | H0 exists, but contracts are not yet backed by code |
| M1 | G1 | `implemented` | prepare artifact persistence, validation, frontend consumption, and H1 package now exist; keep regression evidence current |
| M2 | G2 | `partial` | seeded resolution now persists `resolved_config.json` for stored runs, but broader non-fixture runtime evidence and operator packaging are still incomplete |
| M3 | G2 | `partial` | ensemble launch/status, rerun/cleanup semantics including active-run cleanup refusal, lifecycle-lineage tracking, run detail/action/timeline inspection, backend app-level operator-flow tests, the bounded `latest_probabilistic_runtime` history seam, one repo-owned local-only operator path, one local-only non-fixture Step 1 -> Step 5 browser pass, and six March 10 browser/operator reruns now exist with the current latest capture at `ensemble 0008` / `run 0001` / child `run 0009`, but fuller operator handbook depth, broader history/re-entry, and broader repeatable runtime evidence are still missing |
| M4 | G3 | `partial` | aggregate summaries, cluster artifacts, observational sensitivity, and the first probabilistic report-context artifact now exist, but the report body and richer consumer surfaces are still incomplete |
| M5 | G4 | `partial` | Step 2, a truthful Step 3 probabilistic ensemble browser plus explicit recovery controls, Step 2 runtime-shell-off handoff gating, bounded Step 3 history re-entry, an initial Step 4 report-context addendum, the bounded Step 5 report-context banner/chat seam, the Step 4/Step 5 escape-first rendering seam, Step 4/Step 5 saved-report history re-entry, the repo-owned fixture-backed smoke matrix, and the separate repo-owned local-only operator path now exist, but broader Step 3 history/compare/re-entry plus Step 4/Step 5 broader grounding remain materially incomplete and the current evidence is not yet release-grade |
| M6 | G5 | `partial` | verify/CI baselines, flags, a bounded local enablement/runbook package, and a first repo-owned local-only operator evidence path now exist, but the broader telemetry, rollback, support-ownership, and release-evidence package are still missing |
| M7 | post-MVP policy gate | `not started` | calibration/confidence intentionally deferred |

## 3. Session evidence notes

### 2026-03-08

- repo audit confirmed the codebase is still legacy single-run
- H0 baseline package created
- status audit created
- readiness dashboard created
- backend B0/B1 foundation landed: pytest harness, probabilistic prepare models, versioned prepare sidecars, and API validation
- local evidence: `python3 -m pytest backend/tests -q` passed with 17 tests
- backend capability discovery endpoint landed for Step 2
- Step 2 now consumes capabilities, exposes explicit probabilistic prepare controls, and renders prepared-artifact provenance
- standalone uncertainty resolver landed with deterministic tests for fixed/categorical/uniform/normal distributions
- local evidence: `python3 -m pytest backend/tests -q` now passes with 21 tests
- local evidence: `python3 -m pytest backend/tests -q` now passes with 26 tests after the resolver slice
- local evidence: `npm run verify` now passes and exercises both frontend build and backend pytest
- fresh continuation evidence: `npm run verify` passed again after the audit restart, confirming the dirty continuation branch still builds and runs 26 backend tests
- storage-only ensemble manager landed with deterministic create/load/list/delete coverage
- simulation-scoped storage APIs landed behind `PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED` with `ENSEMBLE_RUNTIME_ENABLED` retained as a compatibility alias
- H2 runtime contract draft now captures the live storage/API slice and its explicit deferrals
- local evidence: `python3 -m pytest backend/tests/unit/test_probabilistic_schema.py tests/unit/test_probabilistic_ensemble_api.py tests/unit/test_ensemble_storage.py tests/unit/test_probabilistic_prepare.py tests/unit/test_uncertainty_resolver.py -q` passed with 39 tests
- local evidence: `python3 -m pytest backend/tests -q` now passes with 39 tests
- local evidence: `npm run verify` now passes and exercises the frontend build plus all 39 backend tests after the storage/API slice
- the live `SimulationRunner` now supports composite run-scoped bookkeeping, run-local state/action roots, run-local profile input staging, and targeted cleanup while preserving the legacy `/api/simulation/start` path
- local evidence: `cd backend && python3 -m pytest tests/unit/test_probabilistic_ensemble_api.py tests/unit/test_simulation_runner_runtime_scope.py -q` passed with `10 passed in 0.16s`
- local evidence: `cd backend && python3 -m pytest tests -q` now passes with 45 tests
- local evidence: `npm run verify` now passes and exercises the frontend build plus all 45 backend tests after the B2.3 runner slice
- runtime scripts now accept `--run-id`, `--seed`, and `--run-dir`, honor run-local working roots, and use explicit RNG objects for scheduling helpers while keeping seed language best-effort
- local evidence: `python3 -m pytest backend/tests/unit/test_runtime_script_contracts.py backend/tests/unit/test_simulation_runner_runtime_scope.py -q` passed with `8 passed in 0.12s`
- local evidence: `cd backend && python3 -m pytest tests/unit/test_simulation_runner_runtime_scope.py tests/unit/test_runtime_script_contracts.py tests/unit/test_probabilistic_ensemble_api.py -q` passed with `17 passed in 0.21s`
- local evidence: `python3 -m py_compile backend/scripts/run_parallel_simulation.py backend/scripts/run_twitter_simulation.py backend/scripts/run_reddit_simulation.py` passed
- local evidence: `cd backend && python3 -m pytest tests -q` now passes with 52 tests
- local evidence: `npm run verify` now passes and exercises the frontend build plus all 52 backend tests after the B2.4 script-contract slice; existing Vite chunking warning remains unrelated
- public ensemble-level `start` and `status` routes now exist for batch launch and poll-safe summary status on top of the member-run runtime routes
- local evidence: `cd backend && python3 -m pytest tests/unit/test_probabilistic_ensemble_api.py -q` passed with `12 passed in 0.21s` after the new ensemble launch/status contract landed
- local evidence: `cd backend && python3 -m pytest tests/unit/test_probabilistic_ensemble_api.py tests/unit/test_simulation_runner_runtime_scope.py tests/unit/test_runtime_script_contracts.py -q` passed with `20 passed in 0.29s`
- local evidence: `cd backend && python3 -m pytest tests -q` now passes with 55 tests
- local evidence: `npm run verify` now passes and exercises the frontend build plus all 55 backend tests after the B2.5 ensemble launch/status slice; existing Vite chunking warning remains unrelated
- run detail now includes runtime-backed `runtime_status`, and raw run `actions` and `timeline` routes now exist under the ensemble namespace
- local evidence: `cd backend && python3 -m pytest tests/unit/test_probabilistic_ensemble_api.py -q` passed with `18 passed in 0.32s` after the run detail/actions/timeline follow-on landed
- local evidence: `cd backend && python3 -m pytest tests/unit/test_probabilistic_ensemble_api.py tests/unit/test_simulation_runner_runtime_scope.py tests/unit/test_runtime_script_contracts.py -q` passed with `26 passed in 0.38s`
- local evidence: `cd backend && python3 -m pytest tests -q` now passes with 61 tests
- local evidence: `npm run verify` now passes and exercises the frontend build plus all 61 backend tests after the frontend ensemble API helper export refresh; existing Vite chunking warning remains unrelated
- Step 3 now consumes probabilistic route/runtime state, loads stored ensembles, can start or resume the ensemble runtime shell, exposes selected-run status/action drilldown, and keeps Step 4 explicitly disabled for probabilistic runs
- local evidence: `npm run verify` now passes and exercises frontend route/runtime unit tests, the frontend build, and all 61 backend tests after the Step 3 probabilistic shell slice; existing Vite chunking warning remains unrelated
- Step 3 now monitors one stored run shell from explicit Step 2 route state, auto-starts or resumes it through the member-run runtime routes, consumes the run-scoped `timeline` endpoint, surfaces stopped/failed states honestly, and hard-errors when probabilistic route identifiers are missing instead of silently falling back
- local evidence: `node --test tests/unit/probabilisticRuntime.test.mjs` first failed on the missing `deriveProbabilisticStep3Runtime` export and then passed with `7` tests after the new helper contract landed
- local evidence: `npm run verify` now passes again with `7` frontend route/runtime unit tests, the frontend build, and all `61` backend tests after the Step 3 runtime-hardening slice; existing Vite chunking warning remains unrelated
- local evidence: real browser smoke at `http://127.0.0.1:3000/simulation/smoke-demo/start?mode=probabilistic` shows the Step 3 missing-handoff error state, the disabled Step 4 button, and truthful monitor copy; screenshot captured at `var/folders/hq/wszcq7714pn_ph44jx870jtm0000gn/T/playwright-mcp-output/1773018828203/page-2026-03-09T01-15-24-992Z.png`
- browser smoke blocker: no local simulations exist, so this session could not capture a stored-run happy path without first invoking the long-running seed/project creation flow
- per-run analytics extraction now persists `metrics.json` for stored ensemble runs, appends the artifact pointer into `run_manifest.json`, and removes both the file and pointer during targeted cleanup
- local evidence: `python3 -m pytest backend/tests/unit/test_outcome_extractor.py backend/tests/unit/test_simulation_runner_runtime_scope.py -q` passed with `9 passed in 0.11s`
- local evidence: `python3 -m pytest backend/tests -q` now passes with `65` backend tests after the final B3.1 alignment
- local evidence: `npm run verify` passed after the final B3.1 alignment, running `7` frontend route/runtime tests, building the frontend, and running all `65` backend tests; existing Vite chunking warning remains unrelated
- aggregate summaries now persist on demand from stored run metrics under `backend/app/services/ensemble_manager.py`, and the planned `/api/simulation/<simulation_id>/ensembles/<ensemble_id>/summary` route is live
- local evidence: `python3 -m pytest backend/tests/unit/test_aggregate_summary.py backend/tests/unit/test_probabilistic_ensemble_api.py -q` passed with `21 passed in 0.35s`
- local evidence: `python3 -m pytest backend/tests -q` now passes with `68` backend tests after the B3.2 aggregate-summary slice
- local evidence: a final full-suite rerun caught and fixed a missing `manifest_path` test variable in `backend/tests/unit/test_simulation_runner_runtime_scope.py`; `python3 -m pytest backend/tests -q` now passes with `71` backend tests
- local evidence: `npm run verify` now passes again after the B3.2/test-fix follow-on, running `7` frontend route/runtime tests, building the frontend, and running all `71` backend tests; existing Vite chunking warning remains unrelated
- scenario clustering now persists on demand from stored run metrics under `backend/app/services/scenario_clusterer.py`, and the planned `/api/simulation/<simulation_id>/ensembles/<ensemble_id>/clusters` route is live
- local evidence: `python3 -m pytest backend/tests/unit/test_scenario_clusterer.py backend/tests/unit/test_probabilistic_ensemble_api.py -q` passed with `25 passed in 0.35s` after the B3.3 slice
- local evidence: `python3 -m pytest backend/tests -q` now passes with `79` backend tests after the B3.3 hardening follow-on
- local evidence: `npm run verify` now passes again after the B3.3 hardening follow-on, running `7` frontend route/runtime tests, building the frontend, and running all `79` backend tests; existing Vite chunking warning remains unrelated
- real happy-path Step 2 -> Step 3 browser evidence still could not be captured in this session because the default local backend capability surface reported `probabilistic_prepare_enabled=false`, `probabilistic_ensemble_storage_enabled=false`, and `/api/simulation/list` returned zero simulations even after the servers were brought up for inspection
- observational sensitivity analysis now persists `sensitivity.json` on demand from stored run metrics plus resolved values under `backend/app/services/sensitivity_analyzer.py`, and the planned `/api/simulation/<simulation_id>/ensembles/<ensemble_id>/sensitivity` route is live
- local evidence: `python3 -m pytest backend/tests/unit/test_sensitivity_analyzer.py -q` passed with `2 passed in 0.07s`
- local evidence: `python3 -m pytest backend/tests/unit/test_probabilistic_ensemble_api.py -q -k sensitivity` passed with `2 passed, 20 deselected in 0.11s`
- local evidence: `python3 -m pytest backend/tests -q` now passes with `86` backend tests after the B3.4 sensitivity slice
- Step 3 now renders read-only observed ensemble analytics cards for aggregate summary, scenario clusters, and sensitivity while keeping Step 4 disabled and preserving observational-only wording
- local evidence: `cd frontend && node --test tests/unit/probabilisticRuntime.test.mjs` passed with `11` tests after the analytics-card helper contract landed
- local evidence: `npm run verify` now passes on 2026-03-09 with `11` frontend route/runtime tests, `vite build`, and all `86` backend tests after the Step 3 analytics slice; existing Vite chunking warning remains unrelated
- Step 2 now exposes a prepared-run-count input for probabilistic ensemble sizing, and Step 3 now uses ensemble status plus stored run summaries to browse member runs, switch the selected run, surface selection-recovery notices, and issue selected-run launch/stop actions without weakening the strict initial handoff contract
- local evidence: `node --test frontend/tests/unit/probabilisticRuntime.test.mjs` first failed on the missing `buildProbabilisticEnsembleRequest` helper and then passed with `14` tests after the ensemble-sizing and selected-run-recovery helpers landed
- local evidence: `npm run verify` now passes on 2026-03-09 with `14` frontend route/runtime tests, `vite build`, and all `86` backend tests after the Step 2 prepared-run sizing plus Step 3 stored-run-browser slice; existing Vite chunking warning remains unrelated
- probabilistic report context now persists as `probabilistic_report_context.json`, `POST /api/report/generate` now accepts `ensemble_id` plus `run_id`, and `GET /api/report/<report_id>` now returns persisted `ensemble_id`, `run_id`, and `probabilistic_context` while preserving legacy report behavior
- Step 3 now forwards probabilistic report scope into report generation, `ReportView.vue` reconstructs Step 4 probabilistic state from saved report metadata, and Step 4 renders additive observed report-context cards from the embedded sidecar before falling back to direct artifact fetches
- local evidence: `cd backend && python3 -m pytest tests/unit/test_probabilistic_report_context.py tests/unit/test_probabilistic_report_api.py -q` passed with `4 passed in 0.14s`
- local evidence: `npm run verify` now passes on 2026-03-09 with `15` frontend route/runtime tests, `vite build`, and all `90` backend tests after the report-context plus Step 4 handoff slice; existing Vite chunking warning around `frontend/src/store/pendingUpload.js` remained unrelated

### 2026-03-09 continuation: deterministic happy-path smoke and runtime hardening

- developer-only deterministic smoke seeding now exists through `backend/app/services/probabilistic_smoke_fixture.py` and `backend/scripts/create_probabilistic_smoke_fixture.py`
- the happy-path Step 2 -> Step 3 smoke now exists on `sim_75a9fec75357`, with real browser captures for the prepared Step 2 surface and the Step 3 probabilistic route `?mode=probabilistic&ensembleId=0001&runId=0001`
- the probabilistic Step 3 start path now launches stored runs with graph-memory updates off and `close_environment_on_complete=true`, avoiding command-wait completion drift
- local evidence: `python3 -m pytest backend/tests/unit/test_probabilistic_smoke_fixture.py -q` passed with `2` tests after the runtime-compatible fixture-profile fix
- local evidence: `node --test frontend/tests/unit/probabilisticRuntime.test.mjs` now passes with `18` tests after the close-on-complete start-request addition
- local evidence: `python3 -m pytest backend/tests/unit/test_simulation_runner_runtime_scope.py backend/tests/unit/test_probabilistic_ensemble_api.py backend/tests/unit/test_probabilistic_smoke_fixture.py -q` passed with `31` tests after the runtime/API hardening slice
- local evidence: live local API probes against `sim_75a9fec75357` confirmed that rerun `0001` now ends with `runner_status=completed`, `storage_status=completed`, no active run IDs, and `backend/uploads/simulations/sim_75a9fec75357/ensemble/ensemble_0001/runs/run_0001/run_manifest.json` persisted as `status: "completed"`
- local evidence: `npm run verify` now passes on 2026-03-09 with `18` frontend route/runtime tests, `vite build`, and all `94` backend tests after the deterministic happy-path smoke plus runtime hardening slice; the existing Vite chunking warning around `frontend/src/store/pendingUpload.js` remained unrelated

### 2026-03-09 continuation: H2 lifecycle semantics, repo-owned smoke matrix, and CI wiring

- run manifests now persist lifecycle counters plus rerun lineage so initial starts, retries, reruns, and cleanup operations are distinguishable without overwriting prior evidence
- the public runtime contract now includes `POST /api/simulation/<simulation_id>/ensembles/<ensemble_id>/runs/<run_id>/rerun` plus `POST /api/simulation/<simulation_id>/ensembles/<ensemble_id>/cleanup`, while retry remains the existing `/start` behavior after cleanup policy is applied
- deterministic smoke seeding now supports a synthetic completed probabilistic report with embedded `probabilistic_report_context`, allowing bounded Step 4 and Step 5 browser evidence without live LLM or Zep dependencies
- repo-owned browser smoke now exists in `tests/smoke/probabilistic-runtime.spec.mjs`, `playwright.config.mjs`, and root `npm run verify:smoke`; CI verify now installs Playwright browsers and runs that smoke command before backend verification
- local evidence: `python3 -m pytest backend/tests/unit/test_simulation_runner_runtime_scope.py backend/tests/unit/test_probabilistic_ensemble_api.py backend/tests/unit/test_probabilistic_smoke_fixture.py -q` passed with `38 passed in 0.55s`
- local evidence: `npm --prefix frontend run verify` passed, running `18` frontend route/runtime unit tests and `vite build`
- local evidence: `npm run verify:smoke` passed with `5 passed (5.1s)` on the deterministic fixture-backed Step 2 through Step 5 matrix
- local evidence: `npm run verify` passed on 2026-03-09 with `18` frontend route/runtime tests, `vite build`, and all `99` backend tests after the lifecycle-semantics plus smoke-matrix slice

### 2026-03-09 continuation: Step 5 report-scoped chat and saved-report history re-entry

- the Step 5 report-agent lane now sends optional `report_id`, and `POST /api/report/chat` validates that the report belongs to the requested simulation before building the prompt
- `ReportAgent` now loads the exact saved report when `report_id` is provided and injects saved `probabilistic_context` from report metadata into the report-agent prompt
- Step 5 now distinguishes the report-agent lane from legacy interviews and surveys in its probabilistic banner copy instead of presenting one undifferentiated unsupported state
- history remains simulation/report centric, but the modal now exposes a Step 5 `Deep Interaction` button when a saved report exists and the smoke matrix exercises that re-entry path
- local evidence: `node --test frontend/tests/unit/probabilisticRuntime.test.mjs` passed with `19` tests after the report-chat request helper plus Step 5 copy split
- local evidence: `cd backend && python3 -m pytest tests/unit/test_probabilistic_report_api.py -q` passed with `4 passed in 0.13s` after the exact-report chat scope plus saved-context contract landed
- local evidence: `npm run verify` passed on 2026-03-09, running `19` frontend route/runtime unit tests, `vite build`, and all `101` backend tests after the Step 5 report-scoped chat slice
- local evidence: `npm run verify:smoke` passed with `6 passed (6.7s)` on the deterministic fixture-backed Step 2 through Step 5 matrix after adding saved-report Step 5 history re-entry coverage

### 2026-03-09 continuation: cleanup safety and smoke hardening

- the ensemble cleanup endpoint now refuses active runs instead of silently resetting their storage artifacts back to `prepared`
- the H2 runtime draft now records cleanup as an inactive-run recovery action that must wait until operators stop active runs first
- the saved-report Step 5 history smoke case needed explicit click hardening because the animated history cards could intermittently intercept pointer events in a reused local workspace
- local evidence: `cd backend && python3 -m pytest tests/unit/test_probabilistic_ensemble_api.py -q -k 'cleanup_endpoint_rejects_active_runs or cleanup_endpoint_resets_targeted_runs_only or cleanup_endpoint_clears_in_memory_run_state'` passed with `3 passed, 25 deselected in 0.13s`
- local evidence: `npm run verify` passed on 2026-03-09, running `19` frontend route/runtime unit tests, `vite build`, and all `103` backend tests after the cleanup-safety fix
- local evidence: `npm run verify:smoke` passed with `6 passed (5.4s)` after hardening the Step 5 history re-entry smoke interaction

### 2026-03-09 continuation: verification-first history replay recovery and H2 admission control

- the Step 5 history replay path now relies on stable history `data-testid` selectors keyed to exact `(simulation_id, report_id)` identity instead of force-clicking through overlapping animated cards
- history replay remains simulation/report centric, but newest-first ordering plus stable z-indexing now keeps the newest saved report on top and makes the saved-report Step 4/Step 5 reopen path deterministic in browser verification
- the backend report/history path now relies on deterministic latest-report selection, and the ensemble batch-start route now enforces stored `max_concurrency` as a real admission ceiling with explicit `started_run_ids`, `deferred_run_ids`, and active-run context
- direct member-run `/start` retry with `force=true` now has explicit backend coverage, preserving retry on the same `run_id` while rerun remains the child-run path
- local evidence: `cd backend && python3 -m pytest tests/unit/test_probabilistic_ensemble_api.py -q -k 'launches_all_member_runs_when_capacity_allows or enforces_max_concurrency_and_reports_active_context or force_retries_active_member_run'` passed with `3 passed, 26 deselected in 0.18s`
- local evidence: `cd backend && python3 -m pytest tests/unit/test_probabilistic_ensemble_api.py -q` passed with `29 passed in 0.57s`
- local evidence: `cd frontend && node --test tests/unit/*.test.mjs` passed with `23` tests
- local evidence: `npm run verify:smoke` passed with `6 passed (5.9s)` on the deterministic fixture-backed Step 2 through Step 5 matrix after switching the history replay check to exact selectors
- local evidence: `npm run verify` passed on 2026-03-09, running `23` frontend route/runtime unit tests, `vite build`, and all `106` backend tests after the history replay plus admission-control hardening slice

### 2026-03-09 continuation: explicit history replay controls and live operator evidence

- `frontend/src/components/HistoryDatabase.vue` now adds an explicit history expand/collapse control and keeps collapsed stacks overview-only so only the newest visible card remains interactive until the deck is expanded
- `frontend/src/utils/probabilisticRuntime.js` now exposes utility contracts for history toggle labeling and collapsed-card interactivity, and the frontend runtime unit suite grew from `23` to `25` tests to cover those rules
- `tests/smoke/probabilistic-runtime.spec.mjs` now expands the history deck before targeting the exact saved report, preserving exact `(simulation_id, report_id)` selectors without relying on buried-card clicks
- local evidence: `node --test frontend/tests/unit/probabilisticRuntime.test.mjs` first failed on the missing history toggle/interactivity helpers and then passed with `25` tests after the replay-hardening change
- local evidence: `npm run verify:smoke -- --grep "history can reopen Step 5 from a saved report"` passed with `1 passed (3.8s)` after the history expand-control fix
- local evidence: `npm run verify:smoke` passed with `6 passed (6.2s)` on the deterministic fixture-backed Step 2 through Step 5 matrix after the history replay hardening wave
- local evidence: `npm run verify` passed on 2026-03-09, running `25` frontend route/runtime unit tests, `vite build`, and all `106` backend tests after the history replay hardening wave
- local non-fixture browser evidence: a real upload of `/Users/danielbloom/Desktop/MiroFishES/README.md` progressed through Step 1 graph build, Step 2 probabilistic prepare, Step 3 stored-run launch, Step 4 report generation, and a Step 5 interaction view for `sim_7a6661c37719`, `ensemble 0002`, `run 0001`, and `report_aa7d1002a422`
- local non-fixture operator risk: the first Step 2 -> Step 3 handoff attempt returned `POST /api/simulation/sim_7a6661c37719/ensembles` `400`, while an immediate retried create succeeded and the live Step 3 -> Step 5 flow continued; this is evidence of local operator viability plus remaining race risk, not release-grade closure

### 2026-03-10 continuation: Step 2 -> Step 3 handoff hardening and verification-truth repair

- backend log review tied the March 9 transient first-click `POST /api/simulation/<simulation_id>/ensembles` `400` to a re-prepare race: frontend Step 2 could re-promote itself to ready from stale config polling while a new probabilistic prepare was still active
- `frontend/src/components/Step2EnvSetup.vue` now clears stale config/task/progress state when probabilistic re-prepare starts and refuses to promote the Step 3 handoff while an active prepare task still exists
- `backend/app/services/simulation_manager.py` now treats probabilistic readiness as a full-sidecar invariant over `simulation_config.base.json`, `uncertainty_spec.json`, `outcome_spec.json`, and `prepared_snapshot.json`; `backend/app/api/simulation.py` now reports the exact missing filenames when that invariant is broken
- local evidence: `cd frontend && node --test tests/unit/probabilisticRuntime.test.mjs` passed with `26` tests after adding Step 2 active-task and stale-ready-state regression coverage
- local evidence: `cd backend && .venv/bin/python -m pytest tests/unit/test_probabilistic_prepare.py tests/unit/test_probabilistic_ensemble_api.py -q` passed with `46` tests after adding the partial-sidecar readiness regressions
- local evidence: `npm run verify` passed on 2026-03-10, running `26` frontend route/runtime unit tests, `vite build`, and all `108` backend tests after the handoff and verification-entrypoint hardening slice
- local evidence: `npm run verify:smoke` passed with `6 passed` on 2026-03-10 after updating the repo-root and smoke backend launchers to prefer `backend/.venv/bin/python` when present
- local evidence: one escalated Playwright browser rerun against `http://127.0.0.1:4173/simulation/sim_7a6661c37719` reached the existing Step 2 page, clicked `Start Dual-World Parallel Simulation ->`, received `200` from `POST /api/simulation/sim_7a6661c37719/ensembles`, navigated directly to Step 3 as `ensemble 0003` / `run 0001`, and then stopped the launched member run cleanly
- remaining gap: the March 10 handoff mitigation now has one fresh non-fixture proof, but G2 and G5 remain partial because live evidence is still local-only and not yet repeatable enough for release confidence

### 2026-03-10 continuation: H2 operator hardening and truth refresh

- Step 3 now exposes explicit retry/launch wording for the same `run_id`, explicit cleanup, explicit child rerun creation, and operator guidance that distinguishes when to stop, retry, clean, or rerun
- the repo now has a higher-level backend operator-flow suite in `backend/tests/integration/test_probabilistic_operator_flow.py`
- the first full smoke rerun in this continuation proved that the deterministic Step 3 smoke fixture is a prepared stored shell, not a terminal retry state; the smoke expectation was corrected so fixture-backed evidence stays honest while retry coverage moves to the live operator path
- the repo now has a separate local-only mutating operator command through `playwright.live.config.mjs`, `tests/live/probabilistic-operator-local.spec.mjs`, and `npm run verify:operator:local`
- local evidence: `pytest backend/tests/integration/test_probabilistic_operator_flow.py` passed with `3 passed in 0.14s`
- local evidence: `pytest backend/tests/unit/test_probabilistic_ensemble_api.py backend/tests/integration/test_probabilistic_operator_flow.py` passed with `33 passed in 0.63s`
- local evidence: `npm run verify` passed on 2026-03-10, running `29` frontend route/runtime unit tests, `vite build`, and all `111` backend tests after the Step 3 operator and live-operator-path slice
- local evidence: `npm run verify:smoke` passed with `6 passed (15.9s)` on 2026-03-10 after aligning the Step 3 fixture expectation to the actual prepared-shell contract
- local evidence: `PLAYWRIGHT_LIVE_ALLOW_MUTATION=true npm run verify:operator:local` first passed with `1 passed (2.5s)` on 2026-03-10, creating `ensemble 0004` for `sim_7a6661c37719`, proving stop -> retry on `run 0001` -> stop -> cleanup -> child rerun to `run 0009`, and writing zero-error browser/network evidence to `output/playwright/live-operator/latest.json`

### 2026-03-10 continuation: hybrid H2 truthful-local hardening and PM truth refresh

- docs-only continuation scope: refresh the live-truth packet so it matches the latest March 10, 2026 repo evidence instead of the earlier same-day `ensemble 0004` snapshot
- evidence relied on: the fresh same-session `npm run verify`, `npm run verify:smoke`, and `PLAYWRIGHT_LIVE_ALLOW_MUTATION=true npm run verify:operator:local` passes already recorded above; `jq '.' output/playwright/live-operator/latest.json`; targeted source re-read of `frontend/src/utils/safeMarkdown.js`, `frontend/src/components/Step4Report.vue`, `frontend/src/components/Step5Interaction.vue`, `frontend/src/components/Step2EnvSetup.vue`, and `frontend/src/utils/probabilisticRuntime.js`
- the then-current `output/playwright/live-operator/latest.json` capture at that point in the session was `sim_7a6661c37719`, `ensemble 0007`, initial `run 0001`, child rerun `run 0009`, and all captured operator `POST` requests returned `200`
- PM truth now explicitly records that this operator evidence class is `local-only non-fixture`, not release-grade
- PM truth now explicitly records that live Step 2 local readiness still depends on Zep/LLM prerequisites, while the deterministic smoke fixture remains separate fixture-backed QA evidence
- PM truth now explicitly records that the current hybrid wave addressed Step 2 probabilistic Step 3 handoff gating plus Step 4/Step 5 raw-HTML rendering safety through the shared escape-first renderer seam
- the March 9 report-context planning docs are now marked historical/superseded so they no longer read like live execution guidance
- remaining open truth after the refresh: Step 3 history/compare/re-entry remains incomplete, broader Step 5 grounding remains incomplete, and no document in the repo should claim 100% local readiness yet

### 2026-03-10 continuation: bounded Step 3 history re-entry

- the backend history surface now publishes `latest_probabilistic_runtime`, preferring the newest probabilistic report with durable `ensemble_id` plus `run_id` scope and otherwise falling back to the newest stored ensemble/run shell
- `frontend/src/utils/probabilisticRuntime.js` now derives a bounded History -> Step 3 replay contract from that runtime summary while preserving the older saved-report Step 4/Step 5 helpers
- `frontend/src/components/HistoryDatabase.vue` now exposes a Step 3 replay button plus truthful conditional helper copy instead of the earlier unconditional “Step 3 must still be launched live” message
- local evidence: `cd frontend && node --test tests/unit/probabilisticRuntime.test.mjs` passed with `38` tests after the new history replay helper and selector coverage landed
- local evidence: `cd backend && .venv/bin/python -m pytest tests/unit/test_probabilistic_report_api.py -q` passed with `15 passed`
- local evidence: `npm run verify:smoke -- --grep "history can reopen Step 3 from a saved probabilistic report"` passed with `1 passed`
- local evidence: `npm run verify` passed on 2026-03-10, running `42` frontend route/runtime unit tests, `vite build`, and `119` backend tests after the bounded Step 3 history slice landed
- local evidence: `npm run verify:smoke` passed on 2026-03-10 with `7 passed (8.6s)` after adding Step 3 history re-entry coverage to the deterministic fixture-backed matrix
- local evidence: `PLAYWRIGHT_LIVE_ALLOW_MUTATION=true npm run verify:operator:local` passed again on 2026-03-10 with `1 passed (2.3s)`, advancing `output/playwright/live-operator/latest.json` to `ensemble 0008`, initial `run 0001`, child rerun `run 0009`
- remaining open truth after this continuation: history is still simulation/report centric, compare remains out of MVP, non-report/non-storage-backed Step 3 history entries still have no replay path, and no document in the repo should claim 100% local readiness yet

### 2026-03-10 continuation: local enablement and recovery doc hardening

- `.env.example` now surfaces the default-false probabilistic rollout flags plus the calibration-off default so a fresh local operator can enable the bounded probabilistic path intentionally
- `README.md` now documents the zero-context local enablement path, the capability-check endpoint, Playwright browser installation, the `PLAYWRIGHT_LIVE_SIMULATION_ID` override, and the difference between durable and cleanup-prone run artifacts
- `docs/local-probabilistic-operator-runbook.md` now documents startup steps, capability checks, explicit live-operator simulation-family selection, stuck-run first-response artifact inspection, and the cleanup boundary for `simulation.log` plus `actions.jsonl`
- `docs/plans/2026-03-08-stochastic-probabilistic-readiness-dashboard.md`, `docs/plans/2026-03-08-stochastic-probabilistic-status-audit.md`, and `docs/plans/2026-03-08-stochastic-probabilistic-gate-evidence-ledger.md` now treat the local operator runbook as partially real evidence while keeping H5 release-ops packaging explicitly incomplete
- repo evidence relied on: `backend/app/config.py`, `tests/live/probabilistic-operator-local.spec.mjs`, the existing same-session verify/smoke/operator passes, and the current artifact tree under `backend/uploads/simulations/sim_7a6661c37719/ensemble/`
- local evidence: `npm run verify` passed again on 2026-03-10 after the doc/control refresh with `42` frontend route/runtime unit tests, `vite build`, and `119` backend tests
- local evidence: `npm run verify:smoke` passed again on 2026-03-10 after the doc/control refresh with `7 passed (8.6s)`
- remaining open truth after this continuation: the repo now has a bounded local operator package, but it still does not have release-grade support ownership, dashboards/alerts, rollback materials, or repeatable release-grade non-fixture evidence
