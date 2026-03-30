# Forecast Mode Primary And Scope-Aware Scenario Analysis Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the forecast workflow primary when selected, and finish the scenario-family plus sensitivity layer so Step 2 through Step 5 can operate on truthful ensemble, cluster, or run scope instead of treating forecast evidence as a bounded run-only overlay.

**Architecture:** Preserve the existing artifact ladder and repo-local evidence boundaries, but promote forecast mode into the main control plane when selected. Keep the stored analytics artifacts (`aggregate_summary.json`, `scenario_clusters.json`, `sensitivity.json`) as the canonical evidence sources, extend them where needed, and move all Step 4 and Step 5 consumers onto one explicit scope contract: `ensemble`, `cluster`, or `run`. Scenario families remain empirical, selected runs remain observed, and driver analysis remains observational only.

**Tech Stack:** Python 3.12, Flask, pytest, Vue 3, Vite, Node test runner, Playwright smoke, JSON artifact contracts under `backend/uploads/simulations/`.

---

## Audit Snapshot

Current repo state is materially better than the original north-star, but the forecasting workflow is still not first-class when selected:

1. Step 2 still defaults to legacy and auto-starts legacy prepare on mount, even when forecast prepare is available.
   - `frontend/src/components/Step2EnvSetup.vue:843`
   - `frontend/src/components/Step2EnvSetup.vue:1552`
   - `frontend/src/components/Step2EnvSetup.vue:1559`

2. Frontend scope ownership is still effectively `ensemble + run` only.
   - route normalization only accepts `ensembleId` and `runId`
   - `frontend/src/utils/probabilisticRuntime.js:663`
   - `frontend/src/utils/probabilisticRuntime.js:720`
   - `frontend/src/utils/probabilisticRuntime.js:1376`

3. Step 4 and the report-context panel still block on explicit run scope even though backend report-context generation already supports pure ensemble scope.
   - `frontend/src/components/ProbabilisticReportContext.vue:211`
   - `frontend/src/components/Step3Simulation.vue:1828`
   - `backend/app/services/probabilistic_report_context.py:91`
   - `backend/tests/unit/test_probabilistic_report_context.py:464`

4. Cluster artifacts exist, but `cluster_id` is not part of any route, report, or interaction request contract.
   - only prompt text references `cluster_id`
   - `frontend/src/utils/probabilisticRuntime.js:1546`

5. Scenario-family and sensitivity artifacts are usable for inspection, but not yet for scope-aware report or interaction flows.
   - `backend/app/services/scenario_clusterer.py:4`
   - `backend/app/services/sensitivity_analyzer.py:4`
   - `backend/app/services/probabilistic_report_context.py:131`
   - `backend/app/services/probabilistic_report_context.py:144`

6. Compare support is still prompt-only, not a scope-preserving contract.
   - `frontend/src/components/ProbabilisticReportContext.vue:316`
   - `frontend/src/utils/probabilisticRuntime.js:1525`

## Phase Decisions

### 1. Forecast mode becomes primary when selected, not a legacy-afterthought

- The UI term for the selected non-legacy path is `Forecast`.
- The repo keeps existing backend/env/artifact names such as `probabilistic_*` for compatibility in this phase.
- Step 2 must stop auto-running legacy prepare when forecast mode is available and selected.
- If a simulation already has complete forecast prepare artifacts, Step 2 must reopen in forecast mode automatically.
- If forecast mode is selected, Step 3 handoff, Step 4 generation, Step 5 routing, and history reopen logic must all preserve that forecast scope without requiring a manual return to the legacy path first.

### 2. One exact scope model must exist everywhere

Use this exact logical scope contract across backend APIs, report artifacts, route state, and report-agent requests:

```json
{
  "level": "ensemble | cluster | run",
  "simulation_id": "sim_xxx",
  "ensemble_id": "0001",
  "cluster_id": null,
  "run_id": null,
  "representative_run_id": null,
  "source": "route | saved_report | derived_membership"
}
```

Rules:

- `ensemble` scope requires `ensemble_id`, with `cluster_id=null`, `run_id=null`
- `cluster` scope requires `ensemble_id` plus `cluster_id`; `run_id` stays null unless the consumer explicitly pivots to a selected run
- `run` scope requires `ensemble_id` plus `run_id`; `cluster_id` may be included when cluster membership is known, but the scope still remains `run`
- `representative_run_id` is descriptive only; it does not silently change the selected scope
- every Step 4 and Step 5 scope must be serializable from route state and reconstructible from a saved report

### 3. No new top-level artifact is required for this phase

Do not create a brand-new `compare` artifact. Extend these existing contracts instead:

- `prepared_snapshot.json`
- `scenario_clusters.json`
- `sensitivity.json`
- `probabilistic_report_context.json`

This keeps the repo maximally finishable in one phase while preserving the existing artifact-first ladder.

### 4. Semantics stay explicit

- `aggregate_summary.json`: empirical
- `scenario_clusters.json`: empirical family grouping of observed run outcomes
- `selected_run`: observed
- `sensitivity.json`: observational co-variation only
- `driver_analysis` in report context: observational only
- no artifact in this phase may claim intervention effect, counterfactual effect, or causal driver attribution

## Target Contract After This Phase

### Step 2 Contract

When Forecast mode is selected:

- Step 2 prepares the forecast artifact set directly
- the main CTA is forecast-first, not legacy-first
- `prepared_artifact_summary` truthfully states the selected mode and artifact readiness
- the operator sees whether the prepared scope is ready for ensemble, cluster, and run downstream use

Compatibility:

- keep existing `probabilistic_mode` request/response fields
- optionally add additive aliases like `forecast_mode` only if needed for clarity
- do not rename persisted artifact filenames in this phase

### Step 3 Contract

Step 3 remains the stored-run execution surface, but it must become the source of scope selection:

- ensemble scope: analytics summary and family cards are usable without picking a run first
- cluster scope: an operator can focus one scenario family from the cluster artifact
- run scope: current selected run behavior remains
- Step 3 can launch Step 4 from ensemble, cluster, or run scope

### Step 4 Contract

Step 4 must treat forecast scope as a first-class input:

- ensemble-scoped report generation is valid
- cluster-scoped report generation is valid
- run-scoped report generation remains valid
- `ProbabilisticReportContext` must render for any of those scopes
- the forecast evidence panel becomes the primary scope/evidence header for forecast mode
- the legacy report body may remain below it in this phase

### Step 5 Contract

Only the report-agent lane is forecast-context-aware in this phase.

- Step 5 banner truth must reflect ensemble, cluster, or run scope accurately
- report-agent requests must carry `ensemble_id`, optional `cluster_id`, and optional `run_id`
- saved-report reopen and live route state must preserve scope
- compare suggestions must be scope-preserving structured options, not only free-text prompts

Interviews and surveys remain legacy-scoped in this phase.

## Scenario-Family Improvements Required

`scenario_clusters.json` is currently too thin for scope-aware reporting. Extend it so each family exposes:

- stable `cluster_id`
- `family_label`
- `family_summary`
- `prototype_run_id`
- `representative_run_ids`
- `member_run_ids`
- `observed_run_share`
- support metadata
- `distinguishing_metrics`
- `assumption_template_counts`
- `prototype_resolved_values`
- `prototype_top_topics`
- `family_signature`
  - concise empirical deltas vs ensemble baseline
  - no causal language
- `comparison_hints`
  - ids of sensible comparison families or runs

Implementation direction:

- keep deterministic clustering
- preserve medoid/prototype logic unless tests show a correctness issue
- enrich the feature space with currently available structured data that is already in-repo and durable:
  - numeric outcome metrics
  - binary/categorical outcome signals when present
  - assumption-template indicators from run manifests
  - top-topic markers only when already extracted and stable

Out of scope:

- natural-language causal family narratives
- cross-ensemble family normalization
- human-authored taxonomy of scenario families

## Driver-Analysis Improvements Required

`sensitivity.json` must become more usable for report and interaction consumers without implying causality.

Add or tighten:

- explicit `ranking_basis`
- stable per-driver support metadata
- scope-friendly `driver_summary`
- per-driver top metric impacts with support and warnings
- cluster alignment hints when a driver clearly differentiates one empirical family from the ensemble
- selected-scope highlights derivable without re-running analytics

Implementation direction:

- keep observational semantics explicit in the artifact and UI
- stop mixing incomparable effect signals silently
- choose one deterministic ranking rule and persist it
- preserve current numeric-band grouping unless tests prove it misleading

Recommended ranking rule for this phase:

- rank by support-aware standardized effect across prepared outcome metrics
- persist raw group means and raw effect sizes alongside the rank basis
- never label the result as “cause”, “driver of”, or “impact of” without the word `observational`

Out of scope:

- intervention-effect estimation
- causal discovery
- synthetic controls
- uplift modeling

## Consumer Contract Changes

### Report Context (`probabilistic_report_context.json`)

Bump the report-context schema to `v2` because the scope model changes materially.

Add or extend:

- `scope`
- `selected_cluster`
- `selected_run`
- `scope_catalog`
  - `ensemble`
  - `clusters`
  - `runs`
  - `compare_options`
- `driver_analysis`
  - `semantics: "observational"`
  - `top_drivers`
  - `selected_scope_highlights`
- `scenario_families`
  - now suitable for rendering or selecting as cluster scope, not just listing

Rules:

- `selected_cluster` exists for cluster scope, and also for run scope when cluster membership is known
- `selected_run` exists only for run scope
- `sensitivity_overview` remains lightweight, but `driver_analysis` provides enough structured detail for Step 4/5 consumers
- `compare_options` must carry explicit left/right scope descriptors instead of only text prompts

### Report Agent Prompt Contract

Update prompt-safe scope packaging so it can include:

- `scope`
- `selected_cluster`
- `selected_run`
- `driver_analysis`
- `compare_options`

The prompt formatter must stay bounded. It should summarize:

- the exact current scope
- upstream grounding status
- support/warnings
- top outcomes
- selected family or run facts
- observational driver analysis

### Frontend Route And State Contract

Routes and state helpers must accept:

- `mode`
- `ensembleId`
- `clusterId`
- `runId`

Rules:

- `clusterId` is additive and optional
- `mode=probabilistic` remains supported for compatibility
- if a forecast-scoped report record is loaded, route state is derived from the saved report context first
- UI fetch plans must work for:
  - ensemble scope
  - cluster scope
  - run scope

## Compatibility Plan

Preserve:

- current artifact filenames
- current env flags
- existing `ensemble_id` plus `run_id` APIs
- current smoke fixtures as the starting point

Additive changes only where possible:

- `cluster_id` becomes optional on report/chat routes
- route/query parsing accepts `clusterId`
- report-context readers accept older `v1` artifacts and degrade gracefully

Version bumps required if artifact meaning changes materially:

- `probabilistic_report_context.json` -> `v2`
- `scenario_clusters.json` -> bump only if the payload meaning changes beyond additive fields
- `sensitivity.json` -> bump only if ranking semantics change, which is likely

## Task 1: Make Forecast Mode Primary In Step 2

**Files:**
- Modify: `frontend/src/components/Step2EnvSetup.vue`
- Modify: `frontend/src/utils/probabilisticRuntime.js`
- Modify: `backend/app/api/simulation.py`
- Modify: `backend/app/services/simulation_manager.py`
- Test: `frontend/tests/unit/probabilisticRuntime.test.mjs`
- Test: `backend/tests/unit/test_probabilistic_prepare.py`

**Step 1: Write the failing tests**

- Assert Step 2 does not auto-run legacy prepare when forecast mode is available and selected.
- Assert existing forecast artifacts reopen Step 2 in forecast mode automatically.
- Assert prepare summary truth stays explicit when forecast artifacts are partial versus complete.

**Step 2: Run the red tests**

Run: `cd /Users/danielbloom/Desktop/MiroFishES/backend && python3 -m pytest tests/unit/test_probabilistic_prepare.py -q`

Run: `node --test /Users/danielbloom/Desktop/MiroFishES/frontend/tests/unit/probabilisticRuntime.test.mjs`

**Step 3: Implement the minimum control-plane changes**

- Stop legacy auto-prepare on mount when forecast mode is selected.
- Make Step 2 selection state the source of truth for downstream forecast routing.
- Keep backward-compatible request payloads.

**Step 4: Re-run the focused tests**

Run the same commands from Step 2.

## Task 2: Add One Shared Scope Contract Across Ensemble, Cluster, And Run

**Files:**
- Modify: `backend/app/services/probabilistic_report_context.py`
- Modify: `backend/app/api/report.py`
- Modify: `frontend/src/utils/probabilisticRuntime.js`
- Modify: `frontend/src/views/SimulationRunView.vue`
- Modify: `frontend/src/views/ReportView.vue`
- Modify: `frontend/src/views/InteractionView.vue`
- Test: `backend/tests/unit/test_probabilistic_report_context.py`
- Test: `backend/tests/unit/test_probabilistic_report_api.py`
- Test: `frontend/tests/unit/probabilisticRuntime.test.mjs`

**Step 1: Write the failing tests**

- Assert report context can be built for ensemble, cluster, and run scope.
- Assert route parsing and request builders preserve `clusterId`.
- Assert Step 4/5 fetch plans no longer require `runId` for every forecast surface.

**Step 2: Run the red tests**

Run: `cd /Users/danielbloom/Desktop/MiroFishES/backend && python3 -m pytest tests/unit/test_probabilistic_report_context.py tests/unit/test_probabilistic_report_api.py -q`

Run: `node --test /Users/danielbloom/Desktop/MiroFishES/frontend/tests/unit/probabilisticRuntime.test.mjs`

**Step 3: Implement the scope model**

- Extend backend request handling with optional `cluster_id`.
- Extend frontend route/query normalization and report-agent request builders.
- Make report-context and UI state treat ensemble scope as fully valid.

**Step 4: Re-run the focused tests**

Run the same commands from Step 2.

## Task 3: Upgrade Scenario-Family Artifact Semantics

**Files:**
- Modify: `backend/app/services/scenario_clusterer.py`
- Modify: `backend/app/services/probabilistic_report_context.py`
- Test: `backend/tests/unit/test_scenario_clusterer.py`
- Test: `backend/tests/unit/test_probabilistic_report_context.py`

**Step 1: Write the failing tests**

- Assert each family carries stable labels, summaries, support, representative runs, and comparison hints.
- Assert cluster scope in report context exposes `selected_cluster`.
- Assert family signatures stay empirical and do not imply causality.

**Step 2: Run the red tests**

Run: `cd /Users/danielbloom/Desktop/MiroFishES/backend && python3 -m pytest tests/unit/test_scenario_clusterer.py tests/unit/test_probabilistic_report_context.py -q`

**Step 3: Implement the minimal artifact upgrades**

- Enrich cluster payloads with operator-usable family metadata.
- Preserve deterministic ordering and stable ids.
- Thread the selected family into report context.

**Step 4: Re-run the focused tests**

Run the same command from Step 2.

## Task 4: Upgrade Observational Driver Analysis

**Files:**
- Modify: `backend/app/services/sensitivity_analyzer.py`
- Modify: `backend/app/services/probabilistic_report_context.py`
- Test: `backend/tests/unit/test_sensitivity_analyzer.py`
- Test: `backend/tests/unit/test_probabilistic_report_context.py`

**Step 1: Write the failing tests**

- Assert `sensitivity.json` exposes one explicit ranking basis.
- Assert per-driver support and warnings survive into report context.
- Assert cluster-aware or selected-scope driver highlights are derivable without causal language.

**Step 2: Run the red tests**

Run: `cd /Users/danielbloom/Desktop/MiroFishES/backend && python3 -m pytest tests/unit/test_sensitivity_analyzer.py tests/unit/test_probabilistic_report_context.py -q`

**Step 3: Implement the minimal driver-analysis upgrades**

- Persist ranking semantics directly in the artifact.
- Add selected-scope driver summaries to report context.
- Keep all driver copy observational.

**Step 4: Re-run the focused tests**

Run the same command from Step 2.

## Task 5: Wire Scope-Aware Step 3 Through Step 5 Consumers

**Files:**
- Modify: `frontend/src/components/Step3Simulation.vue`
- Modify: `frontend/src/components/ProbabilisticReportContext.vue`
- Modify: `frontend/src/components/Step4Report.vue`
- Modify: `frontend/src/components/Step5Interaction.vue`
- Modify: `frontend/src/utils/probabilisticRuntime.js`
- Modify: `backend/app/services/report_agent.py`
- Test: `frontend/tests/unit/probabilisticRuntime.test.mjs`
- Test: `backend/tests/unit/test_probabilistic_report_api.py`
- Test: `tests/smoke/probabilistic-runtime.spec.mjs`

**Step 1: Write the failing tests**

- Assert Step 3 can route to Step 4 with ensemble, cluster, or run scope.
- Assert Step 4 shows the forecast scope as a primary context header.
- Assert Step 5 banner and chat request reflect ensemble, cluster, or run scope truthfully.
- Assert compare options are structured scope choices, not only text prompts.

**Step 2: Run the red tests**

Run: `node --test /Users/danielbloom/Desktop/MiroFishES/frontend/tests/unit/probabilisticRuntime.test.mjs`

Run: `cd /Users/danielbloom/Desktop/MiroFishES/backend && python3 -m pytest tests/unit/test_probabilistic_report_api.py -q`

**Step 3: Implement the minimal UI and prompt wiring**

- Add scope-preserving navigation and compare options.
- Make Step 4 and Step 5 read `selected_cluster` and `driver_analysis`.
- Keep interviews and surveys legacy-scoped.

**Step 4: Re-run the focused tests**

Run the same commands from Step 2.

**Step 5: Run smoke because operator/report surfaces changed**

Run: `cd /Users/danielbloom/Desktop/MiroFishES && npm run verify:smoke`

## Task 6: Update Docs And Truth Boundaries

**Files:**
- Modify: `README.md`
- Modify: `docs/local-probabilistic-operator-runbook.md`
- Modify: `docs/plans/2026-03-29-forecasting-integration-hardening-wave.md`

**Step 1: Update the docs to match the new contract**

- replace “legacy baseline first” operator guidance
- document the exact ensemble/cluster/run scope model
- restate observational versus causal boundaries explicitly

**Step 2: Verify docs match code contracts**

Run a quick grep-based check for stale language:

Run: `cd /Users/danielbloom/Desktop/MiroFishES && rg -n "legacy baseline prepare first|ensemble and run identifiers from Step 3|bounded compare prompts" README.md docs/local-probabilistic-operator-runbook.md docs/plans/2026-03-29-forecasting-integration-hardening-wave.md frontend/src/components frontend/src/utils/probabilisticRuntime.js`

## Acceptance Criteria

This phase is complete only when all of the following are true:

1. Selecting Forecast mode in Step 2 no longer forces a legacy-first prepare sequence.
2. Step 2, Step 3, Step 4, Step 5, and saved-report reopen flows preserve one explicit forecast scope.
3. `probabilistic_report_context.json` supports `ensemble`, `cluster`, and `run` scope truthfully.
4. Scenario families are usable as first-class scope, not only as descriptive cards or prompt text.
5. Driver analysis is structured enough for report and interaction flows, but remains explicitly observational.
6. No UI or report copy implies causal attribution, calibrated certainty, or unsupported compare power.
7. Existing ensemble plus run flows continue to work.
8. Docs, smoke, and unit tests all agree on the same scope contract.

## Exact Verification Commands

Run in this order:

1. `cd /Users/danielbloom/Desktop/MiroFishES/backend && python3 -m pytest tests/unit/test_probabilistic_prepare.py tests/unit/test_scenario_clusterer.py tests/unit/test_sensitivity_analyzer.py tests/unit/test_probabilistic_report_context.py tests/unit/test_probabilistic_report_api.py -q`
2. `node --test /Users/danielbloom/Desktop/MiroFishES/frontend/tests/unit/probabilisticRuntime.test.mjs`
3. `cd /Users/danielbloom/Desktop/MiroFishES && npm run verify`
4. `cd /Users/danielbloom/Desktop/MiroFishES && npm run verify:smoke`

## Out Of Scope For This Phase

Even after this phase, the repo still must not claim:

- causal driver attribution
- intervention-effect estimates
- full compare-workspace maturity beyond structured scope-aware compare options
- forecast calibration beyond explicit backtested artifacts already supported
- forecast-aware interviews or surveys
- release-grade readiness

## Expected Outcome

After this phase, later work can truthfully assume:

- forecast mode is a first-class control-plane path when selected
- report and interaction consumers can operate on ensemble, cluster, or run scope
- scenario-family and driver-analysis artifacts are durable enough for scope-aware reporting
- the repo still distinguishes empirical, observed, and observational evidence clearly
