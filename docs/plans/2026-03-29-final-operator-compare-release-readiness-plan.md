# Final Operator Compare Release-Readiness Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Finish the compare, operator, and evidence product surfaces so the repo reaches a truthful, local release-style state that is ready for a final audit.

**Architecture:** Keep `probabilistic_report_context.json` as the authoritative Step 4 and Step 5 evidence contract. Add one dedicated Step 4 compare workspace over bounded, inspectable compare snapshots, propagate explicit scope and compare handoff into the Step 5 report-agent lane, and close the remaining docs and verification drift. Do not invent production-grade claims, cross-simulation compare, or broader calibration semantics that the repo cannot prove.

**Tech Stack:** Python 3.12, Flask, pytest, Vue 3, Vite, Playwright, JSON artifact contracts under `backend/uploads/simulations/`.

---

## Audit Summary

The forecasting-control-plane waves are now functionally broad enough that the remaining work is product and contract hardening rather than new forecasting theory.

What exists today:

- Step 3 is the operator shell for a stored probabilistic run and already owns the initial Step 4 scope choice across `ensemble`, `cluster`, and `run`.
- Step 4 consumes `probabilistic_report_context.json` with explicit scope, upstream grounding, scenario-family evidence, observational driver analysis, and bounded compare starter prompts.
- Step 5 report-agent chat can already use saved or route-scoped `ensemble_id`, optional `cluster_id`, and optional `run_id`.
- Fixture smoke verification covers the bounded Step 2 through Step 5 shell, and a local-only live operator spec exercises Step 2 handoff plus Step 3 stop, retry, cleanup, and child rerun.

What is still missing or drifting:

- There is still no dedicated compare surface. Compare exists only as chips in Step 4 and starter prompts in Step 5.
- Step 5 still has no manual report-agent scope switcher; it inherits scope but does not let the operator deliberately move between `ensemble`, `cluster`, and `run` inside the report-agent lane.
- The current live operator spec stops at Step 3 and does not prove Step 4 report scope, Step 5 scope, or compare behavior against a real local simulation family.
- README, the local runbook, and the hardening-wave status note still describe compare and Step 5 scope control as deferred seams.
- Current verification is strong for bounded surfaces, but it is not yet packaged as a final-audit-ready operator/report/compare matrix.

## Phase Decisions

### 1. Dedicated compare should live inside Step 4, not as a new global route

This phase should add a dedicated compare workspace inside the Step 4 probabilistic evidence surface rather than a brand-new top-level compare page.

Why:

- the report context artifact already contains the scope and analytics substrate
- Step 4 is already where operators inspect evidence before asking Step 5 questions
- a new route tree would create extra persistence and history work with little product gain for this final phase

Decision:

- build one explicit `Compare Evidence` workspace inside Step 4
- keep Step 5 as the conversational follow-through surface, not the primary compare UI

### 2. Keep one persisted primary scope and one session-local compare handoff

The repo should distinguish three related but different concepts:

- `primary_scope`: the saved Step 4 and report scope, one of `ensemble | cluster | run`
- `chat_scope`: the Step 5 report-agent scope, mutable within the current session but defaulting to `primary_scope`
- `compare_selection`: an optional session-local compare choice that references one bounded compare pair

Decision:

- `primary_scope` remains the only scope persisted into the saved report context and history replay contract
- `compare_selection` is session-local and should not become report identity
- Step 4 can hand off the chosen compare pair to Step 5 through route/session state, but history replay only has to restore the saved primary scope

This is the highest-completion path that stays understandable and avoids overloading the saved-report model.

### 3. Compare remains bounded to one report context and one ensemble

This phase should not add cross-simulation compare, arbitrary report-vs-report compare, or free-form deep compare routing.

Decision:

- compare only within the current report context
- compare only scopes that share the same `simulation_id` and `ensemble_id`
- compare only scopes offered by bounded compare metadata or the existing scope catalog

### 4. Comparisons remain empirical or observational, not causal

This phase must not create stronger semantics than the repo can support.

Decision:

- ensemble and scenario-family comparisons remain empirical
- run comparisons remain observed
- driver comparisons remain observational
- compare UI must not imply causal attribution, intervention certainty, or calibrated forecast superiority unless a named metric already carries ready calibration provenance

### 5. “Release-style, final-assessment-ready” is local and audit-oriented, not production-grade

This phase should make the repo feel finished enough for a rigorous final audit, but it still must not claim:

- self-contained live prepare without LLM/Zep prerequisites
- production-grade rollout evidence
- globally calibrated forecasting
- scope-aware interviews or surveys

## Exact Product Contract For This Phase

### Primary operator workflow

1. Step 2 prepares forecast artifacts and stored run shells.
2. Step 3 launches, stops, retries, cleans, or child-reruns one stored run and sets the initial `primary_scope` for Step 4.
3. Step 4 shows one report body plus a probabilistic evidence surface for the saved `primary_scope`.
4. Step 4 also exposes one dedicated compare workspace using bounded compare-ready metadata from the same report context.
5. Step 5 report-agent chat inherits the saved `primary_scope`, allows explicit manual switching across available scopes, and can optionally receive the currently selected compare pair.

### Dedicated compare workflow that should exist now

The compare workflow should be:

- entered from Step 4, inside the probabilistic evidence surface
- bounded to one chosen compare pair at a time
- based on inspectable scope snapshots, not free-form LLM synthesis
- able to hand off a chosen compare pair into Step 5 report-agent chat

The compare workspace should show, for both left and right scopes:

- exact scope identity: `ensemble_id`, optional `cluster_id`, optional `run_id`
- scope level: `ensemble | cluster | run`
- support counts and representative runs
- warnings and degraded-support notes
- key evidence highlights:
  - top outcomes or distinguishing metrics
  - scenario-family summary when relevant
  - selected-run assumption-ledger summary when relevant
  - confidence status
  - upstream grounding status

The compare workspace should also show one bounded comparison summary:

- “what differs”
- “what has weak support”
- “what remains empirical or observational only”

The compare workspace must not present a synthesized winner, strongest scenario, or causal recommendation as if the artifact itself proved that claim.

### Scope behavior that should exist end-to-end

#### Step 3

- remains the canonical owner of the initial `primary_scope`
- can choose `ensemble`, `cluster`, or `run`
- must show the currently selected Step 4 scope explicitly before handoff

#### Step 4

- reads the saved `primary_scope`
- can switch the primary evidence view across `ensemble`, `cluster`, and `run`
- can enter a dedicated compare workspace using bounded compare options for the current context
- can hand the chosen compare pair to Step 5 without changing report identity

#### Step 5

- report-agent lane gets a manual scope switcher across available `ensemble`, `cluster`, and `run` scopes
- report-agent lane can adopt the current Step 4 compare selection
- interviews and surveys remain legacy-scoped and must say so explicitly

## Artifact And API Contract To Add Or Tighten

### Keep existing artifacts stable

Do not rename:

- `probabilistic_report_context.json`
- `scenario_clusters.json`
- `sensitivity.json`

### Additive compare contract in report context

`probabilistic_report_context.json` should gain one additive compare section, for example:

- `compare_catalog`
  - `boundary_note`
  - `options[]`
    - `compare_id`
    - `label`
    - `reason`
    - `left_scope`
    - `right_scope`
    - `left_snapshot`
    - `right_snapshot`
    - `comparison_summary`
    - `warnings`
    - `prompt`

Each snapshot should be compact and inspectable, not a copy of the full report context.

This keeps compare self-contained for Step 4 UI and Step 5 handoff without requiring a separate compare API.

### Route/session contract

Keep the existing primary route contract:

- `mode=probabilistic`
- `ensembleId`
- optional `clusterId`
- optional `runId`
- `scope`

Add one additive session-level compare handoff token:

- `compareId`

Decision:

- `compareId` is enough if it references a compare option already present in the current saved report context
- do not add a sprawling left/right route encoding unless implementation proves it is necessary

## What Remains Out Of Scope Even After This Phase

- cross-report compare
- cross-simulation compare
- compare history as a first-class replay target
- stepwise compare persistence as report identity
- scope-aware interviews or surveys
- release-grade operational evidence beyond local repo workflows
- stronger than empirical, observed, or observational language without stronger artifacts

## Task 1: Add Compare-Ready Report Context Metadata

**Files:**
- Modify: `backend/app/services/probabilistic_report_context.py`
- Modify: `backend/tests/unit/test_probabilistic_report_context.py`
- Modify: `backend/tests/unit/test_probabilistic_report_api.py`

**Implementation intent:**

Use the existing scope catalog and compare options as the seed, but materialize compare-ready snapshots so Step 4 no longer has to fake compare out of prompt chips alone.

**Required behavior:**

1. `probabilistic_report_context.json` exposes bounded `compare_catalog` metadata.
2. Each compare option references two explicit scopes inside one ensemble.
3. Left and right snapshots carry only inspectable scope summaries, support, warnings, and bounded evidence fields.
4. Unsupported or missing compare data must degrade to an honest unavailable or partial state.
5. Compare metadata must preserve current empirical, observed, and observational semantics.

## Task 2: Finish Step 4 Compare Surface And Step 5 Scope Control

**Files:**
- Modify: `frontend/src/utils/probabilisticRuntime.js`
- Modify: `frontend/src/components/Step3Simulation.vue`
- Modify: `frontend/src/components/ProbabilisticReportContext.vue`
- Modify: `frontend/src/components/Step4Report.vue`
- Modify: `frontend/src/components/Step5Interaction.vue`
- Modify: `frontend/src/views/ReportView.vue`
- Modify: `frontend/src/views/InteractionView.vue`
- Modify: `frontend/tests/unit/probabilisticRuntime.test.mjs`

**Implementation intent:**

Finish the operator product flow without building a separate compare application.

**Required behavior:**

1. Step 3 still shows the active primary Step 4 scope clearly.
2. Step 4 gains a dedicated compare workspace, not just starter chips.
3. Step 4 compare lets the operator select one bounded compare option and inspect left/right evidence side by side.
4. Step 5 report-agent lane gains manual scope switching across available `ensemble`, `cluster`, and `run` scopes.
5. Step 5 can accept a Step 4 compare handoff through `compareId`.
6. Step 5 banner and evidence chips remain explicit that only the report-agent lane is scope-aware.
7. Surveys and interviews remain legacy-scoped and say so plainly.

## Task 3: Expand Browser Verification To Match The Product Contract

**Files:**
- Modify: `tests/smoke/probabilistic-runtime.spec.mjs`
- Modify: `tests/live/probabilistic-operator-local.spec.mjs`
- Modify: `package.json` only if a new final-audit alias is justified

**Implementation intent:**

Make the verification matrix match the actual final-assessment claim.

**Required smoke coverage:**

- Step 3 explicit primary scope selection across `ensemble`, `cluster`, and `run`
- Step 4 compare workspace visible and truthful
- Step 5 report-agent manual scope switching
- Step 5 compare handoff from Step 4
- history replay still restoring the saved primary scope correctly

**Required live local operator coverage:**

- Step 2 handoff
- Step 3 stop, retry, cleanup, child rerun
- Step 4 loading from the live report scope
- Step 5 loading from saved report scope
- one compare workflow capture into `output/playwright/live-operator/latest.json`

Decision:

- a live local pass is the strongest practical repo evidence for this phase
- it is still local operator evidence, not release-grade deployment evidence

## Task 4: Final Docs, Runbook, And Contract Cleanup

**Files:**
- Modify: `README.md`
- Modify: `docs/local-probabilistic-operator-runbook.md`
- Modify: `docs/plans/2026-03-29-forecasting-integration-hardening-wave.md`

**Implementation intent:**

Leave one coherent description of what the repo now supports and what it still does not.

**Required cleanup:**

1. Remove stale statements that compare has no dedicated workspace if the phase implements one.
2. Remove stale statements that Step 5 manual scope switching is deferred if the phase implements it.
3. Add one explicit “final audit can assume” section.
4. Keep the hard boundaries visible:
   - compare is bounded to one report context
   - interviews and surveys remain legacy-scoped
   - calibration is still named-metric and binary-only
   - live prepare still depends on local credentials and services
5. Make the verification order explicit and consistent across README and the runbook.

## Strongest Practical Verification For This Phase

Run these during implementation and again before closeout:

1. `cd /Users/danielbloom/Desktop/MiroFishES/backend && python3 -m pytest tests/unit/test_probabilistic_report_context.py tests/unit/test_probabilistic_report_api.py tests/unit/test_scenario_clusterer.py tests/unit/test_sensitivity_analyzer.py -q`
2. `cd /Users/danielbloom/Desktop/MiroFishES/frontend && node --test tests/unit/probabilisticRuntime.test.mjs`
3. `cd /Users/danielbloom/Desktop/MiroFishES && npm run verify:confidence`
4. `cd /Users/danielbloom/Desktop/MiroFishES && npm run verify`
5. `cd /Users/danielbloom/Desktop/MiroFishES && npm run verify:smoke`
6. `cd /Users/danielbloom/Desktop/MiroFishES && PLAYWRIGHT_LIVE_ALLOW_MUTATION=true npm run verify:operator:local`

If implementation adds a single final-audit alias, document that alias too, but do not replace the explicit commands above in the plan.

## Acceptance Criteria For “Done Enough For Final Audit”

The overhaul is done enough for final audit when all of the following are true:

1. Step 4 contains a dedicated compare workspace that is more than chips or starter prompts.
2. Compare is bounded, inspectable, and truthful:
   - left and right scopes are explicit
   - support and warnings are visible
   - empirical or observational boundaries are visible
3. Step 5 report-agent chat supports explicit manual scope switching across available `ensemble`, `cluster`, and `run` scopes.
4. Step 5 can accept and reflect one bounded compare handoff from Step 4.
5. Saved report context and history replay still restore the primary scope correctly.
6. README, the local operator runbook, and the hardening-wave note all describe the same current product contract.
7. Focused backend tests, frontend runtime tests, `npm run verify`, `npm run verify:smoke`, and the local mutating operator pass all pass freshly.
8. The repo can truthfully say:
   - the forecasting-control-plane overhaul is locally final-audit-ready
   - compare, operator scope, grounding, and confidence surfaces are bounded and inspectable
   - the repo is not claiming production-grade rollout evidence or globally calibrated forecasting

## End State

If this phase lands correctly, MiroFishES will have a finished local operator story for Step 3 through Step 5:

- explicit primary scope ownership
- a real compare workspace
- a report-agent lane with explicit scope control
- coherent docs and verification

That is enough to call the overhaul complete for a final audit without pretending the repo has become a production deployment system or a fully calibrated forecasting platform.
