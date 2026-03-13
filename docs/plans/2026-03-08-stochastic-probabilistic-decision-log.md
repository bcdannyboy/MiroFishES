# Stochastic Probabilistic Simulation Decision Log

**Date:** 2026-03-10

## Approved decisions

### D-001

Decision:

- use a sidecar rollout, not a platform rewrite

Reason:

- current graph, runtime, and report pipeline are strong enough to extend

### D-002

Decision:

- keep world construction deterministic by default

Reason:

- provenance and user trust depend on stable prepared snapshots

### D-003

Decision:

- add uncertainty at the config, runtime, and aggregation layers before graph-confidence work

Reason:

- those layers unlock end-user value first

### D-004

Decision:

- treat calibration as a later phase

Reason:

- benchmark data and recurring targets are not yet part of the MVP

### D-005

Decision:

- do not allow report surfaces to imply calibrated or authoritative probabilities without backing artifacts

Reason:

- avoids pseudo-quantification and false trust

### D-006

Decision:

- treat the planning packet as the approved design baseline, but treat the codebase as the source of truth for what is actually implemented

Reason:

- current repo state remains legacy single-run and must override stale execution assumptions

### D-007

Decision:

- make B0 and B1 the first execution wave, with legacy-preserving verification and feature-flag scaffolding in scope from the start

Reason:

- the probabilistic program has no safe implementation path until tests, schema models, and prepare artifacts exist

### D-008

Decision:

- exclude Phase 5 calibration and graph-confidence work from MVP readiness scoring and map it to post-MVP handoff package H6

Reason:

- the current repository does not implement Phase 5 capabilities and they are intentionally deferred

### D-009

Decision:

- when probabilistic prepare is enabled, Step 2 must preserve the automatic legacy prepare path first and only expose probabilistic re-prepare explicitly after the baseline is ready

Reason:

- preserving the legacy baseline avoids a readiness regression, while the explicit re-prepare path still prevents unsupported probabilistic runtime claims

### D-010

Decision:

- `/api/simulation/prepare/status` must carry probabilistic intent so legacy-ready artifacts are not mistaken for probabilistic readiness

Reason:

- the prepare endpoint and the status endpoint must enforce the same readiness contract or the frontend can regress after reloads or task lookup misses

### D-011

Decision:

- treat `B2.2` ensemble storage and run directory semantics as the next highest-leverage ready implementation slice; do not claim `B2.3` is independently ready until `B2.2` is real in code

Reason:

- the runtime/task registers make `B2.3` explicitly dependent on `B2.2`, and fresh audit evidence still shows runtime, report, and history remain simulation-scoped

### D-012

Decision:

- treat near-term frontend QA work as a Step 2 legacy-plus-probabilistic smoke baseline, not as closure of the full `F5.1` Step 2 through Step 5 matrix

Reason:

- the current task register still gates full `F5.1` on later probabilistic Step 3 through Step 5 surfaces that do not exist yet

### D-013

Decision:

- keep the first ensemble APIs simulation-scoped: `/api/simulation/<simulation_id>/ensembles/...`

Reason:

- the implemented `ensemble_id` and `run_id` are storage identities scoped under one parent simulation, so exposing them without `simulation_id` would create an ambiguous public contract before a deliberate global-ID migration exists

### D-014

Decision:

- gate storage-only ensemble creation and inspection behind `PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED`, with `ENSEMBLE_RUNTIME_ENABLED` retained only as a compatibility alias, separate from `PROBABILISTIC_PREPARE_ENABLED`

Reason:

- prepare and storage are now independent rollout slices; keeping distinct flags preserves the legacy path and allows runtime/report work to remain off until their contracts and evidence exist

### D-015

Decision:

- keep public runtime launch compatibility on the legacy `/api/simulation/start` path for now, while allowing the refactored runner to accept internal `(simulation_id, ensemble_id, run_id)` context for one stored run

Reason:

- the B2.3 runner seam is now real and verified, but public ensemble launch/status APIs and frontend runtime UX do not exist yet, so exposing ensemble runtime support beyond the legacy path would overclaim readiness

### D-016

Decision:

- treat the explicit runtime-script CLI/root/seed seam as implemented, but keep runtime determinism language explicitly best-effort in code, tests, and PM docs

Reason:

- the scripts now accept `--run-id`, `--seed`, and `--run-dir`, honor run-local roots, and use explicit RNG objects for their scheduling helpers, but downstream OASIS/LLM behavior still prevents an honest fully deterministic runtime claim

### D-017

Decision:

- implement the first ensemble-level `start` route as an immediate batch launch of the requested runs, while leaving queued orchestration and richer runtime-detail surfaces for the remaining B2.5 work

Reason:

- the repo already has verified run-scoped launch primitives and member-run lifecycle routes, so exposing a batch-launch wrapper materially improves readiness now without pretending a queue/scheduler contract already exists

### D-018

Decision:

- expose runtime-backed run detail plus raw run `actions` and `timeline` routes under the ensemble namespace now, but keep them positioned as inspection surfaces rather than aggregate probabilistic summaries

Reason:

- the backend already has truthful run-scoped state and raw log readers, and surfacing them unblocks Step 3/H2 integration work without overstating analytics capability before B3 metrics and aggregate artifacts exist

### D-019

Decision:

- probabilistic Step 3 must require the explicit Step 2 handoff (`mode`, `ensembleId`, `runId`) and must hard-error when those identifiers are missing instead of silently guessing a latest stored run

Reason:

- the Step 2 runtime handoff is now real in the repo, and silently selecting another stored run would blur provenance, risk monitoring the wrong run shell, and overstate operator certainty about what Step 3 is actually showing

### D-020

Decision:

- implement B3.1 against the locked B0.2 count-metric registry only, keep `top_topics` as observational support metadata rather than a forecast metric, and emit `metrics.json` automatically only for stored ensemble runs

Reason:

- the older planning packet still contains broader example metrics, but the live codebase only locks three count metrics; constraining B3.1 to that explicit registry preserves truthful semantics, avoids inventing unsupported probabilistic claims, and keeps the legacy single-run filesystem contract unchanged

### D-020A

Decision:

- persist the launched `platform_mode` in run-scoped state, use it when judging run-metrics completeness, keep metrics-persistence failures non-fatal to terminal runtime truth, and derive `extracted_at` from persisted run artifacts instead of wall-clock time whenever possible

Reason:

- analytics must not downgrade a successfully completed run to failed, single-platform member runs must not be mislabeled as partial just because sibling platform logs were never expected, and repeated extraction over unchanged artifacts should stay deterministic enough for diff-based verification

### D-021

Decision:

- implement B3.2 as an empirical aggregate-summary layer over persisted run metrics, expose it through the planned `/summary` route, and surface thin-sample or degraded-run warnings directly in the artifact instead of hiding them behind optimistic summary language

Reason:

- the repo now has real run-level metrics, so aggregate summaries materially improve readiness; however clustering, sensitivity, and calibration are still absent, so the summary must stay explicit about weak evidence and avoid implying a fuller analytics stack than the code actually provides

### D-022

Decision:

- implement B3.3 as a deterministic clustering layer over complete run metrics only, normalize cluster mass against total prepared runs rather than only clusterable survivors, and downgrade missing/invalid/degraded `metrics.json` artifacts to explicit warnings instead of treating them as full clustering evidence

Reason:

- scenario families are now useful enough to persist, but the current evidence surface is still thin and uneven across runs; excluding degraded artifacts from membership and making coverage loss visible prevents the `/clusters` route and `scenario_clusters.json` from overstating empirical support

### D-023

Decision:

- implement B3.4 as an observational sensitivity layer over stored `resolved_values` plus complete `metrics.json`, expose it through `/sensitivity`, and keep `observational_only` plus thin-sample warnings in the artifact instead of pretending the repo already has perturbation semantics or calibrated driver attribution

Reason:

- the repo now has enough stored run evidence to rank drivers truthfully, but it still does not have controlled perturbation orchestration or calibration support; locking the boundary now lets H3, frontend consumers, and report work proceed without overstating certainty

### D-024

Decision:

- keep the legacy report body and `report_id` route intact, but make saved report metadata the source of truth for probabilistic Step 4 scope by persisting `ensemble_id`, `run_id`, and an embedded `probabilistic_context` sidecar when probabilistic report generation is requested

Reason:

- the repo now has enough aggregate evidence to support an additive Step 4 consumer, but not enough to justify replacing the legacy report renderer; persisting scope in report metadata keeps reloads and re-entry honest, avoids route-query drift, and lets Step 4 consume empirical/observational context without overclaiming ensemble-aware narrative generation

### D-025

Decision:

- probabilistic Step 3 stored-run launches must default graph-memory updates off and `close_environment_on_complete=true`

Reason:

- the current probabilistic Step 3 slice is an operator/runtime surface, not a graph-writeback or post-run interview session; leaving graph-memory updates on made the happy-path smoke depend on external graph state, and leaving command-wait mode on allowed a run to look completed in runtime state while storage still said `running`

### D-026

Decision:

- ensemble status aggregation may fall back to persisted terminal storage states (`prepared`, `completed`, `failed`, `stopped`) when runtime state is unavailable, but it must not treat storage-only `running` as proof of an active process

Reason:

- the runtime/status APIs need to preserve truthful terminal state across reloads or missing in-memory state, while still avoiding false claims that a process is actively running just because a manifest was not cleaned up

### D-027

Decision:

- keep retry on the existing member-run `start` path after cleanup policy is applied, and use `rerun` only to create a new child run with a fresh `run_id` plus preserved parent/source lineage

Reason:

- the runtime shell now has enough lifecycle support to distinguish retry from rerun honestly; reusing `start` for retry preserves compatibility, while a separate `rerun` operation prevents prior run evidence from being overwritten

### D-028

Decision:

- treat the repo-owned Playwright smoke matrix as fixture-backed baseline evidence for the bounded Step 2 through Step 5 probabilistic path, not as release-grade or non-fixture runtime proof

Reason:

- the new browser harness is durable enough to gate regressions in the current code path, but it still runs on deterministic synthetic fixtures and cannot honestly stand in for real-project runtime, operator, or release evidence

### D-029

Decision:

- ground only the Step 5 report-agent lane on saved report scope for now: send optional `report_id`, load the exact saved report, and inject saved `probabilistic_context`, while keeping interviews and surveys explicitly legacy-scoped

Reason:

- Step 4 already uses saved report metadata as the durable probabilistic truth carrier, so reusing that exact `report_id` for Step 5 closes a real scoping bug without inventing unsupported run-vs-cluster-vs-ensemble semantics or weakening the legacy interaction path

### D-030

Decision:

- allow Step 5 history re-entry only through saved reports on the existing `/interaction/:reportId` route, while keeping Step 3 live-only and keeping compare outside MVP

Reason:

- `report_id` is already a durable, reload-safe identity for the current Step 4 and Step 5 surfaces, but Step 3 still depends on live runtime operator handoff and the repo still has no ensemble-history row model or compare contract

### D-031

Decision:

- refuse ensemble cleanup requests for runs that still have active runtime state instead of silently resetting their storage artifacts back to `prepared`

Reason:

- cleanup is an operator recovery action, not a force-delete primitive; allowing it to wipe files for `starting`/`running`/`stopping`/`paused` runs created a real lifecycle-consistency risk between runtime truth and persisted storage truth

### D-032

Decision:

- treat stored `max_concurrency` as a real ensemble batch-start admission ceiling: use stable `run_id` order, leave overflow members `prepared`, and return explicit `started_run_ids`, `deferred_run_ids`, and active-run context instead of claiming every requested run launched

Reason:

- the earlier batch-start contract could overclaim runtime progress and rejected mixed active requests instead of reporting actual capacity; explicit active/start/defer semantics keep Step 3 and operator surfaces honest without breaking the legacy single-run path

### D-033

Decision:

- keep the collapsed history deck overview-only: require an explicit expand/collapse control before browsing older saved reports, and keep only the newest visible card interactive while the stack is collapsed

Reason:

- reused local workspaces can accumulate many saved reports, and overlapping clickable cards caused real pointer-interception failures in the Step 5 history replay smoke; explicit expansion preserves the stacked visual treatment without allowing buried cards to masquerade as safe click targets

### D-034

Decision:

- treat probabilistic readiness as a full-sidecar invariant: `simulation_config.base.json`, `uncertainty_spec.json`, `outcome_spec.json`, and `prepared_snapshot.json` must all exist before Step 2 may hand off to Step 3 or the ensemble-create API may proceed

Reason:

- the March 9 live operator pass showed that treating any one sidecar as sufficient could overclaim readiness and produce a real Step 2 -> Step 3 handoff race; explicit missing-artifact reporting keeps the operator path honest and prevents partial prepare state from masquerading as probabilistic-ready

### D-035

Decision:

- prefer `backend/.venv/bin/python` for repo-root backend verification and local smoke backend launches whenever that interpreter exists, and fall back to ambient `python3` only when no repo-local interpreter is available

Reason:

- the March 10 verification rerun showed that ambient `python3` could resolve to a different pytest environment than the backend project expects, which makes root verification results depend on host-machine accidents instead of the repo's intended local runtime

### D-036

Decision:

- make the Step 3 operator surface explicit: same-run `/start` uses launch/retry wording, `cleanup` is its own recovery action, and `rerun` is reserved for child-run creation with a new `run_id`

Reason:

- the backend semantics were already real, but the old Step 3 wording blurred retry and rerun and hid cleanup behind backend-only knowledge; explicit UI labels and guidance are required if operators are expected to use the recovery surface honestly

### D-037

Decision:

- treat the deterministic Step 3 smoke fixture as prepared-shell coverage, not as retry-state coverage, and move same-run retry plus cleanup/rerun evidence into a separate local-only mutating operator path

Reason:

- the fresh smoke rerun showed that the seeded Step 3 fixture shell is a prepared stored run, so forcing retry wording into that fixture would overclaim what the fixture proves; separating fixture-backed prepared-shell coverage from local-only live recovery coverage keeps the evidence classes honest

### D-038

Decision:

- keep the repo-owned local operator path opt-in and local-only: require `PLAYWRIGHT_LIVE_ALLOW_MUTATION=true`, keep it outside `npm run verify`, and persist its evidence under `output/playwright/live-operator/`

Reason:

- the new operator pass materially improves repeatability and PM truth, but it mutates a live local simulation family and therefore cannot be treated as safe default verification or as release-grade evidence

### D-039

Decision:

- document live Step 2 local readiness as explicitly bounded by Zep plus LLM prerequisites, and treat the deterministic smoke fixture as separate fixture-backed QA evidence rather than proof that the live prepare path is self-contained

Reason:

- `README.md`, `backend/app/services/simulation_manager.py`, and `backend/app/services/probabilistic_smoke_fixture.py` now make that boundary clear: the real prepare path still depends on external graph/model services, while the smoke fixture exists specifically to provide deterministic local QA without those dependencies

### D-040

Decision:

- treat Step 4 and Step 5 generated-content rendering as escape-first limited markdown only; raw HTML from report, chat, interview, or survey content must never execute in the browser

Reason:

- the current probabilistic report and interaction seams render generated text into the frontend, and allowing raw HTML there would create a real safety and truthfulness risk; the shared escape-first renderer preserves the existing bounded markdown affordances without treating generated content as trusted markup

### D-041

Decision:

- keep the March 9 report-context planning docs as historical implementation records, but move current execution guidance to the March 8 control packet plus a new March 10 hybrid truthful-local hardening wave doc

Reason:

- the original report-context plans were useful to land the first Step 4 additive consumer, but the live repo truth has now moved on to saved-report replay boundaries, Step 2 handoff gating, Step 4/Step 5 rendering safety, and current-session local-only operator evidence; leaving the old plans positioned as live guidance would create PM drift

### D-042

Decision:

- do not claim 100% local readiness while Step 3 history/compare/re-entry and broader Step 5 grounding remain open, even if the current local-only operator recipe continues to pass

Reason:

- the fresh March 10 verification evidence proves the bounded local path can work, but it does not cover the still-missing history/re-entry and grounded interaction surfaces; claiming full readiness before those gaps close would overstate what the repository actually supports

### D-043

Decision:

- keep explicit probabilistic report generate/status/chat behavior exact-scope and rollout-gated: explicit probabilistic requests must resolve by `ensemble_id` plus `run_id` or explicit `report_id`, while unscoped legacy report requests remain latest-by-simulation

Reason:

- the current Step 4 and Step 5 bounded probabilistic surfaces now depend on saved report scope being truthful and deterministic; silently drifting to a different latest report for the same simulation would break reopen/replay trust while widening the rollout surface beyond what the repo can honestly support

### D-044

Decision:

- treat `runner_status=idle` plus terminal stored status as the stored-shell truth in Step 3; specifically, idle-plus-completed shells stay completed/retry-capable and must not auto-launch during deterministic smoke or reload

Reason:

- the March 10 deterministic smoke regression showed that privileging idle runtime state over persisted terminal storage state made Step 3 relaunch a completed shell and misstate the operator surface; the local product truth is the stored shell plus its persisted lifecycle unless a non-idle runtime state exists

### D-045

Decision:

- allow History to reopen the bounded Step 3 probabilistic stored-run shell when the repo has durable `ensemble_id` plus `run_id` evidence for the latest probabilistic runtime, but keep history simulation/report centric and keep compare outside MVP

Reason:

- the current Step 3 route already supports truthful reload when those identifiers are present, and the repo now has two durable sources for that scope: exact saved probabilistic reports and the newest stored ensemble/run shell. Reusing that bounded seam closes a real local-operator gap without inventing unsupported ensemble-history rows, compare semantics, or broader replay claims the repository still cannot honestly support

### D-046

Decision:

- treat bounded local probabilistic enablement as explicit opt-in documentation, not tribal knowledge: `README.md`, `.env.example`, and the local operator runbook must surface the default-false rollout flags, the capability check path, the live-operator simulation override, and the artifact/log inspection boundary

Reason:

- the current local runtime path is now strong enough to verify, but a fresh operator can still fail before Step 2 simply because the flags are off by default and the live operator harness otherwise falls back to one repo-local simulation family. Those are product truths, not incidental implementation details, so the user path must state them directly if the repo is going to claim truthful local operator support

## Open questions

- OQ-001: should ensemble comparison get a dedicated frontend route or remain embedded in Step 4 history flows?
- OQ-002: what minimum run count is acceptable for showing probability bands to users?
- OQ-003: what exact initial metric catalog should ship in MVP?
- OQ-004: what benchmark corpus will be used when calibration begins?
