# Step 5 Report-Scoped Chat and History Re-entry Implementation Plan

**Status (2026-03-09 later continuations):** implemented as the shipped Step 5 report-scoped slice, then later hardened with deterministic latest-report lookup, saved-report history replay selectors, and fresh verification. Treat this file as historical wave intent; use the execution log, status audit, and H4 docs for the current repo-grounded truth.

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make probabilistic Step 5 safer and more useful by grounding report-agent chat on the exact saved report, then add Step 5 re-entry from history without weakening the legacy interaction path.

**Architecture:** Keep Step 5 agent interviews and surveys explicitly legacy-scoped for now. Tighten only the report-agent lane: send `report_id` with chat requests, load the exact saved report instead of an arbitrary report for the same simulation, and thread saved `probabilistic_context` into the Step 5 state model and copy. Then expose Step 5 history re-entry through saved reports, relying on existing report metadata to reconstruct probabilistic scope.

**Tech Stack:** Flask backend, Vue 3, Vue Router, pytest, Node test runner, existing PM control docs

---

### Task 1: Lock report-scoped Step 5 state in tests

**Files:**
- Modify: `frontend/tests/unit/probabilisticRuntime.test.mjs`
- Modify: `frontend/src/utils/probabilisticRuntime.js`

**Step 1: Write the failing test**

Add tests that prove:
- probabilistic Step 5 distinguishes report-agent chat grounding from legacy-only agent interviews and surveys
- saved probabilistic context changes the Step 5 notice copy without implying full ensemble-aware interaction support

**Step 2: Run test to verify it fails**

Run: `node --test frontend/tests/unit/probabilisticRuntime.test.mjs`
Expected: FAIL because the current Step 5 helper exposes only one coarse unsupported state

**Step 3: Write minimal implementation**

Add the smallest helper changes needed to model:
- report-agent chat grounded by saved report context
- agent/survey interactions still legacy-scoped

**Step 4: Run test to verify it passes**

Run: `node --test frontend/tests/unit/probabilisticRuntime.test.mjs`
Expected: PASS

### Task 2: Add backend report-scoped chat tests

**Files:**
- Modify: `backend/tests/unit/test_probabilistic_report_api.py`
- Modify: `backend/app/api/report.py`
- Modify: `backend/app/services/report_agent.py`

**Step 1: Write the failing test**

Add tests that prove:
- `POST /api/report/chat` accepts `report_id`
- chat uses the exact saved report when `report_id` is supplied instead of any report returned by `get_report_by_simulation`
- saved probabilistic report context is available to the report-agent chat path without breaking legacy `simulation_id` requests

**Step 2: Run test to verify it fails**

Run: `cd backend && python3 -m pytest tests/unit/test_probabilistic_report_api.py -q`
Expected: FAIL because chat currently keys only on `simulation_id`

**Step 3: Write minimal implementation**

Implement:
- optional `report_id` handling in `/api/report/chat`
- exact-report lookup for report content
- additive probabilistic-context injection into the report-agent chat prompt

**Step 4: Run test to verify it passes**

Run: `cd backend && python3 -m pytest tests/unit/test_probabilistic_report_api.py -q`
Expected: PASS

### Task 3: Wire Step 5 and history to the safer report-scoped path

**Files:**
- Modify: `frontend/src/api/report.js`
- Modify: `frontend/src/components/Step5Interaction.vue`
- Modify: `frontend/src/components/HistoryDatabase.vue`
- Modify: `frontend/src/views/InteractionView.vue`

**Step 1: Write the failing test**

Where practical, extend helper-level tests for:
- Step 5 sending `report_id` on report-agent chat
- Step 5 copy reflecting grounded report-agent chat versus legacy-scoped agent/survey lanes

If a direct component test is not cheap with the current harness, lock the route/state behavior in helper tests first and rely on integration verification for the component wiring.

**Step 2: Run test to verify it fails**

Run: `node --test frontend/tests/unit/probabilisticRuntime.test.mjs`
Expected: FAIL because the frontend still treats Step 5 as one undifferentiated unsupported probabilistic state

**Step 3: Write minimal implementation**

Update Step 5 to:
- send `report_id` in report-agent chat requests
- show more precise probabilistic support copy
- add a Step 5 history/re-entry button when a saved report exists

Keep:
- legacy behavior intact for non-probabilistic reports
- agent interviews and surveys explicitly labeled legacy-scoped

**Step 4: Run test to verify it passes**

Run: `npm --prefix frontend run verify`
Expected: PASS

### Task 4: Refresh PM truth and verification evidence

**Files:**
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-status-audit.md`
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-readiness-dashboard.md`
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-execution-log.md`
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-decision-log.md`
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-gate-evidence-ledger.md`
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-frontend-task-register.md`
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-integration-task-register.md`
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-report-context-contract.md`

**Step 1: Update docs after code and tests are real**

Record:
- exact Step 5 grounding scope
- exact history re-entry scope
- exact remaining limits for agent interviews, surveys, and Step 3 replay

**Step 2: Run targeted and broad verification**

Run:
- `cd backend && python3 -m pytest tests/unit/test_probabilistic_report_api.py -q`
- `node --test frontend/tests/unit/probabilisticRuntime.test.mjs`
- `npm run verify`
- `npm run verify:smoke`

Expected: PASS

**Step 3: Reassess next wave**

After this lands, reassess whether the next highest-leverage lane is:
- broader Step 5 grounding for agent/survey flows
- Step 3 probabilistic history/re-entry
- H2 operator/runbook and non-fixture runtime evidence
- H5 release-ops packaging
