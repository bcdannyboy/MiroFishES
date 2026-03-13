# Step 3 History Reentry Wave Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Let History reopen the probabilistic Step 3 stored-run shell from durable probabilistic runtime scope while keeping compare out of MVP and keeping unsupported history cases explicit.

**Architecture:** Keep history simulation/report centric, but add one bounded backend runtime summary so the UI can reopen Step 3 from the newest durable probabilistic runtime even when no report exists yet. Reuse the existing Step 3 route/query contract (`mode`, `ensembleId`, `runId`) and derive one small history replay helper from `latest_probabilistic_runtime` with fallback to saved report metadata instead of inventing ensemble-history rows or a compare contract. Pair the UI change with backend history tests, one frontend unit layer, and one fixture-backed Playwright smoke so the new re-entry seam is covered at API, helper, and browser level.

**Tech Stack:** Vue 3, Vue Router, Vite, Playwright, Node test runner, existing probabilistic runtime helpers

---

### Task 1: Add History Step 3 Replay Helper

**Files:**
- Modify: `backend/app/api/simulation.py`
- Test: `backend/tests/unit/test_probabilistic_report_api.py`
- Modify: `frontend/src/utils/probabilisticRuntime.js`
- Test: `frontend/tests/unit/probabilisticRuntime.test.mjs`

**Step 1: Write the failing test**

Add failing unit coverage for a helper that:
- enables Step 3 replay when a history record has `simulation_id` plus either `latest_probabilistic_runtime.ensemble_id`/`run_id` or the older `latest_report.ensemble_id`/`run_id` fallback
- returns the exact Step 3 route/query payload
- stays disabled for legacy or scope-missing history records

**Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/test_probabilistic_report_api.py -q` and `node --test frontend/tests/unit/probabilisticRuntime.test.mjs`
Expected: FAIL on the missing backend/runtime helper assertions.

**Step 3: Write minimal implementation**

Add one backend history summary in `backend/app/api/simulation.py` plus one frontend helper in `frontend/src/utils/probabilisticRuntime.js` so History can derive Step 3 replay availability and route/query data from durable probabilistic runtime scope.

**Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/test_probabilistic_report_api.py -q` and `node --test frontend/tests/unit/probabilisticRuntime.test.mjs`
Expected: PASS with the new backend/helper coverage included.

### Task 2: Wire History Modal Step 3 Reentry

**Files:**
- Modify: `frontend/src/components/HistoryDatabase.vue`
- Modify: `frontend/src/utils/probabilisticRuntime.js`
- Test: `frontend/tests/unit/probabilisticRuntime.test.mjs`

**Step 1: Write the failing test**

Extend unit coverage to lock any new helper output used by the modal copy/button state, including the new `step3` action test id if needed.

**Step 2: Run test to verify it fails**

Run: `node --test frontend/tests/unit/probabilisticRuntime.test.mjs`
Expected: FAIL until the helper contract matches the modal needs.

**Step 3: Write minimal implementation**

Update `HistoryDatabase.vue` to:
- show a Step 3 button only when durable probabilistic replay scope exists
- route to `SimulationRun` with `mode=probabilistic`, `ensembleId`, and `runId`
- replace the old hard-coded “Step 3 must still be launched live” copy with conditional truthful guidance

**Step 4: Run test to verify it passes**

Run: `node --test frontend/tests/unit/probabilisticRuntime.test.mjs`
Expected: PASS with helper contracts green.

### Task 3: Add Fixture-Backed History -> Step 3 Smoke Coverage

**Files:**
- Modify: `tests/smoke/probabilistic-runtime.spec.mjs`

**Step 1: Write the failing smoke assertion**

Add a new browser flow that:
- opens Home
- expands history
- opens a saved probabilistic card
- clicks the new Step 3 action
- asserts the Step 3 route/query and stored shell load correctly

**Step 2: Run test to verify it fails**

Run: `npm run verify:smoke -- --grep "history can reopen Step 3 from a saved probabilistic report"`
Expected: FAIL because the new action does not exist yet.

**Step 3: Write minimal implementation**

Keep the smoke change aligned to the new History modal surface and the existing probabilistic fixture contract.

**Step 4: Run test to verify it passes**

Run: `npm run verify:smoke -- --grep "history can reopen Step 3 from a saved probabilistic report"`
Expected: PASS.

### Task 4: Refresh Truth Docs For The New Reentry Boundary

**Files:**
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-status-audit.md`
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-readiness-dashboard.md`
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-execution-log.md`
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-decision-log.md`
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-gate-evidence-ledger.md`
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-frontend-task-register.md`
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-integration-task-register.md`

**Step 1: Record the exact supported boundary**

Document that History can now reopen Step 3 from bounded durable probabilistic runtime scope (`latest_probabilistic_runtime` first, saved report metadata second), while compare and broader ensemble-history rows remain deferred.

**Step 2: Record exact evidence**

Document the exact unit, smoke, and broad verification evidence from this session with dates and counts.

**Step 3: Reconcile task status honestly**

Advance only the subtasks supported by code and tests; keep compare and richer ensemble-history browsing explicitly deferred.

### Task 5: Run Broad Verification

**Files:**
- None

**Step 1: Run frontend verification**

Run: `npm run verify`
Expected: PASS with updated frontend test counts and backend regression counts.

**Step 2: Run fixture-backed smoke**

Run: `npm run verify:smoke`
Expected: PASS with the new Step 3 history replay coverage included.

**Step 3: Decide on live evidence refresh**

Run `PLAYWRIGHT_LIVE_ALLOW_MUTATION=true npm run verify:operator:local` after the broad gates if the Step 3 runtime surface or PM truth baselines changed and the latest live-operator evidence needs refreshing.
