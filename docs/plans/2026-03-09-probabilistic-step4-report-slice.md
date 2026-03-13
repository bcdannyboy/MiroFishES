# Probabilistic Step 4 Report Slice Implementation Plan

**Status (2026-03-10 later continuations):** partially implemented and superseded as a live execution guide. The additive Step 4 report-context consumer shipped, but the current repo truth now treats saved report metadata, not route query alone, as the durable probabilistic Step 4 identity. Use the March 8 control packet plus `docs/plans/2026-03-10-hybrid-h2-truthful-local-hardening-wave.md` for current state.

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a truthful probabilistic Step 3 -> Step 4 handoff so legacy reports can display read-only empirical ensemble context without claiming calibrated or report-context-backed support.

**Architecture:** Keep the existing report generation pipeline simulation-scoped and unchanged. Add a frontend-only probabilistic report layer that is activated by explicit route/query handoff plus capability discovery, fetches the already-implemented ensemble analytics artifacts directly, and renders them as provenance-labeled observed context beside the legacy report body. Preserve the legacy single-run path and keep Step 5 explicitly limited when probabilistic interaction support is off.

**Tech Stack:** Vue 3, Vue Router, Vite, existing frontend utility test harness (`node --test`), existing backend analytics/report APIs.

---

### Task 1: Define Step 4 Probabilistic Handoff State

**Files:**
- Modify: `frontend/src/utils/probabilisticRuntime.js`
- Test: `frontend/tests/unit/probabilisticRuntime.test.mjs`

**Step 1: Write the failing test**

Add tests for:
- deriving Step 3 report-button state from runtime mode plus capability flags
- preserving probabilistic query handoff into Step 4 / Step 5 routes
- exposing explicit legacy-only helper text when probabilistic report or interaction support is off

**Step 2: Run test to verify it fails**

Run: `npm --prefix frontend run verify`
Expected: frontend unit test failure in `frontend/tests/unit/probabilisticRuntime.test.mjs`

**Step 3: Write minimal implementation**

Implement utility helpers for:
- probabilistic report CTA gating
- probabilistic route-query reuse for report/interaction routes
- explicit off-state labels for probabilistic Step 4 / Step 5 support

**Step 4: Run test to verify it passes**

Run: `npm --prefix frontend run verify`
Expected: new helper tests pass and the frontend build still succeeds

**Step 5: Commit**

Defer commit in this session unless explicitly requested.

### Task 2: Wire Step 3 Report Handoff

**Files:**
- Modify: `frontend/src/components/Step3Simulation.vue`
- Modify: `frontend/src/views/SimulationRunView.vue`
- Test: `frontend/tests/unit/probabilisticRuntime.test.mjs`

**Step 1: Write the failing test**

Add a test that proves probabilistic Step 3 can enable Step 4 only when the probabilistic report flag is on, while legacy behavior remains unchanged.

**Step 2: Run test to verify it fails**

Run: `npm --prefix frontend run verify`
Expected: report-state test fails because Step 3 still hard-disables probabilistic Step 4 unconditionally

**Step 3: Write minimal implementation**

Update Step 3 to:
- fetch/report capability state needed for Step 4 gating
- route to `/report/:reportId` with explicit probabilistic query handoff when enabled
- preserve existing legacy report-generation behavior for non-probabilistic runs

**Step 4: Run test to verify it passes**

Run: `npm --prefix frontend run verify`
Expected: report-state helper tests pass and build stays green

**Step 5: Commit**

Defer commit in this session unless explicitly requested.

### Task 3: Add Step 4 Observed Ensemble Context

**Files:**
- Create: `frontend/src/components/ProbabilisticReportContext.vue`
- Modify: `frontend/src/components/Step4Report.vue`
- Modify: `frontend/src/views/ReportView.vue`
- Modify: `frontend/src/api/simulation.js` if a small fetch helper gap is found
- Test: `frontend/tests/unit/probabilisticRuntime.test.mjs`

**Step 1: Write the failing test**

Add tests that verify the analytics-card helper output for Step 4 report context:
- summary/clusters/sensitivity cards remain empirical or observational
- warnings are surfaced directly
- empty/error states stay explicit instead of fabricating values

**Step 2: Run test to verify it fails**

Run: `npm --prefix frontend run verify`
Expected: new analytics/report-context assertions fail

**Step 3: Write minimal implementation**

Add a Step 4 side panel or header context block that:
- activates only when probabilistic route handoff is explicit
- fetches `aggregate_summary.json`, `scenario_clusters.json`, and `sensitivity.json`
- labels the data as observed empirical/observational context
- keeps the legacy report content intact

**Step 4: Run test to verify it passes**

Run: `npm --prefix frontend run verify`
Expected: helper tests pass and frontend build remains green

**Step 5: Commit**

Defer commit in this session unless explicitly requested.

### Task 4: Harden Step 5 Off-State and PM Truth

**Files:**
- Modify: `frontend/src/components/Step4Report.vue`
- Modify: `frontend/src/components/Step5Interaction.vue`
- Modify: `frontend/src/views/InteractionView.vue`
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-status-audit.md`
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-readiness-dashboard.md`
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-execution-log.md`
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-decision-log.md`
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-frontend-task-register.md`
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-gate-evidence-ledger.md`

**Step 1: Write the failing test**

Add or extend utility tests proving the interaction surface exposes an explicit unsupported/off-state instead of silently pretending probabilistic chat context exists.

**Step 2: Run test to verify it fails**

Run: `npm --prefix frontend run verify`
Expected: new off-state test fails

**Step 3: Write minimal implementation**

Update Step 4 / Step 5 flow so:
- probabilistic interaction remains clearly disabled unless the flag is on
- probabilistic query handoff is preserved for future work
- PM docs reflect exactly what landed, what remains blocked, and what evidence exists

**Step 4: Run test to verify it passes**

Run: `npm --prefix frontend run verify`
Expected: new off-state tests pass and docs match the code reality

**Step 5: Commit**

Defer commit in this session unless explicitly requested.

### Task 5: Full Verification

**Files:**
- Modify only if verification uncovers defects in files above

**Step 1: Run targeted verification**

Run: `npm --prefix frontend run verify`
Expected: frontend tests and build pass

**Step 2: Run repo verification**

Run: `npm run verify`
Expected: 14+ frontend tests pass, frontend build passes, and backend pytest passes

**Step 3: Review PM truth**

Confirm the status audit, readiness dashboard, execution log, decision log, and gate-evidence ledger all match the current repository and verification output.

**Step 4: Record blockers**

Document any remaining Step 5/report-context gaps, smoke gaps, or operator-policy gaps explicitly.

**Step 5: Commit**

Defer commit in this session unless explicitly requested.
