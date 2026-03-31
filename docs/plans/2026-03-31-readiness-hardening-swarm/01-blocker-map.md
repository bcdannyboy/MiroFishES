# Readiness Hardening Blocker Map

Updated at: 2026-03-31T08:32:41-07:00

## Current Case Map

| Case | Status | Verification | Exact files/modules/tests | Primary owner |
| --- | --- | --- | --- | --- |
| Step 4 hybrid workspace surface missing | closed in targeted smoke | `tests/smoke/probabilistic-runtime.spec.mjs:200-240` green in the prompt-3 rerun | `frontend/src/components/ProbabilisticReportContext.vue`, `frontend/src/components/Step5Interaction.vue`, `frontend/tests/unit/probabilisticRuntime.test.mjs`, `tests/smoke/probabilistic-runtime.spec.mjs` | Volta-equivalent |
| Step 5 hybrid workspace surface missing | closed in targeted smoke | `tests/smoke/probabilistic-runtime.spec.mjs:200-240` green in the prompt-3 rerun | `frontend/src/components/Step5Interaction.vue`, `frontend/src/components/ProbabilisticReportContext.vue` | Volta-equivalent |
| Categorical hybrid Step 4/5 flow red | closed in targeted smoke | `tests/smoke/probabilistic-runtime.spec.mjs:215-226` green | `frontend/src/components/ProbabilisticReportContext.vue`, `frontend/src/components/Step5Interaction.vue`, `frontend/src/utils/forecastRuntime.js`, `frontend/src/utils/probabilisticRuntime.js` | Volta-equivalent |
| Numeric hybrid Step 4/5 flow red | closed in targeted smoke | `tests/smoke/probabilistic-runtime.spec.mjs:229-240` green | `frontend/src/components/ProbabilisticReportContext.vue`, `frontend/src/components/Step5Interaction.vue`, `frontend/src/utils/forecastRuntime.js`, `frontend/src/utils/probabilisticRuntime.js` | Volta-equivalent |
| Compare handoff into Step 5 red | closed in targeted smoke | `tests/smoke/probabilistic-runtime.spec.mjs:243-264` green after shared-state rerun | `frontend/src/components/ProbabilisticReportContext.vue`, `frontend/src/components/Step4Report.vue`, `frontend/src/components/Step5Interaction.vue`, `frontend/src/utils/probabilisticRuntime.js`, `frontend/tests/unit/probabilisticRuntime.test.mjs`, `tests/smoke/probabilistic-runtime.spec.mjs` | Volta-equivalent |
| History reopen Step 5 assertion stale | closed in targeted smoke | `tests/smoke/probabilistic-runtime.spec.mjs:308-345` green after aligning load/expand timing with the current UI contract | `tests/smoke/probabilistic-runtime.spec.mjs`, `frontend/src/components/HistoryDatabase.vue`, `frontend/src/utils/probabilisticRuntime.js` | Carver-equivalent |
| Live Step 4/5 cannot resolve completed report scope | closed in targeted live verification | `PLAYWRIGHT_LIVE_ALLOW_MUTATION=true npm run verify:operator:local -- --grep "Step 4 report and Step 5 report-agent work on a live probabilistic report"` green | `tests/live/probabilistic-operator-local.spec.mjs`, live simulation/report selection under `backend/uploads/*` | Carver-equivalent with Raman support |
| Dedicated backend inference-ready path proof | closed in focused backend verification | `cd backend && python3 -m pytest tests/integration/test_inference_ready_forecast_flow.py -q` green | `backend/tests/integration/test_inference_ready_forecast_flow.py`, `backend/tests/integration/test_probabilistic_operator_flow.py`, `backend/app/services/probabilistic_report_context.py`, `backend/app/api/report.py` | Dirac-equivalent |
| Broad readiness verification ladder | pending next phase, not a focused blocker | not rerun in this prompt by design | full smoke/live/backend readiness ladder | Carver-equivalent with Raman + Dirac support |

## Closed Cluster A: Saved Hybrid Workspace Now Reaches Step 4/5 Honestly

Closed cases:

- Step 5 hybrid workspace surface missing
- categorical hybrid Step 4/5 flow
- numeric hybrid Step 4/5 flow

Root cause fixed:

1. `frontend/src/components/Step5Interaction.vue` used `hybridWorkspace.simulationMarketSummary?.syntheticConsensusProbability !== null`, which is truthy when the summary is absent because `undefined !== null`.
2. The same pattern existed in `frontend/src/components/ProbabilisticReportContext.vue` for `selectedRun.marketSummary`.
3. Those branches then dereferenced missing market-summary fields and aborted the visible render path even though the saved report context already contained a valid hybrid workspace and best-estimate display.
4. The patch made those render gates null-safe and kept the existing forecast-object-first/runtime truth source intact.

Why this is code-truth:

- `frontend/tests/unit/probabilisticRuntime.test.mjs` and `frontend/tests/unit/forecastRuntime.test.mjs` were already green for categorical/numeric best-estimate formatting before the patch.
- the red state was the browser render layer, not the formatter logic
- after the null-guard patch, the targeted smoke slice is green without changing the answer-formatting path

## Closed Cluster B: Compare Selection And Compare Handoff Round Trip

Closed case:

- compare handoff into Step 5

What is now verified together:

1. Step 4 still reconciles hydrated compare ids against saved probabilistic report context.
2. The shared Step 4/5 render repair no longer prevents the selected compare state from surfacing in the visible DOM.
3. `tests/smoke/probabilistic-runtime.spec.mjs:243-264` is green in the prompt-3 rerun, so `probabilistic-compare-handoff` appears and Step 5 opens with preserved `compareId`.

Relevant files:

- `frontend/src/components/ProbabilisticReportContext.vue`
- `frontend/src/components/Step4Report.vue`
- `frontend/src/components/Step5Interaction.vue`
- `frontend/src/utils/probabilisticRuntime.js`
- `frontend/tests/unit/probabilisticRuntime.test.mjs`
- `tests/smoke/probabilistic-runtime.spec.mjs`

## Closed Cluster C: History Replay Contract Is Now Aligned

Closed case:

- Step 5 history reopen assertion

What changed:

1. The smoke test now waits for the history control to load and expands the stack before asserting alternate-card visibility.
2. The replay URL contract itself remains unchanged: the green rerun still asserts `mode=probabilistic`, `ensembleId`, `scope=run`, and `runId` on the reopened Step 5 route.

Relevant files:

- `tests/smoke/probabilistic-runtime.spec.mjs`
- `frontend/src/components/HistoryDatabase.vue`
- `frontend/src/utils/probabilisticRuntime.js`

## Closed Cluster D: Live Step 4/5 Bootstrap Now Resolves A Real Completed Scope

Closed case:

- `tests/live/probabilistic-operator-local.spec.mjs`

Exact code path:

1. the live verifier now catalogs non-smoke completed probabilistic reports separately from mere prepared simulations
2. it prefers a completed saved report scope first, instead of assuming the newest prepared simulation is Step 4/5-ready
3. only if no saved report exists does it fall back to a run-derived scope, and that fallback now requires a ready linked `simulation_market_manifest`
4. when a completed report already exists, the live Step 4/5 test reuses that scope instead of forcing a fresh report generation

Focused verification evidence:

- the latest green live run selected `sim_03059e7c8be8`
- it reused saved report `report_61ad87c3279a`
- Step 4, Step 5, compare handoff, and report chat all completed in the targeted live slice

## Closed Cluster E: Backend Inference-Ready Proof Now Covers Persistence And Rediscovery

Closed case:

- dedicated backend inference-ready path proof

What is now explicitly proved:

1. the inference-ready integration test drives the real chain from forecast question to forecast workspace, extracted simulation signals, hybrid answer generation, report generation, and saved report retrieval
2. the test now asserts the persisted `probabilistic_report_context.json` sidecar exists at ensemble scope after report-context generation
3. it verifies the saved report payload retains exact `scope`, `selected_run`, `forecast_id`, and `answer_id` data needed by downstream consumers
4. it verifies exact `(simulation_id, ensemble_id, run_id)` rediscovery through `/api/report/generate/status` returns the completed saved report instead of a looser latest-by-simulation match

## Failing-Test-First Coverage Status

Present and green after this prompt:

- `frontend/tests/unit/forecastRuntime.test.mjs`
- `frontend/tests/unit/probabilisticRuntime.test.mjs`
- `tests/smoke/probabilistic-runtime.spec.mjs` targeted Step 4/5 hybrid, compare, and history slice
- `backend/tests/integration/test_inference_ready_forecast_flow.py`
- `tests/live/probabilistic-operator-local.spec.mjs` targeted Step 4/5 slice

Still outstanding:

- broad readiness verification beyond the focused slices above
