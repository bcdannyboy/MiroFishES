# Probabilistic Report Context Wave Implementation Plan

**Status (2026-03-10 later continuations):** historical and superseded as a live execution guide. The first report-context slice landed, but current repo truth now lives in the March 8 control packet plus `docs/plans/2026-03-10-hybrid-h2-truthful-local-hardening-wave.md`. Do not use this file as the current execution baseline.

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add the first report-ready probabilistic context path so Step 4 can consume ensemble summary, cluster, and sensitivity artifacts without breaking the legacy report flow.

**Architecture:** Build a backend report-context artifact over the already-real ensemble analytics, then thread that context into report metadata and Step 4 rendering behind explicit probabilistic flags. Keep `report_id` as the durable Step 4 route identity, preserve the legacy simulation-scoped report flow, and defer Step 5 chat grounding unless the new backend context makes it trivially safe in the same session.

**Tech Stack:** Flask backend, Vue/Vite frontend, pytest, Node test runner

---

### Task 1: Add the failing backend report-context tests

**Files:**
- Create: `backend/tests/unit/test_probabilistic_report_context.py`
- Test: `backend/tests/unit/test_probabilistic_report_context.py`

**Step 1: Write the failing test**

Add focused tests that assert:
- a report-context builder can load one ensemble's `aggregate_summary.json`, `scenario_clusters.json`, and `sensitivity.json`
- the built context labels probabilities as empirical and preserves warnings instead of hiding degraded evidence
- the context distinguishes ensemble-level, cluster-level, and representative-run facts
- the builder persists `probabilistic_report_context.json`

**Step 2: Run test to verify it fails**

Run: `cd /Users/danielbloom/Desktop/MiroFishES/backend && python3 -m pytest tests/unit/test_probabilistic_report_context.py -q`
Expected: FAIL because the report-context builder and artifact do not exist yet.

**Step 3: Write minimal implementation**

Do not touch Step 4 yet. Add only the smallest backend seam required for the tests to pass.

**Step 4: Run test to verify it passes**

Run: `cd /Users/danielbloom/Desktop/MiroFishES/backend && python3 -m pytest tests/unit/test_probabilistic_report_context.py -q`
Expected: PASS

### Task 2: Implement backend report-context loading and persistence

**Files:**
- Create: `backend/app/services/probabilistic_report_context.py`
- Modify: `backend/app/services/ensemble_manager.py`
- Modify: `backend/app/api/simulation.py`
- Test: `backend/tests/unit/test_probabilistic_report_context.py`

**Step 1: Extend the failing test coverage**

Add cases for:
- missing cluster or sensitivity artifacts returning explicit omissions or warnings
- representative-run identity being sourced from the cluster prototype when available
- API retrieval of the persisted context for one ensemble

**Step 2: Run test to verify it fails**

Run: `cd /Users/danielbloom/Desktop/MiroFishES/backend && python3 -m pytest tests/unit/test_probabilistic_report_context.py -q`
Expected: FAIL because the service and route are incomplete.

**Step 3: Write minimal implementation**

Implement:
- a dedicated builder service for `probabilistic_report_context.json`
- persistence under `uploads/simulations/<simulation_id>/ensemble/ensemble_<ensemble_id>/`
- a simulation-scoped retrieval route for one ensemble context
- explicit provenance fields, warning passthrough, and no calibrated claims

**Step 4: Run test to verify it passes**

Run: `cd /Users/danielbloom/Desktop/MiroFishES/backend && python3 -m pytest tests/unit/test_probabilistic_report_context.py tests/unit/test_probabilistic_ensemble_api.py -q`
Expected: PASS

### Task 3: Make report generation and retrieval context-aware without breaking legacy flow

**Files:**
- Modify: `backend/app/api/report.py`
- Modify: `backend/app/services/report_agent.py`
- Test: `backend/tests/unit/test_probabilistic_report_context.py`

**Step 1: Write the failing test**

Add tests that assert:
- `POST /api/report/generate` can accept `ensemble_id` and optional `run_id`
- report metadata stores the probabilistic context reference when present
- legacy `simulation_id`-only report generation still works

**Step 2: Run test to verify it fails**

Run: `cd /Users/danielbloom/Desktop/MiroFishES/backend && python3 -m pytest tests/unit/test_probabilistic_report_context.py -q`
Expected: FAIL because report generation is still simulation-only.

**Step 3: Write minimal implementation**

Implement:
- optional `ensemble_id` and `run_id` handling in report generation
- report metadata fields for probabilistic context and provenance
- legacy-compatible fallback when no ensemble context is requested or available

**Step 4: Run test to verify it passes**

Run: `cd /Users/danielbloom/Desktop/MiroFishES/backend && python3 -m pytest tests/unit/test_probabilistic_report_context.py -q`
Expected: PASS

### Task 4: Add the first Step 4 probabilistic report cards

**Files:**
- Modify: `frontend/src/components/Step3Simulation.vue`
- Modify: `frontend/src/components/Step4Report.vue`
- Modify: `frontend/src/api/report.js`
- Modify: `frontend/src/utils/probabilisticRuntime.js`
- Modify: `frontend/tests/unit/probabilisticRuntime.test.mjs`

**Step 1: Write the failing test**

Add frontend helper tests that assert:
- Step 4 card derivation reads probabilistic report metadata/context safely
- empirical labels, run-count support, and warnings remain visible
- missing probabilistic context degrades to the legacy report view cleanly

**Step 2: Run test to verify it fails**

Run: `cd /Users/danielbloom/Desktop/MiroFishES/frontend && node --test tests/unit/probabilisticRuntime.test.mjs`
Expected: FAIL because Step 4 report-card helpers do not exist yet.

**Step 3: Write minimal implementation**

Implement:
- Step 3 probabilistic report generation enablement only when the backend advertises report support
- Step 4 summary cards for top outcomes, scenario families, and sensitivity warnings
- a legacy-safe fallback when report context is absent

**Step 4: Run test to verify it passes**

Run: `cd /Users/danielbloom/Desktop/MiroFishES/frontend && node --test tests/unit/probabilisticRuntime.test.mjs`
Expected: PASS

### Task 5: Refresh PM truth and run verification

**Files:**
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-status-audit.md`
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-readiness-dashboard.md`
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-execution-log.md`
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-decision-log.md`
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-gate-evidence-ledger.md`
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-backend-task-register.md`
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-frontend-task-register.md`
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-integration-task-register.md`
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-api-contracts.md`
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-schema-and-artifact-contracts.md`

**Step 1: Update docs only after code and tests are real**

Record:
- exact implemented scope
- exact remaining deferrals, especially Step 5 chat grounding if still absent
- exact verification evidence from this session

**Step 2: Run targeted and broad verification**

Run: `cd /Users/danielbloom/Desktop/MiroFishES/backend && python3 -m pytest tests/unit/test_probabilistic_report_context.py -q`
Expected: PASS

Run: `cd /Users/danielbloom/Desktop/MiroFishES/backend && python3 -m pytest tests -q`
Expected: PASS

Run: `cd /Users/danielbloom/Desktop/MiroFishES/frontend && node --test tests/unit/probabilisticRuntime.test.mjs`
Expected: PASS

Run: `cd /Users/danielbloom/Desktop/MiroFishES && npm run verify`
Expected: PASS

**Step 3: Reassess for another wave**

If report context and Step 4 are real and verified, decide whether the next ready wave is:
- Step 5 ensemble-aware interaction context
- happy-path browser smoke evidence
- H2/B6.3 operator lifecycle and retry/rerun semantics
