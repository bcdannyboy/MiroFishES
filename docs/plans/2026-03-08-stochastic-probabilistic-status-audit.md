# Stochastic Probabilistic Simulation Status Audit

**Date:** 2026-03-10

This document records repo-grounded implementation status as of 2026-03-10. It tracks actual code and durable artifacts in this repository, not planned intent alone.

## 1. Purpose and audit scope

This audit reconciles the stochastic probabilistic planning packet against the current MiroFishES implementation so execution can proceed from trusted status instead of assumptions.

Audit scope:

- backend prepare, runtime, report, and API layers
- frontend Step 2 through Step 5 surfaces, router, and history
- integration, governance, rollout, and verification surfaces
- planning-packet consistency and execution readiness

## 2. Evidence sources

Primary repo evidence:

- `backend/app/models/probabilistic.py`
- `backend/app/services/ensemble_manager.py`
- `backend/app/services/simulation_manager.py`
- `backend/app/services/simulation_runner.py`
- `backend/app/services/probabilistic_smoke_fixture.py`
- `backend/app/services/uncertainty_resolver.py`
- `backend/app/services/report_agent.py`
- `backend/app/api/simulation.py`
- `backend/app/api/report.py`
- `backend/scripts/run_parallel_simulation.py`
- `backend/scripts/run_twitter_simulation.py`
- `backend/scripts/run_reddit_simulation.py`
- `frontend/src/components/Step2EnvSetup.vue`
- `frontend/src/components/Step3Simulation.vue`
- `frontend/src/components/Step4Report.vue`
- `frontend/src/components/Step5Interaction.vue`
- `frontend/src/components/HistoryDatabase.vue`
- `frontend/src/views/SimulationView.vue`
- `frontend/src/views/SimulationRunView.vue`
- `frontend/src/views/ReportView.vue`
- `frontend/src/views/InteractionView.vue`
- `frontend/src/api/simulation.js`
- `frontend/src/api/report.js`
- `frontend/src/router/index.js`
- `backend/pyproject.toml`
- `frontend/package.json`
- `package.json`
- `.github/workflows/verify.yml`
- `.github/workflows/docker-image.yml`

Primary PM evidence:

- the `docs/plans/2026-03-08-stochastic-probabilistic-*.md` packet

## 3. Status legend

- `implemented`: repo contains the planned capability in materially usable form
- `partially implemented`: adjacent legacy capability exists, but the planned probabilistic contract is incomplete
- `not started`: no meaningful implementation or durable artifact exists
- `blocked`: work cannot safely proceed until named dependencies exist
- `divergent from plan`: code exists but its current architecture conflicts with the planned target model
- `unclear, needs verification`: evidence is insufficient for a confident call

## 4. Repo-grounded current state summary

The repository is still production-anchored to a legacy single-run system, but it now contains real probabilistic prepare, storage, and runner-refactor foundations for probabilistic execution.

Observed truth:

- prepare writes one simulation directory under `backend/uploads/simulations/<simulation_id>/`
- prepare produces `state.json`, `reddit_profiles.json`, `twitter_profiles.csv`, and `simulation_config.json`
- probabilistic prepare additionally persists `simulation_config.base.json`, `uncertainty_spec.json`, `outcome_spec.json`, and `prepared_snapshot.json`
- `prepared_artifact_summary` now exposes `probabilistic_artifacts_complete`, `partial_probabilistic_artifacts`, and `missing_probabilistic_artifacts`, and probabilistic-ready checks now require the full sidecar set instead of treating any one sidecar as sufficient
- storage-only ensemble creation now materializes `ensemble/ensemble_<ensemble_id>/runs/run_<run_id>/` with `ensemble_spec.json`, `ensemble_state.json`, `run_manifest.json`, and `resolved_config.json`
- simulation-scoped storage APIs now exist for ensemble create/list/detail and run list/detail, gated by `Config.PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED` with `ENSEMBLE_RUNTIME_ENABLED` retained as a compatibility alias
- `SimulationRunner` now supports composite run-scoped bookkeeping keyed by `(simulation_id, ensemble_id, run_id)` while preserving the legacy `simulation_id`-only path
- run-scoped launches now persist `run_state.json`, `simulation.log`, and platform `actions.jsonl` under one run directory instead of reusing the simulation root
- run-scoped launches now stage the required legacy profile inputs into the run root before invoking the existing scripts
- runtime scripts now accept explicit `--run-id`, `--seed`, and `--run-dir` arguments and use explicit RNG objects for scheduling helpers
- public member-run runtime routes now exist for run-scoped start, stop, and `run-status` under `/api/simulation/<simulation_id>/ensembles/<ensemble_id>/runs/<run_id>/...`
- public ensemble-level `start` and `status` routes now exist for batch launch and poll-safe summary status under `/api/simulation/<simulation_id>/ensembles/<ensemble_id>/...`
- public runtime-backed run detail, `actions`, and `timeline` routes now exist under the same ensemble namespace for one stored run
- run manifests now sync their `status` field across run launch, stop, cleanup, and completion transitions so stored run summaries do not stay stuck at `prepared`
- stored-run launches now support `close_environment_on_complete`, and the current probabilistic Step 3 path uses that close-on-complete behavior with graph-memory updates left off by default so completed runs do not stay split between runtime truth and command-wait storage state
- targeted runner cleanup now refuses active runs and can operate on one inactive run root without deleting sibling run artifacts
- legacy `/api/simulation/start` remains intact, the probabilistic Step 3 shell calls the member-run runtime routes with explicit `ensemble_id` and `run_id`, and `POST /api/report/generate` now also accepts that same probabilistic scope without breaking the legacy report path
- report generation can now persist `ensemble_id`, `run_id`, and an embedded `probabilistic_context` sidecar in report metadata; explicit probabilistic report generation and report-agent chat now honor the report/interaction rollout flags and resolve by exact saved report scope instead of falling back to an arbitrary latest report for the same simulation, but the generated markdown body plus Step 5 interview/survey lanes are still not ensemble/run/cluster grounded
- `backend/app/services/probabilistic_smoke_fixture.py` plus `backend/scripts/create_probabilistic_smoke_fixture.py` now provide one developer-only deterministic seed path for Step 2 -> Step 3 browser verification without depending on a live graph/LLM prepare flow
- frontend Step 2 now has a capability-gated probabilistic prepare branch, a positive-integer prepared-run-count control for Step 3 ensemble sizing, and `frontend/src/api/simulation.js` exports ensemble/runtime helper methods
- Step 2 now clears stale config, task, and progress state when a new probabilistic prepare starts and refuses to promote itself back to ready from config polling while an active probabilistic prepare task still exists
- Step 2 now also disables the probabilistic Step 3 handoff button when backend capabilities already say runtime shells are unavailable, so operators get an explicit off-state instead of learning through a doomed ensemble-create attempt
- real Step 2 local readiness is still bounded by live Zep plus LLM prerequisites documented in `README.md`, `.env.example`, `docs/local-probabilistic-operator-runbook.md`, and the backend prepare services; the deterministic smoke fixture remains fixture-backed QA evidence, not proof that the live prepare path is self-contained
- Step 3 now consumes explicit probabilistic route/runtime state, loads ensemble status plus stored run summaries, keeps a strict missing-handoff error when `ensembleId` or `runId` is absent, lets operators browse and select stored runs inside the handed-off ensemble, recovers deterministically when the selected run disappears after a valid handoff, exposes explicit selected-run launch/retry, stop, cleanup, and child-rerun actions with operator guidance, consumes the run-scoped `timeline` endpoint, renders explicit stopped/failed runtime states honestly, and now forwards the selected `ensemble_id` plus `run_id` when probabilistic Step 4 generation is enabled
- Step 4 now keeps the legacy report/log stream intact while also consuming saved report metadata plus the embedded probabilistic report-context sidecar to render additive observed summary/cluster/sensitivity cards; Step 5 can now reuse that same saved report metadata to ground the report-agent chat lane on the exact saved report while still keeping interviews and surveys explicitly legacy-scoped
- Step 4 and Step 5 now render report/chat/generated markdown through one shared escape-first limited-markdown utility so raw HTML from generated content is escaped before it reaches `v-html`, and saved Step 4 probabilistic replay now keeps embedded observed analytics visible even when current report flags are off while direct artifact fetches are attempted per missing artifact instead of short-circuiting on the first embedded card
- history is still simulation/report centric and there is still no ensemble-history or compare route, but History can now reopen the bounded Step 3 stored-run shell through `latest_probabilistic_runtime` / saved probabilistic scope when durable `ensemble_id` plus `run_id` evidence exists, Step 4 and Step 5 can still reopen safely from a saved report, and the history deck now uses an explicit expand/collapse control so collapsed stacks stay overview-only instead of exposing buried cards as click targets
- backend pytest tree now exists and passes locally
- fresh local baseline verification now passes via `npm run verify`, which prefers `backend/.venv/bin/python` when present, runs 42 frontend route/runtime unit tests, builds the UI, and runs 119 backend tests
- repo-owned browser smoke now exists via `npm run verify:smoke`, which now runs seven deterministic fixture-backed Playwright checks across the Step 2 prepared state, the Step 3 missing-handoff off-state, the Step 3 stored-run shell, the Step 4 observed addendum, the Step 5 report-context banner, Step 5 saved-report history re-entry, and the new History -> Step 3 saved probabilistic re-entry seam
- a separate repo-owned local-only operator pass now exists via `playwright.live.config.mjs`, `tests/live/probabilistic-operator-local.spec.mjs`, and `npm run verify:operator:local`, writing structured browser/network evidence to `output/playwright/live-operator/latest.json`
- one local-only non-fixture browser pass now exists on the live app: a real `README.md` upload progressed through Step 1 graph build, Step 2 probabilistic prepare, Step 3 stored-run launch, Step 4 report generation, and a Step 5 interaction view for `sim_7a6661c37719`, `ensemble 0002`, `run 0001`, and `report_aa7d1002a422`
- a second March 10 local-only non-fixture browser pass against the existing Step 2 page for `sim_7a6661c37719` created `ensemble 0003` on the first click with `POST /api/simulation/sim_7a6661c37719/ensembles` returning `200`, navigated directly into Step 3 with `run 0001`, and then stopped the launched member run cleanly
- a third March 10 local-only non-fixture operator pass created `ensemble 0004` on the same simulation family and proved stop -> retry on the same `run_id` -> stop -> cleanup -> child rerun to `run 0009`
- a fourth March 10 local-only non-fixture operator pass then refreshed that same repo-owned operator recipe to `ensemble 0005`, initial `run 0001`, child rerun `run 0009`, and all captured operator `POST` requests returning `200`
- a seventh March 10 local-only non-fixture operator pass now overwrote `output/playwright/live-operator/latest.json` with `sim_7a6661c37719`, `ensemble 0008`, initial `run 0001`, child rerun `run 0009`, and all captured operator `POST` requests returning `200`; this remains local-only non-fixture evidence, not release-grade proof
- the March 9 live pass's transient first-click `POST /api/simulation/<simulation_id>/ensembles` `400` is now root-caused to frontend stale Step 2 ready-state promotion during active probabilistic re-prepare plus backend partial-sidecar probabilistic overclaim; both mitigations landed on 2026-03-10, and six fresh non-fixture reruns have now re-proved the handoff, but release-grade non-fixture evidence is still absent
- CI now has a verify workflow in addition to the Docker image workflow
- backend prepare, ensemble-storage, report, interaction, and calibration flags now exist in code and are surfaced through `/api/simulation/prepare/capabilities`

Current identity model implemented in code:

- `project_id`
- `graph_id`
- `simulation_id`
- `mode` as frontend Step 2 -> Step 3 route/runtime state
- `ensemble_id` for storage/API scope under one simulation
- `run_id` for storage/API scope under one ensemble
- `report_id`

Planned but not yet implemented:

- `cluster_id`

## 5. PM-packet inconsistencies resolved or queued

| Issue | Impact | Resolution status | Next action |
| --- | --- | --- | --- |
| `BetterMiroFish` paths in the implementation plan | command examples are misleading | resolved in current session | keep path examples repo-grounded |
| roadmap/dependency-map crosswalk mapped `M7` to `I6` instead of the post-MVP expansion lane | milestone reporting drift | resolved in current session | standardize `M7 -> I7 -> H6` |
| dependency map used `IG1`-`IG4` while governance uses `G1`-`G5` | gate naming drift | resolved in current session | treat `G1`-`G5` as canonical |
| `H0` and `H6` were referenced but not defined in one shared handoff set | missing integration control points | resolved in current session | maintain H0/H1-H6 package set |
| on-disk `AGENTS.md` is absent even though repo instructions are required | startup process ambiguity | resolved for this session | follow the environment-provided repo instructions and record the disk mismatch in the execution log |
| planning packet is untracked in git | planning is not yet durable repo truth | open until committed | commit the packet and this audit after verification |

## 6. Backend reconciliation

| Item | Planned outcome | Repo evidence | Actual status | Why | Next action |
| --- | --- | --- | --- | --- | --- |
| B0.0 | backend pytest harness and fixtures | `backend/tests/conftest.py`, `backend/tests/unit/test_probabilistic_schema.py`, `backend/tests/unit/test_probabilistic_prepare.py` | `implemented` | pytest tree, shared fixtures, and repo-root execution evidence now exist | extend with integration tests as runtime phases land |
| B0.1 | artifact taxonomy locked in runtime-facing form | contracts exist only in docs | `partially implemented` | naming is documented, not adopted in code | implement artifact names in B1 foundation |
| B0.2 | backend JSON schema contracts | docs plus `backend/app/models/probabilistic.py` | `partially implemented` | prepare-phase schemas plus `EnsembleSpec` and `RunManifest` now exist, but aggregate/report/runtime-lifecycle schemas are still incomplete | extend contracts beyond storage artifacts |
| B1.1 | probabilistic schema module | `backend/app/models/probabilistic.py` | `implemented` | minimal prepare-phase models, validation, serialization, and seed-policy structure now exist | extend for resolver/ensemble/runtime phases |
| B1.2 | split baseline config from uncertainty artifacts | `simulation_manager.py` now writes `simulation_config.base.json`, `uncertainty_spec.json`, `outcome_spec.json`, and `prepared_snapshot.json` in probabilistic mode while preserving legacy `simulation_config.json` | `implemented` | sidecar artifact persistence and lineage/version metadata are now in code | add richer artifact fixtures and examples |
| B1.3 | probabilistic prepare API | `/api/simulation/prepare` accepts `probabilistic_mode`, `uncertainty_profile`, and `outcome_metrics`; `/api/simulation/prepare/capabilities` exposes the live prepare domain; `/api/simulation/prepare/status` respects probabilistic intent | `implemented` | prepare contract, capability discovery, and legacy-to-probabilistic re-prepare path are now covered by tests | add fixture-backed H1 examples and keep the status contract aligned as runtime phases land |
| B1.4 | probabilistic-safe profile generation | profile generation exists | `partially implemented` | no stable-vs-variable persona split or preparation seed disclosure | isolate nondeterminism and document limits |
| B2.1 | uncertainty resolver | `backend/app/services/uncertainty_resolver.py`, `backend/tests/unit/test_uncertainty_resolver.py` | `implemented` | a standalone seeded resolver now exists for fixed/categorical/uniform/normal distributions with path patching and manifest capture, and stored ensembles now persist those resolved configs per run | preserve the resolved-config lineage contract and extend supported distributions only when downstream consumers need them |
| B2.2 | ensemble manager and run layout | `backend/app/services/ensemble_manager.py`, `backend/tests/unit/test_ensemble_storage.py` | `implemented` | storage-only ensemble creation, run directory isolation, manifest/config persistence, and load/list/delete helpers now exist with deterministic tests | use this contract to drive B2.3/B2.4 runtime refactors |
| B2.3 | run-scoped `SimulationRunner` | `backend/app/services/simulation_runner.py`, `backend/tests/unit/test_simulation_runner_runtime_scope.py` | `implemented` | runner bookkeeping is now composite-keyed, launch/state/action roots can be run-local, required profile inputs are staged into run roots, targeted cleanup is run-specific, and legacy `/start` compatibility remains intact | expose public ensemble launch/status callers and keep the contract aligned as B2.4/B2.5 land |
| B2.4 | seeded runtime scripts with run dirs | `backend/scripts/run_parallel_simulation.py`, `backend/scripts/run_twitter_simulation.py`, `backend/scripts/run_reddit_simulation.py`, `backend/tests/unit/test_runtime_script_contracts.py` | `implemented` | all three scripts now accept explicit `--run-id`, `--seed`, and `--run-dir`, honor run-local output roots, and use explicit RNG objects for the runtime scheduling helpers while keeping seed language best-effort and honest about downstream nondeterminism | preserve the best-effort boundary in docs and use this verified seam to drive B2.5 |
| B2.5 | ensemble API endpoints | simulation-scoped storage routes plus member-run `start`/`stop`/`run-status`, ensemble-level `start`/`status`, runtime-backed run detail, and raw `actions`/`timeline` inspection endpoints now exist in `backend/app/api/simulation.py` | `implemented` | the planned create, launch, status, run list, and run detail endpoints are now real, the batch-start path now enforces stored `max_concurrency` with explicit `started_run_ids`/`deferred_run_ids` plus active-run context, and the repo still avoids fabricating aggregate probabilities | keep the H2 runtime contract aligned and capture non-fixture operator evidence next |
| B3.1 | per-run outcome extractor | `backend/app/services/outcome_extractor.py`, `backend/app/services/simulation_runner.py`, `backend/tests/unit/test_outcome_extractor.py`, `backend/tests/unit/test_simulation_runner_runtime_scope.py` | `implemented` | stored ensemble runs now persist deterministic `metrics.json` artifacts from the locked count-metric registry, wire the artifact into `run_manifest.json`, preserve legacy single-run roots, and record partial/degraded evidence through explicit quality flags instead of silent omissions | use the new run-metrics contract to drive `B3.2` aggregate summaries and the later H3 analytics package |
| B3.2 | aggregate summary builder | `backend/app/services/ensemble_manager.py`, `/api/simulation/<simulation_id>/ensembles/<ensemble_id>/summary`, `backend/tests/unit/test_aggregate_summary.py`, `backend/tests/unit/test_probabilistic_ensemble_api.py` | `implemented` | stored ensembles now persist `aggregate_summary.json` on demand from run-level metrics, expose the summary through the planned `/summary` route, and include thin-sample plus degraded-run warnings without implying calibrated probabilities | use the live summary contract to drive B3.4 sensitivity analysis and the later H3 aggregate analytics package |
| B3.3 | scenario clustering | `backend/app/services/scenario_clusterer.py`, `/api/simulation/<simulation_id>/ensembles/<ensemble_id>/clusters`, `backend/tests/unit/test_scenario_clusterer.py`, `backend/tests/unit/test_probabilistic_ensemble_api.py` | `implemented` | stored ensembles now persist deterministic `scenario_clusters.json` artifacts on demand, cluster only complete run metrics, normalize cluster mass against total prepared runs, and downgrade missing/invalid/degraded metrics to explicit warnings instead of silently overstating evidence | use the live cluster contract to drive B3.4 sensitivity analysis and the later H3 aggregate analytics package |
| B3.4 | sensitivity analysis | `backend/app/services/sensitivity_analyzer.py`, `/api/simulation/<simulation_id>/ensembles/<ensemble_id>/sensitivity`, `backend/tests/unit/test_sensitivity_analyzer.py`, `backend/tests/unit/test_probabilistic_ensemble_api.py` | `implemented` | stored ensembles now persist observational `sensitivity.json` artifacts on demand from complete run metrics plus resolved values, expose the ranking through the planned `/sensitivity` route, and keep thin-sample plus non-causal warnings explicit instead of implying perturbation semantics or calibrated certainty | package the live sensitivity contract into H3 and add truthful frontend/report consumers next |
| B4.1 | probabilistic report context builder | `backend/app/services/probabilistic_report_context.py`, `backend/tests/unit/test_probabilistic_report_context.py`, `docs/plans/2026-03-08-stochastic-probabilistic-report-context-contract.md` | `implemented` | the backend now persists `probabilistic_report_context.json` by composing aggregate summary, scenario clusters, sensitivity, prepared-artifact provenance, and representative run snapshots with explicit empirical/observational labeling | keep the contract doc aligned as Step 5 grounding and richer Step 4 consumers land |
| B4.2 | ensemble-aware report generation | `backend/app/api/report.py`, `backend/app/services/report_agent.py`, `backend/tests/unit/test_probabilistic_report_api.py` | `partially implemented` | report generation now accepts `ensemble_id`/`run_id` and persists report-scoped probabilistic context metadata, but the report body itself is still the legacy simulation-scoped narrative rather than a true ensemble-aware report renderer | extend the markdown/body generation and provenance enforcement after the first Step 4 consumer stabilizes |
| B4.3 | probabilistic report-agent chat | report-agent chat exists | `partially implemented` | no ensemble/run/cluster grounding exists | extend chat context after B4.1/B4.2 |
| B5.1 | graph/project confidence metadata | absent | `not started` | confidence fields do not exist | keep out of MVP wave |
| B5.2 | graph confidence propagation | absent | `not started` | no confidence metadata exists | keep out of MVP wave |
| B5.3 | calibration artifact management | absent | `not started` | no calibration artifacts or policy enforcement exists | keep out of MVP wave |
| B6.1 | backend feature flags | `Config.PROBABILISTIC_PREPARE_ENABLED`, `Config.PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED` with `ENSEMBLE_RUNTIME_ENABLED` as a compatibility alias, `Config.PROBABILISTIC_REPORT_ENABLED`, `Config.PROBABILISTIC_INTERACTION_ENABLED`, `Config.CALIBRATED_PROBABILITY_ENABLED`, and `/api/simulation/prepare/capabilities` | `partially implemented` | prepare, storage, report, interaction, and calibration slices are now independently gated and discoverable, but rollout-stage controls and broader frontend flag plumbing are still incomplete | keep the backend capability surface aligned while the frontend/off-state package broadens |
| B6.2 | observability/perf instrumentation | logs and progress callbacks exist | `partially implemented` | legacy logging exists but no rollout telemetry model | add metrics/alerts after runtime refactor |
| B6.3 | failure recovery/cleanup/rerun ops | member-run `start`/`stop`, run-targeted cleanup, ensemble-scoped cleanup, rerun creation, lifecycle counters, rerun lineage, direct force-retry coverage, batch admission-control reporting, full-sidecar probabilistic readiness checks, `backend/tests/integration/test_probabilistic_operator_flow.py`, the repo-owned local-only `npm run verify:operator:local` path, the bounded local operator runbook plus README/.env enablement docs, one local-only non-fixture Step 2 -> Step 5 operator pass, and six March 10 local-only Step 2 -> Step 3/operator reruns now exist with the current latest capture at `ensemble 0008` / `run 0001` / child `run 0009` | `partially implemented` | retry via `/start` after cleanup policy, child-run reruns, targeted cleanup that now refuses active runs, explicit active/start/defer reporting, app-level operator-flow tests, bounded artifact-inspection/recovery docs, and March 10 frontend/backend mitigation for the transient first-click ensemble-create `400` are real and now have repeatable local-only proof, but fuller stuck-run/operator handbook depth and release-grade non-fixture recovery evidence are still missing | extend the bounded local operator package into fuller stuck-run/artifact-inspection guidance and broader repeatable runtime evidence |
| B6.4 | release-evidence bundle and ops handoff | absent | `not started` | no full release-evidence bundle, rollback package, or support-ownership handoff exists yet | create after flags/tests/telemetry exist |

## 7. Frontend reconciliation

| Item | Planned outcome | Repo evidence | Actual status | Why | Next action |
| --- | --- | --- | --- | --- | --- |
| F0.1 | probabilistic UX vocabulary | `Step2EnvSetup.vue` plus `docs/plans/2026-03-08-stochastic-probabilistic-frontend-ux-contract.md` | `implemented` | Step 2 wording is now backed by an explicit glossary, provenance rules, and forbidden-language contract for later surfaces | keep the contract aligned as Step 3 through Step 5 land |
| F0.2 | explicit probabilistic surface placement | Step 2 state, Step 3 route/runtime state, and `docs/plans/2026-03-08-stochastic-probabilistic-frontend-ux-contract.md` | `implemented` | cross-step ownership for `mode`, `ensemble_id`, `run_id`, and `cluster_id` is now explicitly documented, and the frontend already uses `mode`, `ensemble_id`, and `run_id` for the current Step 2 -> Step 3 probabilistic browser | keep downstream route/handoff decisions synchronized as Step 4, Step 5, and history work land |
| F1.0 | Step 2 probabilistic prepare orchestration | `Step2EnvSetup.vue` now performs capability discovery, legacy baseline auto-prepare, and explicit probabilistic re-prepare | `partially implemented` | the probabilistic branch exists, legacy flow is preserved, and active re-prepare now clears stale ready-state before Step 3 handoff, but the orchestration is still Step 2-local and not reused elsewhere | codify the final state model and extend smoke coverage |
| F1.1 | Step 2 probabilistic controls | `Step2EnvSetup.vue` now has mode toggle, prepared-run-count input, uncertainty profile selector, and outcome metric selection | `partially implemented` | all planned Step 2 controls are now visible, but the run-count budget is still governed only by frontend positive-integer validation and Step 2-local state | add backend-advertised budget limits and shared validation once the runtime budget contract exists |
| F1.2 | prepared artifact preview | Step 2 renders a compact prepared-artifact summary panel from `prepared_artifact_summary` | `partially implemented` | provenance/version summary exists, but deterministic-vs-uncertain field split is still shallow | deepen preview once more artifact detail exists |
| F1.3 | Step 2 guardrails | disabled-state copy, CTA gating, runtime-shell-off handoff blocking, server error handling, and active-prepare stale-state suppression now exist | `partially implemented` | guardrails are limited to Step 2 and there is no broader frontend flag module; the live prepare path still depends on Zep/LLM prerequisites outside the deterministic smoke fixture | extend off-state handling beyond Step 2 and write the local prerequisite boundary more explicitly in operator docs |
| F2.1 | ensemble progress header | `Step3Simulation.vue`, `SimulationRunView.vue`, `SimulationView.vue`, and the runtime-route helpers now provide a dual-mode Step 3 header plus a probabilistic ensemble browser with status counts, selected-run launch/retry, stop, cleanup, child-rerun actions, operator guidance, lifecycle, timeline, and explicit runtime copy | `partially implemented` | the Step 3 shell now truthfully reflects one handed-off ensemble and one selected run inside it, the fixture-backed smoke covers the prepared-shell control surface, and the new local-only operator pass proves retry/cleanup/rerun behavior against the live app, but centralized off-state plumbing and downstream Step 4/Step 5 adoption are still absent | harden the broader operator state model, keep fixture-vs-live evidence boundaries explicit, and extend shared off-state handling |
| F2.2 | run-level drilldown | Step 3 now lets users inspect stored-run status, seed, raw actions, recent timeline rows, selection notices, and child-rerun re-selection inside the probabilistic shell | `partially implemented` | Step 3 now has a stored-run browser plus deterministic fallback when the selected run disappears after a valid handoff, and the current fixture-backed plus local-only operator coverage is evidenced, but history replay, broader resume flows, and reusable QA coverage are still missing | harden browser/reload semantics and extend the Step 2 -> Step 3 evidence path beyond the current local-only recipe |
| F2.3 | early aggregation widgets | `Step3Simulation.vue`, `frontend/src/utils/probabilisticRuntime.js`, `frontend/tests/unit/probabilisticRuntime.test.mjs`, summary/cluster/sensitivity frontend API helpers | `partially implemented` | Step 3 now renders read-only observed ensemble analytics cards for aggregate summary, scenario clusters, and sensitivity alongside the stored-run browser with explicit loading/error/warning states, but it still lacks richer trend/spread drilldown and happy-path browser evidence | extend the current Step 3 monitor into broader operator and report handoff flows without implying calibrated or report-ready support |
| F3.1 | probabilistic report summary cards | `frontend/src/components/ProbabilisticReportContext.vue`, `frontend/src/components/Step4Report.vue`, `frontend/src/views/ReportView.vue`, `frontend/tests/unit/probabilisticRuntime.test.mjs` | `partially implemented` | Step 4 now renders an additive observed aggregate-summary card from saved report metadata or direct artifact fallback while preserving the legacy report stream, but it still lacks fuller probability-band and calibrated-label treatment | deepen the summary card into a fuller report-facing analysis surface after the current H4 contract settles |
| F3.2 | scenario cluster rendering | the same Step 4 probabilistic report-context component now renders an observed scenario-cluster card | `partially implemented` | Step 4 can now show cluster count, lead-family mass, and prototype-run reference from the report context, but deeper family browsing and early-indicator drilldown are still absent | extend the current card into cluster-family detail without weakening provenance |
| F3.3 | sensitivity/tail-risk views | backend `sensitivity.json` plus `/sensitivity` exist, Step 3 has a read-only observed sensitivity card, and Step 4 now has an initial observed sensitivity card via report context | `partially implemented` | Step 4 can now surface the top observed driver and warnings, but it still lacks richer ranking drilldown and any honest tail-risk comparison view | extend the current observational consumer without inventing causal or calibrated tail-risk semantics |
| F3.4 | preserve current report-generation experience | Step 4 legacy flow still streams report sections and logs while the probabilistic addendum sits beside it, and the rendered report-context markdown now flows through a shared escape-first renderer | `partially implemented` | the new report-context path stays additive and legacy-safe and the raw-HTML seam is now closed, but history replay and full single-run fallback hardening remain thin | preserve the additive design and add replay coverage |
| F4.1 | ensemble-aware interaction context | `frontend/src/components/Step5Interaction.vue`, `frontend/src/views/InteractionView.vue`, `backend/app/api/report.py`, `backend/app/services/report_agent.py`, `frontend/src/utils/safeMarkdown.js` | `partially implemented` | the Step 5 report-agent lane can now send `report_id`, load the exact saved report, reuse saved probabilistic report context, and render generated markdown through the shared escape-first renderer, but interviews and surveys remain legacy-scoped and there is still no ensemble/run/cluster selector or answer-level provenance display | extend the current report-rooted chat seam into explicit run/cluster scope controls and probability provenance cues |
| F4.2 | history and comparison entry points | `backend/app/api/simulation.py`, `backend/tests/unit/test_probabilistic_report_api.py`, `frontend/src/components/HistoryDatabase.vue`, `frontend/src/views/ReportView.vue`, `frontend/src/views/InteractionView.vue`, `frontend/src/utils/probabilisticRuntime.js`, `tests/smoke/probabilistic-runtime.spec.mjs` | `partially implemented` | history is still simulation/report centric, but it now reopens the bounded Step 3 stored-run shell through `latest_probabilistic_runtime` when durable `ensemble_id` plus `run_id` evidence exists, and it still reopens the exact saved Step 4/Step 5 report via deterministic newest-first ordering, stable selectors, and an explicit expand/collapse control that keeps collapsed stacks overview-only; ensemble rows and compare remain absent | extend history beyond the current bounded Step 3 plus saved-report Step 4/Step 5 re-entry seams into ensemble-aware records and decide whether compare stays out of MVP |
| F4.3 | feature-flag/off-state handling | Step 2 consumes `/api/simulation/prepare/capabilities`, blocks Step 3 handoff when runtime shells are already known to be unavailable, Step 3 hard-errors when probabilistic route identifiers are missing, Step 4 now honors `probabilistic_report_enabled`, saved Step 4 replay keeps embedded observed analytics visible even when current flags are off, and Step 5 now renders an explicit probabilistic banner that distinguishes the report-agent lane from legacy interviews/surveys | `partially implemented` | off-state handling now reaches Step 4 and Step 5 more truthfully, but it is still not centralized across history/replay or broader feature-flag plumbing | extract shared flag/off-state plumbing after the report and interaction contracts stabilize |
| F5.1 | frontend probabilistic QA fixtures and smoke matrix | `npm run verify` now runs 42 frontend route/runtime unit tests, builds the frontend, verifies all 119 backend tests, `npm run verify:smoke` covers seven deterministic fixture-backed browser checks across Step 2, Step 3, Step 4, Step 5, Step 5 history re-entry, and the new bounded Step 3 history re-entry path, `npm run verify:operator:local` now provides a repo-owned local-only mutating operator path, one local-only non-fixture browser pass reached Step 5, and six March 10 local-only browser/operator reruns re-proved first-click Step 2 -> Step 3 plus Step 3 operator recovery success with the latest capture at `ensemble 0008` / `run 0001` / child `run 0009` | `partially implemented` | a repo-owned browser-scripted matrix now exists for the bounded fixture-backed path, a separate repo-owned local-only operator path now captures real retry/cleanup/rerun evidence plus browser/network output, and README/runbook now document live-prepare prerequisites more explicitly, but broader browser/device breadth, ensemble-history coverage, repeatability, and release-grade non-fixture evidence are still missing | extend the matrix into richer history/compare flows and convert the current local-only passes into broader release evidence |
| F5.2 | frontend release-evidence bundle | absent | `not started` | no release-evidence workflow exists | add after first probabilistic slice lands |

## 8. Integration and release reconciliation

| Item | Planned outcome | Repo evidence | Actual status | Why | Next action |
| --- | --- | --- | --- | --- | --- |
| I0.1 | H0 contract baseline package | packet exists and H0 now links the shared baseline members | `implemented` | the baseline package is now real enough to govern continuation work, even though the packet is still uncommitted | keep H0 members and ledger links synchronized as contracts evolve |
| I0.2 | terminology and state ownership lock | `docs/plans/2026-03-08-stochastic-probabilistic-frontend-ux-contract.md`, decision log, and API contract updates | `implemented` | vocabulary, provenance, and future ID ownership are now explicitly documented against repo truth | keep the lock current as backend IDs become user-visible |
| I1.1 | H1 prepare-path package | `docs/plans/2026-03-08-stochastic-probabilistic-h1-prepare-path-contract.md` now captures the live prepare contract | `partially implemented` | H1 exists, but durable JSON fixtures and signoff evidence are still thin | add example fixtures and review notes |
| I2.1 | H2 runtime contract draft | storage/runtime handoff now covers resolver, ensemble storage, the verified B2.3 runner slice, the explicit B2.4 script-launch seam, ensemble-level `start`/`status`, run-scoped detail/action/timeline inspection routes, `close_environment_on_complete`, rerun plus cleanup semantics, manifest lifecycle plus lineage tracking, the status-aggregation fallback for missing runtime state, the Step 3 explicit retry/cleanup/rerun surface, the repo-owned Step 2 through Step 5 fixture-backed smoke harness, the repo-owned local-only operator path, the bounded local operator runbook plus README/.env enablement docs, one local-only non-fixture Step 1 -> Step 5 browser pass, and six March 10 local-only browser/operator reruns on `sim_7a6661c37719` with the current latest evidence at `ensemble 0008` / `run 0001` / child `run 0009` | `partially implemented` | the backend/runtime contract and truthful Step 3 through Step 5 bounded frontend handoff are now real, a bounded Step 3 history re-entry seam now exists, and a bounded local operator package exists, but fuller operator handbook depth, release-grade non-fixture evidence, and broader history/re-entry adoption remain deferred | extend H2 from the current lifecycle contract into fuller operator runbooks, broader repeatable evidence, and the final H2 package |
| I2.2 | H2 runtime contract final | absent | `blocked` | the backend public runtime contract now includes retry, rerun, cleanup, active-run cleanup refusal, real batch admission-control semantics, the bounded `latest_probabilistic_runtime` history seam, the fixture-backed smoke baseline, a repo-owned local-only operator pass, a bounded local operator runbook plus README/.env enablement docs, one local-only non-fixture Step 1 -> Step 5 browser pass, six March 10 local-only browser/operator reruns on `sim_7a6661c37719`, and March 10 root-cause analysis plus code mitigation for the transient first-click ensemble-create `400`, but final H2 still lacks fuller operator handbook depth, broader repeatable non-fixture evidence, and broader Step 3 replay/history/compare guidance | unblock through fuller runbook completion, broader repeatable non-fixture verification, and the final H2 package |
| I3.1 | H3 aggregate analytics package | `docs/plans/2026-03-08-stochastic-probabilistic-aggregate-summary-contract.md`, `docs/plans/2026-03-08-stochastic-probabilistic-scenario-clusters-contract.md`, `docs/plans/2026-03-08-stochastic-probabilistic-sensitivity-contract.md`, `/summary`, `/clusters`, `/sensitivity` | `partially implemented` | the first three aggregate analytics artifacts and their dedicated contracts now exist, but report-facing provenance rules, consumer fixtures, and the full H3 handoff package are still absent | finish the H3 package with field-level provenance notes, frontend/report examples, and rollout-safe wording |
| I4.1 | H4 report/interaction package | `docs/plans/2026-03-08-stochastic-probabilistic-report-context-contract.md`, report-context artifact persistence, the Step 4 report-context consumer, and the bounded Step 5 report-scoped chat/history seam now exist | `partially implemented` | the H4 package now covers the report-context artifact, the first Step 4 consumer, exact-report Step 5 chat grounding, and saved-report Step 5 re-entry, but run/cluster grounding, reviewed answer examples, and fuller unsupported-claim guidance remain open | extend H4 from report-rooted grounding into explicit run/cluster semantics and broader interaction QA |
| I5.1 | H5 release-ops package | absent | `not started` | no full evidence bundle, dashboard/alert map, rollback package, or support-ownership handoff exists yet | create after flags/tests/telemetry exist |
| I6.1 | gate-evidence ledger | `docs/plans/2026-03-08-stochastic-probabilistic-gate-evidence-ledger.md` exists and records verified test/code evidence | `implemented` | the ledger is now the live gate-evidence surface | keep it current whenever verification evidence changes |
| I6.2 | dependency/escalation review cadence | absent | `not started` | no recurring review log exists | record in execution log and weekly cadence docs |
| I7.1 | staged rollout control | rollout stages exist in docs | `partially implemented` | stages are documented, not evidence-backed | drive from new gate ledger |
| I7.2 | H6 post-MVP calibration/confidence handoff | post-MVP intent exists in docs | `partially implemented` | no explicit handoff package existed | define H6 and keep out of MVP scoring |

## 9. Immediate subtask execution wave

The first execution wave is ready now and should be treated as the highest-leverage bundle:

| Subtask | Status | Why it is ready now | Owner lane |
| --- | --- | --- | --- |
| B0.0.a | `implemented` | no dependency | Backend |
| B0.0.b | `implemented` | immediately after test tree exists | Backend |
| B0.0.c | `implemented` | immediately after shared fixtures exist | Backend |
| B0.0.d | `implemented` | validates repo-root/backend-root execution behavior early | Backend |
| B1.1.a | `implemented` | contracts are documented well enough to encode initial models | Backend |
| B1.1.b | `implemented` | follows B1.1.a | Backend |
| B1.1.c | `implemented` | follows B1.1.a | Backend |
| B1.1.d | `implemented` | follows B1.1.a | Backend |
| B1.2.a | `implemented` | ready after B1.1 | Backend |
| B1.2.b | `implemented` | ready after B1.1 | Backend |
| B1.2.c | `implemented` | ready after B1.1 | Backend |
| B1.2.d | `implemented` | ready after B1.1 | Backend |
| B1.2.e | `implemented` | ready after B1.1 | Backend |
| B1.3.a-d | `implemented` | ready after B1.2 | Backend/API |
| F0.1.a-c | `implemented` | vocabulary/provenance contract now exists in PM docs | Frontend/PM |
| F0.2.a-d | `implemented` | state-ownership matrix now exists in PM docs | Frontend/PM |
| F5.1 baseline harness definition | `partially implemented` | route/runtime unit tests, the root frontend build verify baseline, a repo-owned `npm run verify:smoke` Playwright harness now cover seven deterministic fixture-backed Step 2 through Step 5 checks including exact-selector Step 5 history re-entry plus the bounded Step 3 history re-entry seam, a separate repo-owned `npm run verify:operator:local` path now captures real Step 2 -> Step 3 plus Step 3 recovery actions on a live local simulation family, one local-only non-fixture browser pass reached Step 5, and six March 10 local-only browser/operator reruns re-proved first-click Step 2 -> Step 3 handoff success with the current latest capture at `ensemble 0008` / `run 0001` / child `run 0009`, but broader history/compare and release-grade evidence are still absent | Frontend/QA |
| I0.1.a-c | `implemented` | H0 + control docs now exist and are being maintained as the live control system | Integration/PM |
| I6.1 initial ledger | `implemented` | the first gate ledger now exists and is being refreshed with verification evidence | Integration/PM |
| B2.2.a-e | `implemented` | ensemble/run storage layer, artifacts, and load/list helpers now exist with tests | Backend |
| B2.3.a-d | `implemented` | composite runner identity, run-local IO, targeted cleanup, and legacy compatibility are now verified in code | Backend |
| B2.5 storage + ensemble runtime routes | `implemented` | create/list/detail storage endpoints, member-run `start`/`stop`/`run-status`, ensemble-level `start`/`status`, enriched run detail, and raw run `actions`/`timeline` inspection routes are live behind the dedicated storage/runtime flag surface | Backend/API |

## 10. Highest-leverage ready work

1. Finish the remaining H2 operator runbook package on top of the now-real retry/rerun/cleanup semantics, lifecycle/lineage manifests, repo-owned smoke harness, and the now-explained plus once-rerun Step 2 -> Step 3 ensemble-create race (`I2.2`, `B6.3`).
2. Deepen Step 4 and Step 5 probabilistic surfaces on top of the now-stable `probabilistic_report_context` plus honesty-banner baseline without overstating support, but only after the H2 operator package is no longer surfacing unresolved handoff risk (`F3.x`, `F4.x`, `I4.1`).
3. Add history, compare, reload, and re-entry semantics for stored ensembles and probabilistic reports so the current Step 3 through Step 5 path survives beyond the happy path (`F2.2`, `F4.2`).
4. Assemble the first release-ops and evidence package, keeping fixture-backed smoke clearly separated from non-fixture runtime proof and documenting that live Step 2 still depends on Zep/LLM prerequisites (`B6.4`, `F5.2`, `I5.1`).
5. Maintain H0 through H4, the execution log, the readiness dashboard, and the gate ledger so implementation and PM status do not drift again (`I0.1`, `I2.1`, `I4.1`, `I6.1`).

## 11. Blockers and deferred items

Blocked by missing runtime/report foundation:

- Step 4 probabilistic depth beyond the current additive summary/cluster/sensitivity cards
- Step 5 ensemble-aware chat context
- structured ensemble-aware history replay beyond the current saved-report Step 4/Step 5 reopen path
- H3 through H5 handoff packages
- a self-contained live Step 2 local path without Zep/LLM prerequisites

Explicitly deferred from MVP readiness scoring:

- graph-confidence work
- calibration artifacts and calibrated probability surfaces
- post-MVP H6 rollout work
