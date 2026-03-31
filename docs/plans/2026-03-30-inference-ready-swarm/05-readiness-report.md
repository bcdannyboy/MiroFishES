# Readiness Report

Date: 2026-03-30
Updated at: 2026-03-30T20:57:49-07:00
Plan id: `2026-03-30-inference-ready-swarm`
Verdict: `NOT READY`

## Executive verdict

MiroFishES is not ready for internal research use as a simulation-backed feature generator.

The code path is substantially implemented: forecast questions/workspaces exist, simulation-backed runs can emit structured inference artifacts, the forecast engine consumes those signals with contribution tracing, provenance gating exists, and resolution/scoring primitives exist. Focused backend and frontend verification passed. The system fails the final readiness bar because the Step 4/5 report-context path is still not reliable enough end to end, and the live local run did not validate the full question -> simulation -> extracted signals -> forecast answer path.

## Acceptance gates

1. `PASS` A user can define a forecast question and open a forecast workspace.
   Code path implemented and verified in focused backend suites.
2. `PASS` A simulation-backed scenario/market run can be executed for that question.
   Code path implemented and verified; live Step 2/3 validation passed.
3. `PASS` The system emits structured simulation-market inference artifacts.
   Code path implemented and verified in extraction and integration tests.
4. `PASS` The forecast engine consumes those signals and derives a final forecast answer with contribution tracing.
   Code path implemented and verified in engine, hybrid-service, and integration tests.
5. `PASS` Signal-level provenance exists and invalid provenance is rejected or downgraded.
   Code path implemented and verified.
6. `FAIL` A report/context surface can present the forecast object and supporting simulation evidence.
   Smoke is still red in Step 4/5 and compare/hybrid workspace behavior is incomplete.
7. `PASS` Resolution/scoring primitives exist for the final forecast object.
   Code path implemented and verified.
8. `FAIL` Automated tests for the inference-ready path pass.
   Focused suites are green, but smoke and live Step 4/5 are not.
9. `FAIL` At least one live local end-to-end run from question -> simulation -> extracted signals -> forecast answer succeeds.
   The environment permitted the run, but live Step 4/5 verification failed.

## Verification matrix

- `pytest -q backend/tests/unit/test_forecasting_schema.py backend/tests/unit/test_forecast_manager.py backend/tests/unit/test_forecast_api.py backend/tests/unit/test_simulation_market_schema.py backend/tests/unit/test_simulation_market_extractor.py backend/tests/unit/test_simulation_market_aggregator.py backend/tests/unit/test_forecast_signal_provenance.py backend/tests/unit/test_forecast_engine.py backend/tests/unit/test_hybrid_forecast_service.py backend/tests/unit/test_forecast_resolution_manager.py backend/tests/unit/test_probabilistic_report_context.py backend/tests/unit/test_probabilistic_report_api.py backend/tests/integration/test_probabilistic_operator_flow.py`
  Result: `114 passed`
- `node --test frontend/tests/unit/forecastRuntime.test.mjs frontend/tests/unit/probabilisticRuntime.test.mjs`
  Result: `79 passed`
- `pytest -q backend/tests/unit/test_scan_forecasting_artifacts_script.py`
  Result: `8 passed`
- `npm run verify:forecasting`
  Result: `passed`
- `npm run verify:smoke`
  Result: `failed` with `4 passed, 6 failed`
- `PLAYWRIGHT_LIVE_ALLOW_MUTATION=true npm run verify:operator:local`
  Result: `failed` with `1 passed, 1 failed`

## Exact blockers

- `tests/smoke/probabilistic-runtime.spec.mjs:189`
  Step 4 still fails to surface `probabilistic-compare-handoff` after selecting a compare option.
- `tests/smoke/probabilistic-runtime.spec.mjs:200`
  Step 5 still fails to surface `probabilistic-step5-hybrid-workspace`.
- `tests/smoke/probabilistic-runtime.spec.mjs:215`
  The categorical hybrid-answer path is still red.
- `tests/smoke/probabilistic-runtime.spec.mjs:229`
  The numeric hybrid-answer path is still red.
- `tests/smoke/probabilistic-runtime.spec.mjs:243`
  Compare handoff remains unavailable to the operator.
- `tests/smoke/probabilistic-runtime.spec.mjs:297`
  History reopen now preserves probabilistic query state, so the smoke assertion expecting the old URL shape is stale.
- `tests/live/probabilistic-operator-local.spec.mjs:610`
  Live Step 4/5 verification could not resolve a completed probabilistic report scope.

## Code path vs verification vs live validation

- `Code path implemented`
  Gates 1, 2, 3, 4, 5, and 7 are implemented in code.
- `Automated verification passed`
  Focused backend and frontend verification passed. `npm run verify:forecasting` passed.
- `Automated verification failed`
  Smoke remains red in Step 4/5.
- `Live local end-to-end validated`
  Step 2/3 validated.
- `Live local end-to-end failed`
  Step 4/5 did not validate because no completed probabilistic report scope was resolved for the live test family.
- `Blocked by environment`
  No. Browser-based verification initially needed escalation outside the sandbox, but the harness ran successfully afterward. The remaining blockers are code-path/runtime issues, not environment restrictions.

## Prompt 6 hardening work completed

- Fixed the forecasting artifact scan tests to isolate against temporary forecast directories.
- Relaxed Step 4 context gating so the forecast/simulation evidence card is not hidden behind capability-loading banners.
- Added local report-context hydration in Step 4 and Step 5 so saved reports can recover probabilistic context without relying on parent state.
- Preserved probabilistic query state when reopening reports/interactions from history.

## Final decision

`NOT READY`

Do not certify this repo for internal research use until the Step 4/5 report-context flow is green in smoke and at least one live local end-to-end path validates through forecast answer display.
