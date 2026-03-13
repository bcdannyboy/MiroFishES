# Step 5 Report Scope and History Re-entry Implementation Plan

**Status (2026-03-09 later continuations):** implemented and later superseded as the active execution guide. The saved-report history replay path shipped, and the later verification-first continuation replaced the old force-click smoke workaround with exact selectors plus deterministic history ordering. Use the execution log and live PM control docs for current state.

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the frontend actually use the already-implemented `report_id`-scoped Step 5 chat path, expose truthful Step 5 re-entry from history, and extend smoke/PM evidence for the report-scoped probabilistic path.

**Architecture:** Keep `report_id` as the canonical Step 4 and Step 5 route identity. The backend report/chat seam is already capable of targeting one exact saved report, so this wave focuses on adopting that durable identity in the frontend, enriching history with the latest report replay metadata, and aligning UI and PM truth with the repo’s real reopen/replay behavior. Preserve the current legacy interaction path for individual-agent chat and surveys unless the saved report context explicitly supports more.

**Tech Stack:** Flask backend, Vue 3, Vite, Playwright, pytest, Node test runner

---

### Task 1: Lock history replay metadata with failing backend tests

**Files:**
- Create or Modify: `backend/tests/unit/test_simulation_history_api.py`
- Modify: `backend/app/api/simulation.py`

**Step 1: Write the failing test**

Add targeted tests that prove:
- `/api/simulation/history` returns the newest saved report metadata for one simulation.
- the history payload includes whether the latest report has saved probabilistic context plus any saved `ensemble_id` and `run_id`.
- legacy history entries without reports remain stable.

**Step 2: Run test to verify it fails**

Run: `cd /Users/danielbloom/Desktop/MiroFishES/backend && python3 -m pytest tests/unit/test_simulation_history_api.py -q`
Expected: FAIL because history does not yet expose report replay metadata.

**Step 3: Write minimal implementation**

Implement only the backend code required to:
- resolve the newest saved report metadata deterministically for history,
- surface that metadata in `/api/simulation/history`,
- and keep legacy entries unchanged when no report exists.

**Step 4: Run test to verify it passes**

Run: `cd /Users/danielbloom/Desktop/MiroFishES/backend && python3 -m pytest tests/unit/test_simulation_history_api.py -q`
Expected: PASS

### Task 2: Thread report-scoped Step 5 behavior through the frontend

**Files:**
- Modify: `frontend/src/api/report.js`
- Modify: `frontend/src/components/Step5Interaction.vue`
- Modify: `frontend/src/utils/probabilisticRuntime.js`
- Modify: `frontend/tests/unit/probabilisticRuntime.test.mjs`

**Step 1: Write the failing test**

Add frontend tests that prove:
- Step 5 report-agent requests include `report_id`,
- Step 5 state stays honest about what is report-scoped vs still legacy-scoped,
- saved probabilistic report context can produce a more precise Step 5 notice without implying full ensemble-grounded agent or survey support.

**Step 2: Run test to verify it fails**

Run: `cd /Users/danielbloom/Desktop/MiroFishES/frontend && node --test tests/unit/probabilisticRuntime.test.mjs`
Expected: FAIL because Step 5 helper logic and report-agent request scope do not yet include `report_id`.

**Step 3: Write minimal implementation**

Update Step 5 so:
- report-agent chat posts `report_id`,
- the notice copy distinguishes report-agent scope from still-legacy individual-agent/survey scope,
- and the legacy path remains intact.

**Step 4: Run test to verify it passes**

Run: `cd /Users/danielbloom/Desktop/MiroFishES/frontend && node --test tests/unit/probabilisticRuntime.test.mjs`
Expected: PASS

### Task 3: Expose truthful Step 5 history re-entry and smoke it

**Files:**
- Modify: `frontend/src/components/HistoryDatabase.vue`
- Modify: `frontend/src/api/simulation.js` only if a small replay-metadata helper gap is found
- Modify: `tests/smoke/probabilistic-runtime.spec.mjs`
- Modify: `playwright.config.mjs` only if the smoke environment needs a narrow capability adjustment

**Step 1: Write the failing smoke expectation**

Extend the smoke harness so it proves:
- history exposes a Step 5 re-entry path when a saved report exists,
- the modal copy no longer claims Step 5 is non-replayable when the repo can reopen it by `report_id`,
- the reopened Step 5 route still shows the bounded probabilistic interaction state honestly.

**Step 2: Run test to verify it fails**

Run: `cd /Users/danielbloom/Desktop/MiroFishES && npm run verify:smoke`
Expected: FAIL because history does not yet expose a Step 5 entry point and the modal copy is stale.

**Step 3: Write minimal implementation**

Update history so:
- Step 4 and Step 5 can reopen from saved `report_id`,
- Step 3 remains clearly live-only,
- probabilistic report history rows can show bounded replay metadata without inventing Step 3 support,
- and the history copy matches the actual route support.

**Step 4: Run test to verify it passes**

Run: `cd /Users/danielbloom/Desktop/MiroFishES && npm run verify:smoke`
Expected: PASS

### Task 4: Refresh PM truth and rerun full verification

**Files:**
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-status-audit.md`
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-readiness-dashboard.md`
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-execution-log.md`
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-decision-log.md`
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-gate-evidence-ledger.md`
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-frontend-task-register.md`
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-report-context-contract.md`
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-frontend-ux-contract.md`

**Step 1: Update docs only after code and tests are real**

Record:
- exact report-scoped Step 5 behavior,
- exact history re-entry support,
- exact remaining limits for individual-agent chat, surveys, and broader ensemble history.

**Step 2: Run targeted and broad verification**

Run:
- `cd /Users/danielbloom/Desktop/MiroFishES/backend && python3 -m pytest tests/unit/test_simulation_history_api.py -q`
- `cd /Users/danielbloom/Desktop/MiroFishES/frontend && node --test tests/unit/probabilisticRuntime.test.mjs`
- `cd /Users/danielbloom/Desktop/MiroFishES && npm run verify:smoke`
- `cd /Users/danielbloom/Desktop/MiroFishES && npm run verify`

Expected: PASS

**Step 3: Reassess the next wave**

If this wave lands cleanly, the next decision should be between:
- fuller Step 5 ensemble-aware chat grounding beyond the report-agent-only seam,
- H2 operator runbooks plus non-fixture runtime evidence,
- or a broader probabilistic history package for Step 3 and compare.
