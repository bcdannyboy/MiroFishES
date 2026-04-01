# Graphiti + Neo4j Cutover Chain Ledger

## Branch

- active branch: `codex/graphiti-neo4j-overhaul-chain`
- committed prompt history present before Prompt 7 remediation:
  - `83b9a6a` `chore(graphiti-chain): establish cutover harness`
  - `b6c50f0` `feat(graphiti-chain): add backend core and base build path`
  - `cabd8aa` `feat(graphiti-chain): replace read-side graph query stack`
  - `4102a30` `feat(graphiti-chain): add runtime namespace and event ingestion`
  - `dc4219a` `feat(graphiti-chain): cut over apis and graph consumers`
- Prompt 6 repo-truth completion was verified and remediated from the current worktree during Prompt 7 because the earlier claim was not trusted without code, tests, and docs evidence

## Baseline Dirty Policy

- treat `docs/plans/2026-03-31-graphiti-neo4j-baseline-dirty.txt` as the authoritative pre-chain dirty manifest
- never stage or revert any path listed there unless this ledger explicitly adopts it
- Prompt 7 does not adopt any baseline dirty path
- baseline dirty paths remain excluded from staging:
  - `output/playwright/**`
  - `docs/plans/2026-03-31-graphiti-neo4j-cutover-prompt-chain.md`
  - `docs/plans/2026-03-31-graphiti-neo4j-overhaul.md`

## Chain-Owned Path Policy

- Prompt 1 chain-owned paths:
  - `docs/plans/2026-03-31-graphiti-neo4j-chain.md`
  - `docs/plans/2026-03-31-graphiti-neo4j-chain-status.json`
  - `docs/plans/2026-03-31-graphiti-neo4j-baseline-dirty.txt`
  - `package.json`
  - `.env.example`
  - `README.md`
  - `docs/local-probabilistic-operator-runbook.md`
  - `backend/pyproject.toml`
  - `backend/requirements.txt`
  - `backend/app/config.py`
  - `backend/app/api/graph.py`
  - `backend/app/services/graph_backend/`
  - `backend/scripts/`
  - `backend/tests/unit/services/graph_backend/`
  - `backend/tests/unit/test_graph_backend_readiness_api.py`
- Prompt 2 chain-owned paths:
  - Prompt 1 paths
  - `backend/app/services/graph_builder.py`
  - `backend/tests/unit/test_graph_builder_service.py`
- Prompt 3 chain-owned paths:
  - `backend/app/services/graph_backend/query_service.py`
  - `backend/app/services/graph_backend/scan_service.py`
  - `backend/app/services/zep_entity_reader.py`
  - `backend/app/services/zep_tools.py`
  - `backend/app/utils/graph_scan.py`
  - `backend/tests/unit/services/graph_backend/test_query_service.py`
  - `backend/tests/unit/services/graph_backend/test_scan_service.py`
  - `backend/tests/unit/test_zep_entity_reader.py`
  - `backend/tests/unit/test_zep_tools_multigraph.py`
  - `backend/tests/unit/test_report_agent_hybrid_retrieval.py`
  - chain state files
- Prompt 4 chain-owned paths:
  - `README.md`
  - `docs/local-probabilistic-operator-runbook.md`
  - `package.json`
  - `backend/app/api/simulation.py`
  - `backend/app/services/__init__.py`
  - `backend/app/services/graph_backend/`
  - `backend/app/services/runtime_graph_manager.py`
  - `backend/app/services/runtime_graph_state_store.py`
  - `backend/app/services/runtime_graph_updater.py`
  - `backend/app/services/simulation_runner.py`
  - `backend/scripts/verify_graphiti_scaffold.py`
  - `backend/scripts/verify_runtime_graph_live.py`
  - runtime graph unit tests
  - chain state files
- Prompt 5 chain-owned paths:
  - `.env.example`
  - `README.md`
  - `docs/local-probabilistic-operator-runbook.md`
  - `package.json`
  - `backend/app/api/graph.py`
  - `backend/app/api/report.py`
  - `backend/app/api/simulation.py`
  - `backend/app/services/graph_entity_reader.py`
  - `backend/app/services/graph_query_tools.py`
  - `backend/app/services/oasis_profile_generator.py`
  - `backend/app/services/probabilistic_smoke_fixture.py`
  - `backend/app/services/report_agent.py`
  - `backend/app/services/simulation_config_generator.py`
  - `backend/app/services/simulation_manager.py`
  - `backend/app/services/world_state_compiler.py`
  - `backend/app/services/zep_tools.py`
  - touched graph/report/simulation tests
  - chain state files
- Prompt 6 chain-owned paths:
  - Prompt 1-5 paths needed for repo-truth remediation
  - `playwright.config.mjs`
  - `scripts/ensure-graphiti-live-neo4j.sh`
  - `backend/uv.lock`
  - `backend/app/config.py`
  - `backend/app/services/backtest_manager.py`
  - `backend/app/services/calibration_manager.py`
  - `backend/app/services/ensemble_manager.py`
  - `backend/app/services/evidence_bundle_service.py`
  - `backend/app/services/forecast_manager.py`
  - `backend/app/services/grounding_bundle_builder.py`
  - `backend/app/services/ontology_generator.py`
  - `backend/app/services/probabilistic_report_context.py`
  - `backend/app/services/scenario_clusterer.py`
  - `backend/app/services/sensitivity_analyzer.py`
  - `backend/app/services/graph_backend/live_probe.py`
  - `backend/app/services/zep_graph_memory_updater.py`
  - `backend/app/utils/zep_paging.py`
  - `backend/tests/conftest.py`
  - `backend/tests/unit/test_backend_test_stubs.py`
  - `backend/tests/unit/test_graph_entity_reader.py`
  - `backend/tests/unit/test_graph_query_tools.py`
  - touched backend integration/unit tests required by the harness replacement
- Prompt 7 chain-owned paths:
  - Prompt 6 paths needed for end-to-end remediation
  - `README.md`
  - `docs/local-probabilistic-operator-runbook.md`
  - `.env.example`
  - `backend/app/api/graph.py`
  - `backend/scripts/verify_graphiti_scaffold.py`
  - `backend/scripts/verify_runtime_graph_live.py`
  - chain state files

## Commit Policy

- commit once at the end of each prompt
- stage only chain-owned paths for the active prompt
- never stage baseline dirty paths unless adopted here first
- Prompt 7 stages Prompt 7 paths plus Prompt 6 remediation paths because Prompt 6 repo-truth gaps were fixed before Prompt 7 could complete

## Prompt-By-Prompt Progress Log

### Prompt 1

- status: completed
- scope: branch creation, baseline dirty capture, chain state files, initial Graphiti + Neo4j config scaffolding, readiness endpoint, and verification wrapper foundation
- implemented decisions:
  - created the dedicated cutover branch
  - created the baseline dirty manifest, human ledger, and machine-readable status file
  - introduced `verify:graphiti:unit`, `integration`, `smoke`, `live`, and `all`
  - added `GET /api/graph/backend/readiness`
- verification summary:
  - scoped red then green: `4 failed` -> `4 passed`
  - `npm run verify:graphiti:all` passed as an honest scaffold ladder
  - broader backend regression: `13 passed`

### Prompt 2

- status: completed
- scope: backend core seam, namespace manager, ontology compiler, ingestion/export scaffolding, and Step 1 base graph build cutover off Zep
- implemented decisions:
  - built the internal `graph_backend` seam and Graphiti/Neo4j factories
  - compiled ontology JSON into Graphiti-compatible models
  - rewrote the base graph build path to stop depending on Zep
  - aligned dependency declarations to `neo4j>=5.23.0,<6.0.0`
- verification summary:
  - scoped red then green: `5 failed` -> `11 passed`
  - `npm run verify:graphiti:unit` passed
  - `npm run verify:graphiti:integration` passed while honestly reporting readiness gaps
  - broader backend regression: `25 passed`

### Prompt 3

- status: completed
- scope: read-side graph query stack, deterministic scans, multigraph base/runtime reads, entity reader, and report-agent retrieval adapters
- implemented decisions:
  - replaced the live Zep read path with deterministic artifact-backed query and scan services
  - preserved merged `base_graph_id` + `runtime_graph_id` semantics
  - preserved panorama/history-style runtime transition reads
- verification summary:
  - scoped red then green: `5 failed, 6 passed` -> `11 passed`
  - `npm run verify:graphiti:unit` passed
  - `npm run verify:graphiti:integration` passed
  - `npm run verify:graphiti:smoke` passed
  - broader regression: `29 passed` and `31 passed`

### Prompt 4

- status: completed
- scope: runtime namespace provisioning, runtime manifest/state alignment, runtime event ingestion, and live runtime probe scaffolding
- implemented decisions:
  - rewrote runtime provisioning around application-managed namespace ids
  - replaced the runtime updater path with Graphiti-backed ingestion services
  - added `backend/scripts/verify_runtime_graph_live.py`
- verification summary:
  - scoped red then green: `6 failed, 8 passed` -> `14 passed`
  - `npm run verify:graphiti:unit` passed
  - `npm run verify:graphiti:integration` passed
  - broader runtime regression: `38 passed`
  - live runtime probe passed against local Neo4j reachability

### Prompt 5

- status: completed
- scope: graph/report/simulation API cutover, report generation consumers, simulation entity endpoints, and secondary graph consumers
- implemented decisions:
  - rewrote touched APIs and consumers to use graph-backed services and DTOs
  - removed live `ZEP_API_KEY` requirements from the touched runtime paths
  - kept compatibility module names only where that reduced blast radius
- verification summary:
  - scoped red then green: `6 failed, 6 passed` -> `12 passed`
  - broader touched regressions: `119 passed` and `9 passed`
  - `npm run verify:graphiti:unit` passed after splitting the unit wrapper into deterministic invocations
  - `npm run verify:graphiti:integration` passed
  - `npm run verify:smoke` passed
  - live operator coverage was honestly still blocked at that point

### Prompt 6

- status: completed via Prompt 7 repo-truth remediation
- scope: harness replacement, live smoke/live readiness surface hardening, and legacy Zep deletion
- repo-truth gaps discovered at Prompt 7 startup:
  - legacy runtime Zep modules and Zep-only tests were still present in the worktree
  - smoke/live/operator usability was not yet hard enough to treat the repo as locally operable
  - docs had not fully converged around the managed local Neo4j helper, readiness surfaces, and the no-Zep operator contract
- implemented decisions:
  - deleted legacy runtime Zep modules:
    - `backend/app/services/zep_entity_reader.py`
    - `backend/app/services/zep_graph_memory_updater.py`
    - `backend/app/services/zep_tools.py`
    - `backend/app/utils/zep_paging.py`
  - deleted legacy Zep tests:
    - `backend/tests/unit/test_zep_entity_reader.py`
    - `backend/tests/unit/test_zep_tools_multigraph.py`
  - removed the `zep_cloud` test stub from `backend/tests/conftest.py`
  - added `backend/tests/unit/test_backend_test_stubs.py` to prove the harness no longer installs Zep shims
  - added `backend/app/services/graph_backend/live_probe.py` and helper-backed smoke/live defaults
  - added `scripts/ensure-graphiti-live-neo4j.sh` and wired smoke/live/operator wrappers through it
  - updated `playwright.config.mjs` and verification wrappers for the managed local graph helper path
- verification summary:
  - Prompt 6 repo-truth completion is evidenced by the final Prompt 7 verification ladder, not by earlier untrusted claims
  - the replacement harness and deletions now participate in `npm run verify:graphiti:all`, `npm run verify:smoke`, and `npm run verify:operator:local`

### Prompt 7

- status: completed
- scope: full-system remediation, activation flow hardening, startup/operator docs convergence, readiness/capabilities surface finalization, and broad verification repair
- Ruflo orchestration records:
  - workspace verifier result: `swarm-task-only`
  - swarm id: `swarm-1775026301901-ocayti`
  - research audit task id: `task-1775026320589-u6eecf`
  - remediation task id: `task-1775026320592-d0eg77`
  - docs task id: `task-1775026320608-fhbckc`
- architectural decisions actually implemented:
  - made simulation and forecasting data dir resolution dynamic in `backend/app/config.py` so broad verification runs no longer leak stale path state
  - added `GET /api/graph/backend/capabilities` as the stable operator-facing backend contract surface
  - fixed the Neo4j driver factory to call `GraphDatabase.driver(..., auth=...)`
  - fixed the run-scope readiness race so `SimulationRunner` no longer marks a run complete before monitor-thread artifact finalization
  - added managed-local graph default injection for smoke/live verification wrappers while keeping integration honest about the real `.env`
  - fixed `panorama_search` and edge scans to preserve edge attributes and runtime-history metadata
  - converged README, `.env.example`, and the local runbook around Graphiti + Neo4j CE activation with no Zep assumptions
- owned files actually changed:
  - `.env.example`
  - `README.md`
  - `docs/local-probabilistic-operator-runbook.md`
  - `package.json`
  - `playwright.config.mjs`
  - `scripts/ensure-graphiti-live-neo4j.sh`
  - `backend/uv.lock`
  - `backend/app/api/graph.py`
  - `backend/app/api/simulation.py`
  - `backend/app/config.py`
  - `backend/app/services/backtest_manager.py`
  - `backend/app/services/calibration_manager.py`
  - `backend/app/services/ensemble_manager.py`
  - `backend/app/services/evidence_bundle_service.py`
  - `backend/app/services/forecast_manager.py`
  - `backend/app/services/graph_backend/__init__.py`
  - `backend/app/services/graph_backend/live_probe.py`
  - `backend/app/services/graph_backend/neo4j_factory.py`
  - `backend/app/services/graph_backend/scan_service.py`
  - `backend/app/services/graph_entity_reader.py`
  - `backend/app/services/graph_query_tools.py`
  - `backend/app/services/grounding_bundle_builder.py`
  - `backend/app/services/ontology_generator.py`
  - `backend/app/services/probabilistic_report_context.py`
  - `backend/app/services/report_agent.py`
  - `backend/app/services/scenario_clusterer.py`
  - `backend/app/services/sensitivity_analyzer.py`
  - `backend/app/services/simulation_runner.py`
  - `backend/scripts/verify_graphiti_scaffold.py`
  - `backend/scripts/verify_runtime_graph_live.py`
  - `backend/tests/conftest.py`
  - `backend/tests/integration/test_probabilistic_operator_flow.py`
  - `backend/tests/integration/test_structural_uncertainty_handoff.py`
  - `backend/tests/unit/services/graph_backend/test_factory.py`
  - `backend/tests/unit/services/graph_backend/test_live_probe.py`
  - `backend/tests/unit/services/graph_backend/test_settings.py`
  - `backend/tests/unit/test_backend_test_stubs.py`
  - `backend/tests/unit/test_ensemble_storage.py`
  - `backend/tests/unit/test_evidence_grounded_initialization.py`
  - `backend/tests/unit/test_forecast_grounding.py`
  - `backend/tests/unit/test_graph_backend_readiness_api.py`
  - `backend/tests/unit/test_graph_entity_reader.py`
  - `backend/tests/unit/test_graph_query_tools.py`
  - `backend/tests/unit/test_model_routing.py`
  - `backend/tests/unit/test_probabilistic_ensemble_api.py`
  - `backend/tests/unit/test_probabilistic_prepare.py`
  - `backend/tests/unit/test_probabilistic_report_api.py`
  - `backend/tests/unit/test_probabilistic_report_context.py`
  - `backend/tests/unit/test_report_agent_hybrid_retrieval.py`
  - `backend/tests/unit/test_simulation_entity_api.py`
  - `backend/tests/unit/test_simulation_runner_runtime_scope.py`
  - deleted legacy runtime Zep modules and tests listed in Prompt 6
  - chain state files
- verification summary:
  - broad verify: `npm run verify` passed with `401 passed, 1 warning`
  - forecasting verify: `npm run verify:forecasting` passed after rerunning outside the sandbox for Docker helper access
  - smoke verify: `npm run verify:smoke` passed with `10 passed`
  - live operator verify: `PLAYWRIGHT_LIVE_ALLOW_MUTATION=true npm run verify:operator:local` passed with `2 passed (3.1m)`
  - Graphiti ladder: `npm run verify:graphiti:all` passed after repo-truth remediation
  - targeted TDD evidence:
    - `backend/tests/unit/services/graph_backend/test_factory.py` red -> green for the Neo4j auth call
    - `backend/tests/unit/test_simulation_runner_runtime_scope.py` red -> green for run finalization
    - `backend/tests/unit/services/graph_backend/test_live_probe.py` red -> green for managed defaults
    - `backend/tests/unit/test_graph_query_tools.py` red -> green for edge attribute preservation
- deviations from the source plan that were implemented intentionally:
  - the integration wrapper still tells the truth about the real repo `.env`; it does not consume the managed-local defaults
  - smoke/live/operator wrappers do consume the managed-local defaults so the local helper path is operable end to end

## Blockers And Resolutions

- blocker: Ruflo memory storage is blocked by the external `sql.js` dependency
  - status: open
  - resolution: continue in `swarm-task-only` mode; swarm/task orchestration remains usable and is sufficient for this chain
- blocker: direct MCP Ruflo task tools wrote to `/.claude-flow` instead of the repo workspace
  - status: resolved
  - resolution: use `scripts/ruflo-mcp-workspace.sh` and repo-local `npm run verify:ruflo`
- blocker: the Prompt 2 dependency graph had a declared Neo4j version conflict
  - status: resolved
  - resolution: align backend dependency declarations to `neo4j>=5.23.0,<6.0.0`
- blocker: read-side and runtime write paths still depended on Zep across Prompts 3 and 4
  - status: resolved
  - resolution: replace those paths with graph-backed query, scan, namespace, and runtime ingestion services
- blocker: touched graph/report/simulation API consumers still depended on Zep at Prompt 5 start
  - status: resolved
  - resolution: cut those consumers over to the graph-backed services and DTOs
- blocker: the expanded graphiti unit wrapper exposed pytest shared-state issues
  - status: resolved
  - resolution: split `verify:graphiti:unit` into deterministic invocations
- blocker: Prompt 6 repo truth still contained legacy runtime Zep modules and tests
  - status: resolved
  - resolution: delete the runtime Zep modules and legacy Zep tests, remove the `zep_cloud` conftest stub, and replace it with graph-backend-focused harness coverage
- blocker: Neo4j driver initialization used positional auth and failed during live operator coverage
  - status: resolved
  - resolution: call `GraphDatabase.driver` with keyword `auth=...`
- blocker: the simulation runner could mark a run complete before monitor-thread finalization persisted runtime artifacts
  - status: resolved
  - resolution: keep completion/finalization ownership in the monitor path
- blocker: smoke/live wrappers depended on a real repo `.env` graph configuration and were not locally operable by default
  - status: resolved
  - resolution: inject managed-local graph defaults in the smoke/live/operator wrappers and verification probes
- blocker: panorama/history reads dropped edge attributes and could crash on runtime-history probes
  - status: resolved
  - resolution: preserve edge attributes in normalized edge DTOs and use them during panorama/history-style reads
- blocker: the real repo `.env` still omits explicit `NEO4J_PASSWORD`
  - status: open
  - resolution: integration stays honest and reports `configured=false`; smoke/live/operator wrappers use the managed local helper defaults instead
- blocker: `graphiti-core` availability was previously missing
  - status: resolved
  - resolution: Prompt 7 repo truth shows `graphiti-core 0.11.6` available through the backend environment/lock state and the live ladder now builds the Graphiti client successfully

## Verification Command Ledger

- `git branch --show-current`
  - result: `codex/graphiti-neo4j-overhaul-chain`
- `git status --short`
  - result: baseline dirty paths remained the same; Prompt 7 work stayed on chain-owned paths
- `npm run verify:ruflo`
  - result: PASS in `swarm-task-only` mode; memory still blocked by external `sql.js`
- Prompt 1 scoped tests:
  - `backend/.venv/bin/python -m pytest backend/tests/unit/services/graph_backend/test_settings.py backend/tests/unit/services/graph_backend/test_factory.py backend/tests/unit/test_graph_backend_readiness_api.py -q`
  - result before implementation: `4 failed`
  - result after implementation: `4 passed`
- Prompt 2 scoped tests:
  - `backend/.venv/bin/python -m pytest backend/tests/unit/services/graph_backend/test_namespace_manager.py backend/tests/unit/services/graph_backend/test_ontology_compiler.py backend/tests/unit/services/graph_backend/test_factory.py backend/tests/unit/test_graph_builder_service.py -q`
  - result before implementation: `5 failed`
  - result after implementation: `11 passed`
- Prompt 3 scoped tests:
  - `backend/.venv/bin/python -m pytest backend/tests/unit/services/graph_backend/test_scan_service.py backend/tests/unit/services/graph_backend/test_query_service.py backend/tests/unit/test_zep_entity_reader.py backend/tests/unit/test_zep_tools_multigraph.py backend/tests/unit/test_report_agent_hybrid_retrieval.py -q`
  - result before implementation: `5 failed, 6 passed`
  - result after implementation: `11 passed`
- Prompt 4 scoped tests:
  - `backend/.venv/bin/python -m pytest backend/tests/unit/test_runtime_graph_state.py backend/tests/unit/services/graph_backend/test_runtime_event_ingestor.py backend/tests/unit/test_runtime_graph_updater.py backend/tests/unit/test_simulation_runner_runtime_scope.py -q`
  - result before implementation: `6 failed, 8 passed`
  - result after implementation: `14 passed`
- Prompt 5 scoped tests:
  - `backend/.venv/bin/python -m pytest backend/tests/unit/test_graph_data_api.py backend/tests/unit/test_report_api_graph_tools.py backend/tests/unit/test_report_agent_hybrid_retrieval.py backend/tests/unit/test_simulation_entity_api.py backend/tests/unit/test_evidence_grounded_initialization.py -q`
  - result before implementation: `6 failed, 6 passed`
  - result after implementation: `12 passed`
- Prompt 7 targeted red/green tests:
  - `backend/.venv/bin/python -m pytest backend/tests/unit/services/graph_backend/test_factory.py -q`
    - result before implementation: failing Neo4j auth factory test
    - result after implementation: `2 passed`
  - `backend/.venv/bin/python -m pytest backend/tests/unit/test_simulation_runner_runtime_scope.py -q`
    - result before implementation: failing run-finalization test
    - result after implementation: `10 passed`
  - `backend/.venv/bin/python -m pytest backend/tests/unit/services/graph_backend/test_live_probe.py backend/tests/unit/services/graph_backend/test_factory.py backend/tests/unit/test_simulation_runner_runtime_scope.py -q`
    - result: `14 passed`
  - `backend/.venv/bin/python -m pytest backend/tests/unit/services/graph_backend/test_live_probe.py backend/tests/unit/test_graph_query_tools.py backend/tests/unit/services/graph_backend/test_factory.py backend/tests/unit/test_simulation_runner_runtime_scope.py -q`
    - result: `20 passed`
- Prompt 7 broader regression tests:
  - `backend/.venv/bin/python -m pytest backend/tests/unit/test_probabilistic_ensemble_api.py backend/tests/unit/test_probabilistic_report_api.py backend/tests/unit/test_report_agent_hybrid_retrieval.py -q`
    - result: `67 passed`
- broad repo verify:
  - `npm run verify`
  - result: PASS with `401 passed, 1 warning`
- forecasting verify:
  - `npm run verify:forecasting`
  - result: PASS after rerunning outside the sandbox for Docker helper access
- smoke verify:
  - `npm run verify:smoke`
  - result: PASS with `10 passed`
- live operator verify:
  - `PLAYWRIGHT_LIVE_ALLOW_MUTATION=true npm run verify:operator:local`
  - result: PASS with `2 passed (3.1m)`
- Graphiti ladder:
  - `npm run verify:graphiti:all`
  - result: PASS
  - notes:
    - unit wrapper passed across both deterministic pytest invocations
    - integration wrapper passed while honestly reporting the real repo `.env` gap for `NEO4J_PASSWORD`
    - smoke wrapper passed with managed-local defaults and helper-backed Neo4j
    - live wrapper passed with `graphiti_client_built=true`, `neo4j_healthcheck=true`, and panorama runtime-history coverage

## Next-Prompt Entry Checklist

- re-read the source plan, prompt-chain doc, this ledger, the chain status JSON, and the baseline dirty manifest
- confirm the active branch still matches the chain status branch
- confirm no baseline dirty path has been staged or adopted accidentally
- verify Prompt 1-5 commits still exist in `git log`
- verify the Prompt 7 commit exists and note that Prompt 6 repo-truth remediation is intentionally captured there
- re-run `npm run verify:ruflo` and continue in `swarm-task-only` mode unless `sql.js` has been remediated
- re-check `npm run verify`, `npm run verify:forecasting`, `npm run verify:smoke`, `PLAYWRIGHT_LIVE_ALLOW_MUTATION=true npm run verify:operator:local`, and `npm run verify:graphiti:all` only if Prompt 8 finds drift from the recorded outputs
- confirm `/api/graph/backend/readiness` and `/api/graph/backend/capabilities` still match the documented operator contract
- confirm the real repo `.env` gap for `NEO4J_PASSWORD` is still either explicitly fixed or still honestly reported as an integration-only readiness gap
- confirm no runtime path or operator doc still assumes Zep services, Zep credentials, or Zep test stubs
- audit the branch for merge readiness, residual risk, and any remaining cleanup that should block mainline integration
