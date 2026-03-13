# Stochastic Probabilistic Simulation Readiness Dashboard

**Date:** 2026-03-10

This dashboard measures true v1.0 readiness using implemented evidence only. Planned intent without code, tests, or durable control artifacts does not count as ready.

## 1. Overall readiness summary

Current overall assessment:

- MVP/v1.0 readiness: `low`
- current system state: legacy single-run product remains the production truth, but probabilistic prepare, seeded resolution, ensemble storage artifacts, simulation-scoped ensemble APIs, a verified run-scoped runner seam, an explicit runtime script CLI/root/seed seam, ensemble-level launch/status plus rerun/cleanup APIs, runtime-backed run detail/actions/timeline APIs, manifest lifecycle plus lineage tracking, deterministic run-level `metrics.json` extraction, on-demand `aggregate_summary.json`, `scenario_clusters.json`, observational `sensitivity.json`, a persisted `probabilistic_report_context.json` path, the `/summary`, `/clusters`, and `/sensitivity` routes, a Step 2 prepared-run-count control, truthful Step 2 runtime-shell-off handoff gating, a truthful Step 3 probabilistic ensemble browser with selected-run recovery plus read-only observed analytics cards, bounded History -> Step 3 stored-shell re-entry through durable probabilistic runtime scope, a bounded Step 4 observed ensemble addendum, a bounded Step 5 report-agent lane grounded on the exact saved report plus saved probabilistic context, Step 4/Step 5 escape-first limited-markdown rendering for generated content, saved-report Step 4/Step 5 history re-entry with an explicit expand/collapse history control, collapsed-stack overview-only interaction, Step 2 stale-ready-state suppression during active probabilistic re-prepare, full-sidecar probabilistic readiness checks, and batch-start admission control that now reports active, started, and deferred run IDs now exist
- control-plane health: `improving` in this session through H0, status audit, readiness dashboard, execution log, and gate ledger creation
- fresh verification baseline: `npm run verify` passed on 2026-03-10, running 42 frontend route/runtime unit tests, building the frontend, and running 119 backend tests; `npm run verify:smoke` also passed on 2026-03-10 with 7 deterministic fixture-backed Playwright checks, and `PLAYWRIGHT_LIVE_ALLOW_MUTATION=true npm run verify:operator:local` passed with 1 local-only non-fixture operator check whose current `output/playwright/live-operator/latest.json` capture is `sim_7a6661c37719`, `ensemble 0008`, initial `run 0001`, child rerun `run 0009`
- Phase 5 confidence/calibration work is excluded from MVP readiness scoring

## 2. Gate scoreboard

| Gate | Status | Evidence present | Missing evidence | Owner | Last updated |
| --- | --- | --- | --- | --- | --- |
| G1 Schema and artifact readiness | `partial` | planning packet, H0 baseline, status audit, backend pytest harness, probabilistic prepare schemas, versioned prepare artifacts, storage-level `EnsembleSpec`/`RunManifest`, ensemble/run artifact persistence, the new `probabilistic_report_context.json` artifact, and legacy-to-probabilistic re-prepare regression tests | richer runtime-lifecycle schemas, example fixtures, committed release evidence | Backend + Integration | 2026-03-09 |
| G2 Runtime readiness | `partial` | legacy single-run runtime, standalone seeded uncertainty resolver, ensemble manager, simulation-scoped ensemble APIs, run-scoped `SimulationRunner` bookkeeping, explicit script `--run-id`/`--seed`/`--run-dir` plumbing, run-local profile staging, member-run rerun plus ensemble cleanup APIs, cleanup now refusing active runs, manifest lifecycle plus lineage tracking, `close_environment_on_complete` support for stored-run launches, runtime-backed run detail/actions/timeline APIs, batch-start admission control with explicit active/start/defer reporting, backend app-level operator-flow tests, the repo-owned local-only `npm run verify:operator:local` path plus `output/playwright/live-operator/latest.json`, one local-only non-fixture browser pass from live upload through Step 5, six March 10 local-only browser/operator reruns on `sim_7a6661c37719` including the fresh `ensemble 0008` / `run 0001` / child `run 0009` capture, the bounded `latest_probabilistic_runtime` history summary, March 10 frontend/backend mitigation for the previously observed first-click Step 2 -> Step 3 ensemble-create `400`, and the bounded local operator runbook plus README/.env enablement docs | fuller stuck-run/artifact-inspection handbook depth, a complete release-ops package, and broader repeatable non-fixture runtime verification | Backend | 2026-03-10 |
| G3 Analytics readiness | `partial` | raw logs/timelines/agent stats, run-level `metrics.json` extraction, on-demand `aggregate_summary.json`, `scenario_clusters.json`, observational `sensitivity.json`, the persisted `probabilistic_report_context.json` path, the `/summary`, `/clusters`, and `/sensitivity` API routes, analytics unit coverage, and report-context/report-API tests | richer H3 packaging, consumer fixtures, and full report/chat grounding rules | Backend + Report | 2026-03-09 |
| G4 UX readiness | `partial` | legacy Step 2-5 UI, Step 2 capability-gated mode selection, probabilistic prepare controls including prepared-run sizing, prepared-artifact summary, active-prepare stale-state suppression in the Step 2 -> Step 3 handoff, Step 2 runtime-shell-off handoff gating, a Step 3 probabilistic ensemble browser with lifecycle/timeline/failure-state handling plus deterministic selected-run recovery and explicit retry/cleanup/rerun guidance, read-only observed ensemble analytics cards for summary/clusters/sensitivity, bounded History -> Step 3 replay when durable probabilistic runtime scope exists, a bounded Step 4 observed ensemble addendum, a bounded Step 5 report-agent banner plus exact-report chat grounding, Step 4/Step 5 escape-first limited-markdown rendering for generated content, saved-report Step 4/Step 5 history re-entry with stable selectors, deterministic card ordering, and explicit expand/collapse history controls, 42 frontend route/runtime unit tests, a repo-owned `npm run verify:smoke` matrix covering 7 deterministic fixture-backed checks, a separate repo-owned `npm run verify:operator:local` path, one local-only non-fixture browser pass through Step 5, and six March 10 local-only browser/operator reruns that succeeded on the first click | fuller Step 4 report-body consumers, broader Step 5 interaction grounding beyond the report-agent lane, broader Step 3 history/compare/re-entry, ensemble/history compare entry points, broader browser/device coverage, and repeatable release-grade non-fixture evidence | Frontend | 2026-03-10 |
| G5 Rollout readiness | `partial` | governance doc, risk register, root verify script, CI verify workflow now installs Playwright browsers and runs `npm run verify:smoke`, stable local verify behavior that now prefers `backend/.venv/bin/python` when present, backend prepare/storage/report/interaction/calibration flags surfaced through capabilities, a deterministic smoke fixture plus synthetic probabilistic report seeding path, the repo-owned local-only `npm run verify:operator:local` command with JSON evidence output, March 10 code mitigation for the transient Step 2 -> Step 3 handoff race, one local-only non-fixture browser pass through Step 5, six March 10 local-only browser/operator reruns on `sim_7a6661c37719` including the fresh `ensemble 0008` capture, `.env.example` probabilistic-flag scaffolding, the README local enablement notes, and the bounded local operator runbook | release-grade alerts/metrics, release evidence bundle, release decision records, rollback checklist, support ownership, and repeatable release-grade non-fixture evidence | Integration + Release | 2026-03-10 |

## 3. Milestone scoreboard

| Milestone | Definition | Status | Blocking item | Evidence path |
| --- | --- | --- | --- | --- |
| M0 | contract package ratified | `partial` | H0 and packet must be tracked and used as one baseline | `docs/plans/2026-03-08-stochastic-probabilistic-h0-contract-baseline.md` |
| M1 | probabilistic artifacts persist in prepare flow | `implemented` | maintain H1 package and regression coverage as follow-on work lands | status audit backend section |
| M2 | seeded single-run resolution works | `partial` | resolver-backed `resolved_config.json` artifacts are now persisted for stored runs, but broader non-fixture runtime evidence and operator packaging are still incomplete | status audit backend section |
| M3 | multi-run ensemble execution works | `partial` | ensemble lifecycle, rerun/cleanup, lifecycle-lineage tracking, explicit Step 3 retry/cleanup/rerun controls, backend app-level operator-flow tests, the bounded `latest_probabilistic_runtime` history seam, and one repo-owned local-only operator path now exist with the latest capture at `ensemble 0008` / `run 0001` / child `run 0009`, but fuller operator handbook depth, broader history/re-entry, and broader runtime evidence are still incomplete | status audit backend section |
| M4 | aggregate summaries, scenario clusters, and sensitivity exist | `partial` | the three aggregate analytics artifacts plus the first report-context package now exist, but report-body consumers, richer provenance packaging, and deeper frontend surfaces are still incomplete | status audit backend section |
| M5 | Step 2 through Step 5 probabilistic UI path is usable | `partial` | Step 2, the Step 3 ensemble browser plus explicit recovery controls, Step 2 runtime-shell-off handoff gating, bounded Step 3 history re-entry, the Step 4 observed addendum, the bounded Step 5 report-context banner/chat seam, the Step 4/Step 5 escape-first rendering seam, Step 4/Step 5 saved-report history re-entry, the fixture-backed smoke matrix, and the separate repo-owned local-only operator path now exist, but broader Step 3 history/compare/re-entry plus Step 4/Step 5 broader depth remain materially incomplete and the current evidence is still not release-grade | status audit frontend section |
| M6 | operational hardening and rollout readiness complete | `partial` | verify/CI baselines, flags, a bounded local enablement/runbook package, and a first repo-owned local-only operator evidence path now exist, but the broader telemetry, rollback, support-ownership, and release-evidence package are still missing | gate ledger |
| M7 | calibration and graph-confidence work complete | `post-MVP, not counted` | Phase 5 intentionally deferred | decision log |

## 4. Lane scoreboard

| Lane | Implemented | Partial / divergent | Not started / blocked | Notes |
| --- | --- | --- | --- | --- |
| Backend foundation | 14 task blocks | 5 task blocks | 4 task blocks | B0.0, B1.1-B1.3, B2.1-B2.5, B3.1-B3.4, and B4.1 are now repo-real; ensemble-aware report generation, interaction grounding, rollout hardening, and confidence-calibration layers remain open |
| Frontend/report surfaces | 2 probabilistic task blocks | 12 task blocks | 4 task blocks | Step 2 plus the UX/state-ownership contract are real, Step 3 has a truthful probabilistic ensemble browser plus read-only observed analytics cards, Step 4 now has an initial additive report-context consumer, and Step 5 now has a bounded report-scoped chat seam plus saved-report re-entry rather than fake ensemble/run claims |
| Integration/delivery | 3 task blocks | 4 task blocks | 5 task blocks | verify baseline, H0/H1, the state-ownership lock, and the H2 runner draft now exist, but rollout controls and release evidence remain thin |
| Documentation/PM control | 4 task blocks | improving this session | several updates still pending commit | packet now has H0, H1, audit, dashboard, execution log, gate ledger, and frontend UX contract control docs |

## 5. Evidence ledger links

- status audit: `docs/plans/2026-03-08-stochastic-probabilistic-status-audit.md`
- H0 contract baseline: `docs/plans/2026-03-08-stochastic-probabilistic-h0-contract-baseline.md`
- H2 ensemble storage contract: `docs/plans/2026-03-08-stochastic-probabilistic-h2-ensemble-storage-contract.md`
- run-metrics contract: `docs/plans/2026-03-08-stochastic-probabilistic-run-metrics-contract.md`
- aggregate-summary contract: `docs/plans/2026-03-08-stochastic-probabilistic-aggregate-summary-contract.md`
- scenario-clusters contract: `docs/plans/2026-03-08-stochastic-probabilistic-scenario-clusters-contract.md`
- sensitivity contract: `docs/plans/2026-03-08-stochastic-probabilistic-sensitivity-contract.md`
- report-context contract: `docs/plans/2026-03-08-stochastic-probabilistic-report-context-contract.md`
- gate-evidence ledger: `docs/plans/2026-03-08-stochastic-probabilistic-gate-evidence-ledger.md`
- execution log: `docs/plans/2026-03-08-stochastic-probabilistic-execution-log.md`

## 6. Current blockers

- no full Step 5 probabilistic interaction flow beyond the report-agent lane
- no ensemble-aware history or compare route, and Step 3 history support is still limited to the bounded saved probabilistic runtime seam rather than full compare/reload/re-entry coverage
- real Step 2 local prepare still depends on Zep/LLM prerequisites; the deterministic smoke fixture is QA evidence, not proof that live prepare is self-contained
- seven local-only non-fixture runtime/browser evidence passes now exist for the probabilistic rollout path: the March 9 Step 1 -> Step 5 pass that surfaced the race, the March 10 first-click Step 2 -> Step 3 rerun, the March 10 repo-owned operator pass on `ensemble 0004`, the later March 10 repo-owned operator pass on `ensemble 0005`, the earlier current-session repo-owned operator pass on `ensemble 0006`, the later same-session repo-owned operator pass on `ensemble 0007`, and the current March 10 repo-owned operator pass on `ensemble 0008`
- a bounded local operator runbook now exists, but fuller stuck-run/artifact-inspection guidance and the release-ops package are still incomplete
- no release-grade telemetry or gate evidence bundle
- no full report-body consumer for the probabilistic report context yet

## 7. Current ready work

- extend the bounded H2 handbook into fuller stuck-run/artifact-inspection guidance and broader repeatable non-fixture runtime evidence beyond the current seven local-only passes and the repo-owned operator recipe
- keep the Step 2 local prerequisite/runbook boundary explicit so operators know the difference between the live Zep/LLM path and the deterministic smoke fixture
- deepen the current Step 4 report-context consumer while keeping thin-sample and observational-only warnings explicit, but only after the H2 operator package no longer has unresolved live handoff risk
- extend the current Step 5 grounding slice beyond report-agent chat without implying unsupported ensemble/run/cluster semantics
- add ensemble/history compare, reload, and re-entry semantics beyond the current bounded Step 3 plus saved-report Step 4/Step 5 path
- H5 release-ops packaging on top of the now-live verify plus smoke baseline
- H3 aggregate-analytics packaging and provenance maintenance on top of the live `metrics.json`, `aggregate_summary.json`, `scenario_clusters.json`, observational `sensitivity.json`, and `probabilistic_report_context.json` contracts
