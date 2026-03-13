# Step 3 Multirun Operator Wave Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Expand the current probabilistic Step 2 to Step 3 handoff from a single stored run shell into a usable multirun operator flow with explicit ensemble sizing, run selection, and safe missing-run recovery while preserving the legacy path.

**Architecture:** Reuse the already-implemented simulation-scoped ensemble storage and runtime status APIs instead of adding new backend contracts. Add the missing Step 2 ensemble-size input and Step 3 run-list/state model on top of the existing `mode`, `ensembleId`, and `runId` route query contract, then update PM truth and H2 documentation to reflect the broader frontend adoption.

**Tech Stack:** Vue 3, Vue Router, Vite, Node test runner, Flask API contracts, Markdown PM control docs

---

### Task 1: Lock the route/runtime helper behavior for multirun selection

**Files:**
- Modify: `frontend/tests/unit/probabilisticRuntime.test.mjs`
- Modify: `frontend/src/utils/probabilisticRuntime.js`

**Step 1: Write the failing test**

Add tests that prove:
- route query helpers preserve a changed `runId` while keeping `mode`, `ensembleId`, and `maxRounds`
- a new helper can derive a stable selected run from an explicit query run, a fetched run list, and a fallback strategy when the selected run is missing

**Step 2: Run test to verify it fails**

Run: `npm --prefix frontend run verify -- --test tests/unit/probabilisticRuntime.test.mjs`
Expected: FAIL because the run-selection helper does not exist and the new selection persistence cases are not handled.

**Step 3: Write minimal implementation**

Implement helper-level selection and recovery logic in `frontend/src/utils/probabilisticRuntime.js` only.

**Step 4: Run test to verify it passes**

Run: `node --test frontend/tests/unit/probabilisticRuntime.test.mjs`
Expected: PASS

### Task 2: Add explicit probabilistic ensemble sizing to Step 2

**Files:**
- Modify: `frontend/src/components/Step2EnvSetup.vue`
- Test: `frontend/tests/unit/probabilisticRuntime.test.mjs`

**Step 1: Write the failing test**

Extend helper tests where practical for control serialization defaults. If the component behavior cannot be unit-tested cheaply with the current harness, capture the expected serialization and state rules in helper-level tests first.

**Step 2: Run test to verify it fails**

Run: `node --test frontend/tests/unit/probabilisticRuntime.test.mjs`
Expected: FAIL because the helper/default contract for ensemble sizing is not represented yet.

**Step 3: Write minimal implementation**

Add a Step 2 probabilistic run-count control with safe defaults and validation, and pass the selected count into `createSimulationEnsemble(...)` instead of hardcoding `run_count: 1`.

**Step 4: Run test to verify it passes**

Run: `npm --prefix frontend run verify`
Expected: PASS

### Task 3: Expand Step 3 into a multirun browser with safe selection recovery

**Files:**
- Modify: `frontend/src/components/Step3Simulation.vue`
- Modify: `frontend/src/views/SimulationRunView.vue`
- Modify: `frontend/src/views/SimulationView.vue`
- Modify: `frontend/src/api/simulation.js`
- Modify: `frontend/src/utils/probabilisticRuntime.js`
- Test: `frontend/tests/unit/probabilisticRuntime.test.mjs`

**Step 1: Write the failing test**

Add helper tests for:
- selecting an explicit run when it exists in the fetched run list
- falling back to a stable alternative when the current `runId` no longer exists
- keeping missing-selection copy truthful when no runs remain

**Step 2: Run test to verify it fails**

Run: `node --test frontend/tests/unit/probabilisticRuntime.test.mjs`
Expected: FAIL because no multirun selection/recovery helper exists yet.

**Step 3: Write minimal implementation**

In Step 3:
- fetch ensemble status and/or run list for the current ensemble
- render a run list panel with explicit status and seed metadata
- allow switching the selected run without leaving the route
- persist the selected run into the route query
- recover safely when the selected run is missing or deleted
- preserve the current single-run timeline/action drilldown and legacy mode behavior

**Step 4: Run test to verify it passes**

Run: `npm --prefix frontend run verify`
Expected: PASS

### Task 4: Refresh PM control docs for the new frontend/runtime truth

**Files:**
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-status-audit.md`
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-readiness-dashboard.md`
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-execution-log.md`
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-decision-log.md`
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-gate-evidence-ledger.md`
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-frontend-task-register.md`
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-h2-runtime-contract-draft.md`

**Step 1: Write the failing test**

No code test applies. The failure condition is stale PM truth after implementation.

**Step 2: Run verification of stale state**

Re-read the touched docs and compare them against the implemented UI/runtime behavior. Expected before edit: the docs still describe Step 3 as a single-run shell only and Step 2 as creating only one stored run shell.

**Step 3: Write minimal implementation**

Update PM artifacts with exact dates, exact verification counts, exact scope changes, and any remaining blockers around happy-path browser evidence and retry/rerun semantics.

**Step 4: Run verification**

Run: `rg -n "single-run probabilistic monitor|run_count: 1|broader multi-run browsing" docs/plans/2026-03-08-stochastic-probabilistic-*.md`
Expected: matches only where historical context or remaining gaps are intentionally described.

### Task 5: Fresh verification evidence

**Files:**
- Test only

**Step 1: Run focused frontend verification**

Run: `node --test frontend/tests/unit/probabilisticRuntime.test.mjs`
Expected: PASS

**Step 2: Run full frontend verification**

Run: `npm --prefix frontend run verify`
Expected: PASS

**Step 3: Run repo verification**

Run: `npm run verify`
Expected: PASS
