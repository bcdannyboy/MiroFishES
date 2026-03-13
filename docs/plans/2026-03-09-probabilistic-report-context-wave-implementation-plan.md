# Probabilistic Report Context Wave Implementation Plan

**Status (2026-03-10 later continuations):** historical and superseded as a live execution guide. The backend report-context and first Step 4 additive consumer landed, but current repo truth now lives in the March 8 control packet plus `docs/plans/2026-03-10-hybrid-h2-truthful-local-hardening-wave.md`. Do not use this file as the current execution baseline.

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add the first ensemble-aware report-context contract so probabilistic Step 3 runs can generate Step 4 reports with explicit empirical analytics context while preserving the legacy report flow.

**Architecture:** Keep report generation simulation-rooted for the report body, but add an additive probabilistic sidecar: when Step 3 launches report generation for a stored ensemble/run, the backend builds and persists a `probabilistic_report_context.json` artifact plus report metadata fields for `ensemble_id` and `run_id`. Step 4 consumes those persisted fields to render read-only empirical cards and scope labels without implying calibrated or fully ensemble-aware report generation.

**Tech Stack:** Flask, Python dataclasses/services, pytest, Vue 3, Vite, Node test runner

---

### Task 1: Add Backend Report-Context Contract Tests

**Files:**
- Create: `backend/tests/unit/test_probabilistic_report_context.py`
- Create: `backend/tests/unit/test_probabilistic_report_api.py`
- Modify: `backend/tests/conftest.py`

**Step 1: Write the failing tests**

Add backend tests that prove:
- a context builder can assemble deterministic report context from persisted prepare, ensemble, run, summary, cluster, and sensitivity artifacts
- the builder preserves warning/provenance fields instead of collapsing them
- `POST /api/report/generate` accepts optional `ensemble_id` and `run_id`
- `GET /api/report/<report_id>` returns persisted probabilistic scope/context metadata when present
- legacy report requests still work without probabilistic fields

**Step 2: Run tests to verify they fail**

Run: `python3 -m pytest backend/tests/unit/test_probabilistic_report_context.py backend/tests/unit/test_probabilistic_report_api.py -q`

Expected: FAIL because the context builder, API wiring, and report metadata fields do not exist yet.

**Step 3: Write minimal implementation**

Implement only the backend code needed to make the new report-context tests pass.

**Step 4: Run tests to verify they pass**

Run: `python3 -m pytest backend/tests/unit/test_probabilistic_report_context.py backend/tests/unit/test_probabilistic_report_api.py -q`

Expected: PASS

### Task 2: Persist Probabilistic Report Context in Backend Report Flow

**Files:**
- Create: `backend/app/services/probabilistic_report_context.py`
- Modify: `backend/app/services/report_agent.py`
- Modify: `backend/app/api/report.py`

**Step 1: Extend the failing tests if needed**

If Task 1 did not yet cover persistence details, add assertions for:
- persisted `probabilistic_report_context.json` path under `uploads/reports/<report_id>/`
- report metadata containing `ensemble_id`, `run_id`, and a compact context summary
- report lookup honoring `(simulation_id, ensemble_id, run_id)` when deduplicating existing reports

**Step 2: Run the targeted tests to verify RED**

Run: `python3 -m pytest backend/tests/unit/test_probabilistic_report_context.py backend/tests/unit/test_probabilistic_report_api.py -q`

Expected: FAIL on the new assertions.

**Step 3: Implement the backend sidecar**

Add:
- a context builder service that reads existing probabilistic artifacts only
- report metadata support for optional probabilistic scope
- additive API request/response fields
- persistence for `probabilistic_report_context.json`

Keep:
- legacy report generation behavior unchanged when no probabilistic scope is provided
- all displayed probability semantics labeled as empirical/observational only

**Step 4: Verify GREEN**

Run:
- `python3 -m pytest backend/tests/unit/test_probabilistic_report_context.py backend/tests/unit/test_probabilistic_report_api.py -q`
- `python3 -m pytest backend/tests -q`

Expected: PASS

### Task 3: Wire Step 3 -> Step 4 Probabilistic Scope and Step 4 Cards

**Files:**
- Modify: `frontend/src/api/report.js`
- Modify: `frontend/src/components/Step3Simulation.vue`
- Modify: `frontend/src/components/Step4Report.vue`
- Modify: `frontend/src/views/ReportView.vue`
- Modify: `frontend/src/utils/probabilisticRuntime.js`
- Modify: `frontend/tests/unit/probabilisticRuntime.test.mjs`

**Step 1: Write the failing frontend test**

Add or extend a unit test proving:
- report-generation requests include `ensemble_id` and `run_id` for probabilistic Step 3 sessions
- Step 4 card-derivation logic renders empirical summary/cluster/sensitivity state from persisted report context
- legacy report state remains unchanged when the report has no probabilistic context

**Step 2: Run the frontend test to verify RED**

Run: `npm --prefix frontend exec node --test tests/unit/probabilisticRuntime.test.mjs`

Expected: FAIL because report-context helpers/request payload handling do not exist yet.

**Step 3: Implement minimal frontend support**

Add:
- probabilistic report-generation payload fields from Step 3
- Step 4 read-only probabilistic cards and scope labels fed from report metadata/context
- explicit legacy/probabilistic copy boundaries so Step 4 still does not imply calibrated or Step 5-ready support

**Step 4: Verify GREEN**

Run:
- `npm --prefix frontend exec node --test tests/unit/probabilisticRuntime.test.mjs`
- `npm --prefix frontend run verify`

Expected: PASS

### Task 4: Refresh PM Truth and Handoff Docs

**Files:**
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-status-audit.md`
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-readiness-dashboard.md`
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-execution-log.md`
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-decision-log.md`
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-gate-evidence-ledger.md`
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-backend-task-register.md`
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-frontend-task-register.md`
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-integration-task-register.md`
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-h2-runtime-contract-draft.md`
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-api-contracts.md`
- Create or modify: `docs/plans/2026-03-08-stochastic-probabilistic-probabilistic-report-context-contract.md`

**Step 1: Capture exact verified scope**

Record:
- what landed in backend report context
- what Step 4 consumes now
- what remains deferred for Step 5 and full ensemble-aware report generation

**Step 2: Verify docs against code and tests**

Re-read changed code and cite exact command evidence from this session.

**Step 3: Update the PM packet**

Make the live docs reflect:
- actual statuses only
- exact test counts and commands
- exact remaining blockers

**Step 4: Run the full verification gate**

Run: `npm run verify`

Expected: PASS with the current frontend unit count, Vite build, and backend pytest count from this session.
