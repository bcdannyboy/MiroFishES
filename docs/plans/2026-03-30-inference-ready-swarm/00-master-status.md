# Inference-Ready Swarm Master Status

Date: 2026-03-30
Updated at: 2026-03-30T20:57:49-07:00
Plan id: `2026-03-30-inference-ready-swarm`
Prompt chain step: 6
State: prompt 6 complete, NOT READY

## Summary

Prompt 1 produced the planning baseline for bringing MiroFishES to internal research-ready inference as a simulation-backed feature generator.
Prompt 2 completed P1, the canonical forecast control plane.
Prompt 3 completed P2, the simulation-market extraction artifact layer.
Prompt 4 completed P3-P6, the signal schema, aggregation, provenance gating, and hybrid-engine integration layer.
Prompt 5 completed P7-P8, the resolution/scoring lifecycle plus forecast-object-first report/API/frontend integration layer.
Prompt 6 executed the final readiness ladder and failed closed. MiroFishES is not ready for internal research use yet because the Step 4/5 report-context path is still failing smoke and live end-to-end validation.

The new inference-ready path is now forecast-workspace-first in code:

- forecast workspaces persist canonical lifecycle metadata
- forecast workspaces persist explicit simulation scope
- simulation state can carry `forecast_id`
- simulation create/prepare/ensemble/run-start endpoints can create or reopen a forecast workspace and attach simulation scope
- question-primary `/api/forecast/questions` creation now stays question-first even if callers over-send richer legacy workspace payloads

The strongest code-truth finding is that the repo already contains a meaningful forecast foundation:

- canonical forecast models already exist
- forecast workspace persistence already exists
- forecast API and runtime helpers already exist
- hybrid forecast engine already exists with contribution tracing

The main missing layer is no longer the simulation-market inference layer. That layer now exists in code. The current blocking gaps are:

- Step 4 compare selection still fails to surface the selected compare handoff/detail state in smoke
- Step 5 still fails to surface the hybrid workspace consistently from saved probabilistic report context
- categorical and numeric hybrid-answer smoke expectations remain red because the Step 4/5 hybrid workspace path is incomplete
- live local Step 4/5 verification still cannot resolve a completed probabilistic report scope
- one history reopen smoke assertion is now stale because probabilistic scope is preserved in the URL query string

## Deliverables created

- `01-code-truth-gap-analysis.md`
- `02-target-architecture.md`
- `03-task-graph.md`
- `04-swarm-board.json`
- `status.json`
- `05-readiness-report.md`
- `06-readiness-status.json`

## Swarm state

- Active local swarm id: `swarm-1774818185510-bscyl8`
- Topology: `hierarchical-mesh`
- Strategy: `specialized`
- Ownership slices assigned:
  - Dirac: architecture and forecast control plane
  - Lagrange: simulation-market extraction and aggregation
  - Arendt: semantics and provenance
  - Volta: report/API/frontend integration
  - Carver: verification and end-to-end validation
  - Curie: resolution/scoring and narrow research support

## Coordination note

Ruflo MCP write APIs are currently misresolving to `/.claude-flow/...` instead of the workspace-local `.claude-flow/...` directory. To keep the autonomous chain unblocked, the planning board is mirrored directly into:

- `docs/plans/2026-03-30-inference-ready-swarm/04-swarm-board.json`
- `.claude-flow/tasks/store.json`
- `.claude-flow/swarm/swarm-state.json`

This keeps the plan machine-readable and locally aligned with existing Ruflo state despite the MCP write-path defect.

## Prompt 2 completion

- Completed task: `task-20260330-inference-001`
- Phase: `P1 canonical forecast control plane`
- Status: `complete`

### Files changed

- `backend/app/models/forecasting.py`
- `backend/app/services/forecast_manager.py`
- `backend/app/services/simulation_manager.py`
- `backend/app/api/forecast.py`
- `backend/app/api/simulation.py`
- `backend/tests/unit/test_forecasting_schema.py`
- `backend/tests/unit/test_forecast_manager.py`
- `backend/tests/unit/test_forecast_api.py`
- `backend/tests/unit/test_probabilistic_prepare.py`
- `backend/tests/unit/test_probabilistic_ensemble_api.py`
- `backend/tests/integration/test_probabilistic_operator_flow.py`

### What changed

- Added canonical workspace artifacts:
  - `simulation_scope.json`
  - `lifecycle_metadata.json`
  - `resolution_record.json`
  - `scoring_events.json`
- Added `ForecastSimulationScope`, `ForecastLifecycleMetadata`, `ForecastResolutionRecord`, and `ForecastScoringEvent` models.
- Made `ForecastWorkspaceRecord` derive and serialize canonical lifecycle/scope state.
- Added `ForecastManager.attach_simulation_scope(...)`.
- Added `forecast_id` to `SimulationState` and simulation creation.
- Wired simulation create/prepare/ensemble/run-start API paths to create or reopen forecast workspaces and attach scope when forecast context is supplied.
- Kept legacy `/api/forecast/workspaces` behavior intact while making `/api/forecast/questions` stay question-primary.

### Validation

- Command:
  - `pytest -q backend/tests/unit/test_forecasting_schema.py backend/tests/unit/test_forecast_manager.py backend/tests/unit/test_forecast_api.py backend/tests/unit/test_probabilistic_prepare.py backend/tests/unit/test_probabilistic_ensemble_api.py backend/tests/integration/test_probabilistic_operator_flow.py`
- Result:
  - `116 passed`

## Prompt 3 completion

- Completed task: `task-20260330-inference-002`
- Phase: `P2 simulation-market extraction artifacts`
- Status: `complete`

### Files changed

- `backend/app/models/simulation_market.py`
- `backend/app/services/simulation_market_extractor.py`
- `backend/app/services/simulation_runner.py`
- `backend/app/services/ensemble_manager.py`
- `backend/app/services/probabilistic_report_context.py`
- `backend/app/api/simulation.py`
- `backend/tests/unit/test_simulation_market_schema.py`
- `backend/tests/unit/test_simulation_market_extractor.py`
- `backend/tests/unit/test_outcome_extractor.py`
- `backend/tests/unit/test_simulation_runner_run_scope.py`
- `backend/tests/unit/test_probabilistic_report_context.py`
- `backend/tests/integration/test_probabilistic_operator_flow.py`

### What changed

- Added versioned simulation-market artifact models for:
  - run-scoped references
  - per-agent beliefs
  - disagreement summaries
  - market snapshots
  - manifest metadata
- Added `SimulationMarketExtractor` to extract bounded inference signals from raw action logs.
- Persisted new run-scoped artifacts on completion and stop paths:
  - `simulation_market_manifest.json`
  - `agent_belief_book.json`
  - `belief_update_trace.json`
  - `disagreement_summary.json`
  - `market_snapshot.json`
  - `argument_map.json`
  - `missing_information_signals.json`
- Registered those files in `run_manifest.artifact_paths`.
- Extended ensemble run loading so stored runs expose `simulation_market`.
- Extended probabilistic report context so `selected_run` can expose additive simulation-market snapshots.
- Extended cleanup paths so simulation-market artifacts are removed and de-registered alongside `metrics.json`.

### Validation

- Command:
  - `pytest -q backend/tests/unit/test_simulation_market_schema.py backend/tests/unit/test_simulation_market_extractor.py backend/tests/unit/test_outcome_extractor.py backend/tests/unit/test_simulation_runner_run_scope.py backend/tests/unit/test_probabilistic_report_context.py backend/tests/unit/test_probabilistic_ensemble_api.py backend/tests/integration/test_probabilistic_operator_flow.py`
- Result:
  - `73 passed`

### Boundaries preserved

- extraction is heuristic because runtime logs still emit raw discourse, not native belief objects
- simulation-market artifacts remain observational and non-calibrated
- numeric questions are still unsupported in this extraction lane
- report-context exposure is additive only; no forecast-engine integration happened in Prompt 3

## Prompt 4 completion

- Completed tasks:
  - `task-20260330-inference-003`
  - `task-20260330-inference-004`
  - `task-20260330-inference-005`
  - `task-20260330-inference-006`
- Phase: `P3-P6 signal schema, simulation-market aggregation, forecast-engine integration, and provenance validation`
- Status: `complete`

### Files changed

- `backend/app/models/forecasting.py`
- `backend/app/models/simulation_market.py`
- `backend/app/services/simulation_market_aggregator.py`
- `backend/app/services/forecast_signal_provenance.py`
- `backend/app/services/forecast_engine.py`
- `backend/app/services/hybrid_forecast_service.py`
- `backend/tests/unit/test_simulation_market_aggregator.py`
- `backend/tests/unit/test_forecast_signal_provenance.py`
- `backend/tests/unit/test_forecast_engine.py`
- `backend/tests/unit/test_hybrid_forecast_service.py`
- `backend/tests/integration/test_probabilistic_operator_flow.py`

### What changed

- Added `SimulationMarketSummary` and explicit signal/provenance schema for simulation-derived inference.
- Added `SimulationMarketAggregator` to convert persisted run artifacts into deterministic forecast signals:
  - synthetic consensus probability
  - disagreement index
  - argument cluster distribution
  - belief momentum
  - minority warning signal
  - missing-information signal
  - scenario split distribution
- Added `ForecastSignalProvenanceValidator` so critical signal references can fail closed and partial provenance can downgrade rather than silently pass.
- Added `simulation_market` as a first-class worker kind and auto-registration path in the hybrid forecast service.
- Wired the hybrid forecast engine to consume simulation-market summaries, apply abstention/downgrade rules, and expose simulation-market contribution traces in the final forecast answer payload.
- Preserved explicit boundaries:
  - simulation-market signals remain heuristic and observational
  - invalid provenance blocks best-estimate use
  - numeric questions remain unsupported in this lane

### Validation

- Command:
  - `pytest -q backend/tests/unit/test_simulation_market_schema.py backend/tests/unit/test_simulation_market_extractor.py backend/tests/unit/test_simulation_market_aggregator.py backend/tests/unit/test_forecast_signal_provenance.py backend/tests/unit/test_forecast_engine.py backend/tests/unit/test_hybrid_forecast_service.py backend/tests/unit/test_forecast_manager.py backend/tests/integration/test_probabilistic_operator_flow.py`
- Result:
  - `40 passed`
- Command:
  - `pytest -q backend/tests/unit/test_forecasting_schema.py backend/tests/unit/test_probabilistic_report_context.py backend/tests/unit/test_probabilistic_ensemble_api.py backend/tests/unit/test_outcome_extractor.py backend/tests/unit/test_simulation_runner_run_scope.py`
- Result:
  - `80 passed`

## Prompt 5 completion

- Completed tasks:
  - `task-20260330-inference-007`
  - `task-20260330-inference-008`
- Phase: `P7-P8 resolution/scoring lifecycle plus report/API/frontend integration`
- Status: `complete`

### Files changed

- `backend/app/__init__.py`
- `backend/app/api/forecast.py`
- `backend/app/services/ensemble_manager.py`
- `backend/app/services/forecast_manager.py`
- `backend/app/services/forecast_resolution_manager.py`
- `backend/app/services/probabilistic_report_context.py`
- `backend/app/services/report_agent.py`
- `backend/app/models/forecasting.py`
- `frontend/src/utils/forecastRuntime.js`
- `frontend/src/utils/probabilisticRuntime.js`
- `frontend/src/components/Step2EnvSetup.vue`
- `frontend/src/components/Step3Simulation.vue`
- `frontend/src/components/ProbabilisticReportContext.vue`
- `frontend/src/components/Step5Interaction.vue`
- `backend/tests/unit/test_forecast_api.py`
- `backend/tests/unit/test_forecast_resolution_manager.py`
- `backend/tests/unit/test_probabilistic_report_context.py`
- `backend/tests/unit/test_probabilistic_report_api.py`
- `backend/tests/integration/test_probabilistic_operator_flow.py`
- `frontend/tests/unit/probabilisticRuntime.test.mjs`

### What changed

- Added explicit resolution/scoring service support for final forecast objects via `ForecastResolutionManager`.
- Added forecast question scoring endpoints and first-class `resolution_record` / `scoring_events` API payloads.
- Extended run loading and report-context generation so simulation-market summary and provenance are first-class report/API objects.
- Reframed report prompting so forecast objects lead and simulation narrative supports.
- Updated runtime helpers and Step 2/3/5 UI surfaces so forecast workspaces, scoring, and simulation-market/provenance state are visible without pretending unsupported calibration or causal strength.
- Hardened the Flask app factory to register the route-bound forecast blueprint under the test harness's stubbed `app.api` package model.
- Fixed forecast workspace resolution-state normalization and multi-root lookup drift in `ForecastManager`.

### Validation

- Command:
  - `pytest -q backend/tests/unit/test_forecast_api.py backend/tests/unit/test_forecast_resolution_manager.py backend/tests/unit/test_probabilistic_report_context.py backend/tests/unit/test_probabilistic_report_api.py backend/tests/integration/test_probabilistic_operator_flow.py`
- Result:
  - `64 passed`
- Command:
  - `node --test frontend/tests/unit/probabilisticRuntime.test.mjs`
- Result:
  - `70 passed`

### What Prompt 5 now proves

- forecast objects can be resolved and scored through the API
- the report stack can surface forecast object, simulation-market summary, and signal provenance together
- one end-to-end integration path exists from question creation through simulation-backed forecast derivation and forecast resolution
- the Step 2/3/5 runtime surfaces now reflect forecast-object-first state honestly

### Boundaries preserved

- simulation-market evidence remains observational and non-causal
- scoring events are explicit, but this still does not imply broad earned calibration
- Prompt 5 does not certify live local end-to-end readiness; that remains Prompt 6 work

## Ready for Prompt 6

Prompt 6 should begin with:

1. read `status.json`
2. read this file
3. restore the existing swarm/task board state
4. start `task-20260330-inference-009`
5. run the final readiness verification ladder
6. harden any remaining truthfulness/semantic debt needed to satisfy readiness gates
7. fail closed if live/local readiness gates do not pass

## Remaining blockers

- Step 4 compare selection does not reliably surface `probabilistic-compare-handoff`
- Step 5 does not reliably surface `probabilistic-step5-hybrid-workspace`
- categorical and numeric hybrid-answer smoke paths remain red
- live local Step 4/5 verification still cannot resolve a completed probabilistic report scope
- history reopen smoke expects the old URL shape after probabilistic query preservation

## Do not lose these boundaries

- simulation-derived signals are not automatically calibrated probabilities
- clustering and sensitivity remain observational, not causal
- the forecast object is primary for the new path, but the simulated marketplace remains a legitimate feature generator

## Prompt 6 completion

- Completed task:
  - `task-20260330-inference-009`
- Phase: `P9 final readiness verification and hardening`
- Status: `complete, failed closed`
- Verdict: `NOT READY`

### Files changed

- `backend/tests/unit/test_scan_forecasting_artifacts_script.py`
- `frontend/src/components/ProbabilisticReportContext.vue`
- `frontend/src/components/Step4Report.vue`
- `frontend/src/components/Step5Interaction.vue`
- `frontend/src/components/HistoryDatabase.vue`
- `docs/plans/2026-03-30-inference-ready-swarm/00-master-status.md`
- `docs/plans/2026-03-30-inference-ready-swarm/status.json`
- `docs/plans/2026-03-30-inference-ready-swarm/05-readiness-report.md`
- `docs/plans/2026-03-30-inference-ready-swarm/06-readiness-status.json`

### What changed

- Fixed the forecasting artifact scan unit tests so they isolate against temporary forecast directories instead of whatever exists in the repo worktree.
- Relaxed Step 4 probabilistic-context gating so capability-loading banners do not suppress the actual forecast/simulation evidence card.
- Added local report-context hydration in Step 4 and Step 5 so saved reports can recover probabilistic context even if the parent view has not passed it down yet.
- Preserved probabilistic query state when reopening report and interaction routes from history.
- Re-ran the readiness ladder under real local browser execution and failed closed when the Step 4/5 surfaces still did not meet the acceptance gates.

### Validation

- Command:
  - `pytest -q backend/tests/unit/test_forecasting_schema.py backend/tests/unit/test_forecast_manager.py backend/tests/unit/test_forecast_api.py backend/tests/unit/test_simulation_market_schema.py backend/tests/unit/test_simulation_market_extractor.py backend/tests/unit/test_simulation_market_aggregator.py backend/tests/unit/test_forecast_signal_provenance.py backend/tests/unit/test_forecast_engine.py backend/tests/unit/test_hybrid_forecast_service.py backend/tests/unit/test_forecast_resolution_manager.py backend/tests/unit/test_probabilistic_report_context.py backend/tests/unit/test_probabilistic_report_api.py backend/tests/integration/test_probabilistic_operator_flow.py`
- Result:
  - `114 passed`
- Command:
  - `node --test frontend/tests/unit/forecastRuntime.test.mjs frontend/tests/unit/probabilisticRuntime.test.mjs`
- Result:
  - `79 passed`
- Command:
  - `pytest -q backend/tests/unit/test_scan_forecasting_artifacts_script.py`
- Result:
  - `8 passed`
- Command:
  - `npm run verify:forecasting`
- Result:
  - `passed`
- Command:
  - `npm run verify:smoke`
- Result:
  - `failed`
  - `4 passed, 6 failed`
- Command:
  - `PLAYWRIGHT_LIVE_ALLOW_MUTATION=true npm run verify:operator:local`
- Result:
  - `failed`
  - `1 passed, 1 failed`

### Failing readiness evidence

- `tests/smoke/probabilistic-runtime.spec.mjs:189`
  - Step 4 compare handoff is still missing after selecting a compare option.
- `tests/smoke/probabilistic-runtime.spec.mjs:200`
  - Step 5 still does not render `probabilistic-step5-hybrid-workspace`.
- `tests/smoke/probabilistic-runtime.spec.mjs:215`
  - categorical hybrid-answer surface is still red.
- `tests/smoke/probabilistic-runtime.spec.mjs:229`
  - numeric hybrid-answer surface is still red.
- `tests/smoke/probabilistic-runtime.spec.mjs:243`
  - compare handoff action remains unavailable.
- `tests/smoke/probabilistic-runtime.spec.mjs:297`
  - history reopen assertion is stale because probabilistic query state is now preserved in the URL.
- `tests/live/probabilistic-operator-local.spec.mjs:610`
  - live Step 4/5 verification still cannot resolve a completed probabilistic report scope.

### Final gate summary

- Gate 1: `pass`
  - forecast question and forecast workspace creation/open are implemented and verified.
- Gate 2: `pass`
  - simulation-backed scenario/market runs execute for a forecast question; live Step 2/3 passed.
- Gate 3: `pass`
  - structured simulation-market inference artifacts are emitted and verified.
- Gate 4: `pass`
  - the forecast engine consumes those signals and exposes contribution tracing.
- Gate 5: `pass`
  - signal-level provenance exists and invalid provenance is rejected or downgraded.
- Gate 6: `fail`
  - report/context surfaces are still not reliable enough end to end because Step 4/5 smoke remains red.
- Gate 7: `pass`
  - resolution/scoring primitives exist and are verified.
- Gate 8: `fail`
  - automated inference-ready verification is not fully green because smoke and live Step 4/5 are failing.
- Gate 9: `fail`
  - the local environment permitted the live run, but the end-to-end Step 4/5 path did not validate.

### Environment note

The browser-based readiness checks were initially blocked inside the sandbox, but they were rerun successfully with escalation. The remaining failures are not sandbox blockers. They are code-path or runtime-behavior failures in the Step 4/5 report-context flow.
