# Graphiti + Neo4j Cutover Chain Ledger

## Branch

- active branch: `codex/graphiti-neo4j-overhaul-chain`

## Baseline Dirty Policy

- treat `docs/plans/2026-03-31-graphiti-neo4j-baseline-dirty.txt` as the authoritative pre-chain dirty manifest
- do not stage or revert any path listed in that manifest unless the chain explicitly adopts it
- if a later prompt adopts a baseline path, record the adoption and reason in this ledger before staging it

## Chain-Owned Path Policy

- Prompt 1 may create or modify only chain-owned harness paths plus the minimal repo surfaces needed to expose and verify that harness
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
- Prompt 2 may extend the backend core and base graph build path while preserving Prompt 1 chain state files
- Prompt 2 chain-owned paths:
  - `.env.example`
  - `README.md`
  - `docs/local-probabilistic-operator-runbook.md`
  - `package.json`
  - `backend/pyproject.toml`
  - `backend/requirements.txt`
  - `backend/app/api/graph.py`
  - `backend/app/services/graph_builder.py`
  - `backend/app/services/graph_backend/`
  - `backend/scripts/verify_graphiti_scaffold.py`
  - `backend/tests/unit/services/graph_backend/`
  - `backend/tests/unit/test_graph_builder_service.py`
  - `docs/plans/2026-03-31-graphiti-neo4j-chain.md`
  - `docs/plans/2026-03-31-graphiti-neo4j-chain-status.json`
- Prompt 3 may extend the read-side graph query stack, deterministic scans, multigraph runtime/base reads, and report/entity adapters while preserving earlier chain state files
- Prompt 3 chain-owned paths:
  - `backend/app/services/graph_backend/__init__.py`
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
  - `docs/plans/2026-03-31-graphiti-neo4j-chain.md`
  - `docs/plans/2026-03-31-graphiti-neo4j-chain-status.json`

## Commit Policy

- commit at the end of every prompt
- stage only chain-owned paths for the active prompt
- never stage baseline dirty paths unless the ledger records an adoption entry
- use one focused commit per prompt with the prompt-scoped message contract

## Prompt-By-Prompt Progress Log

### Prompt 1

- status: completed
- scope: branch/bootstrap state, chain files, Graphiti/Neo4j verification wrappers, initial backend scaffolding, and Prompt 1 TDD harness
- startup grounding completed against:
  - `docs/plans/2026-03-31-graphiti-neo4j-overhaul.md`
  - `docs/plans/2026-03-31-graphiti-neo4j-cutover-prompt-chain.md`
  - `README.md`
  - `docs/local-probabilistic-operator-runbook.md`
  - `package.json`
  - `backend/pyproject.toml`
  - current Zep/graph touchpoints across backend, docs, and tests
- startup branch/remote snapshot:
  - initial branch before cutover: `main`
  - remote: `origin https://github.com/bcdannyboy/MiroFishES`
- Ruflo orchestration records:
  - workspace verifier result: `swarm-task-only`
  - workspace launcher swarm id: `swarm-1775016400679-6itc00`
  - docs/state task id: `task-1775016400681-a68yxm`
  - backend harness task id: `task-1775016400681-qtb8ld`
- owned files actually changed:
  - `.env.example`
  - `README.md`
  - `docs/local-probabilistic-operator-runbook.md`
  - `package.json`
  - `backend/pyproject.toml`
  - `backend/requirements.txt`
  - `backend/app/config.py`
  - `backend/app/api/graph.py`
  - `backend/app/services/graph_backend/__init__.py`
  - `backend/app/services/graph_backend/errors.py`
  - `backend/app/services/graph_backend/types.py`
  - `backend/app/services/graph_backend/settings.py`
  - `backend/app/services/graph_backend/graphiti_factory.py`
  - `backend/app/services/graph_backend/neo4j_factory.py`
  - `backend/scripts/verify_graphiti_scaffold.py`
  - `backend/tests/unit/services/graph_backend/test_settings.py`
  - `backend/tests/unit/services/graph_backend/test_factory.py`
  - `backend/tests/unit/test_graph_backend_readiness_api.py`
  - `docs/plans/2026-03-31-graphiti-neo4j-baseline-dirty.txt`
  - `docs/plans/2026-03-31-graphiti-neo4j-chain.md`
  - `docs/plans/2026-03-31-graphiti-neo4j-chain-status.json`
- architectural decisions implemented:
  - added a dedicated `app.services.graph_backend` scaffold instead of touching the live Zep call graph prematurely
  - exposed one truthful readiness surface at `GET /api/graph/backend/readiness`
  - kept Graphiti and Neo4j factories deferred so Prompt 1 proves config/dependency state without pretending the cutover is already live
  - added repo-native `verify:graphiti:*` wrappers that stay green when the harness executes and reports honest readiness gaps
- deviations from the source plan that were intentional in Prompt 1:
  - retained `zep-cloud` because the runtime still depends on legacy Zep services and Prompt 1 does not yet rewrite those call sites
  - wrapper integration/smoke/live checks remain scaffold-level sanity probes; they are not yet end-to-end Graphiti backend tests
- completion summary:
  - failing tests were written first, observed red, implemented to green, and then wrapped in repo-native verification commands
  - docs were updated to describe the new Graphiti scaffold env vars and wrapper commands without claiming live cutover completion

### Prompt 2

- status: completed
- scope: internal graph backend core, deterministic namespace/ontology services, Neo4j-backed export path, and base graph build cutover off Zep
- startup grounding completed against:
  - `docs/plans/2026-03-31-graphiti-neo4j-overhaul.md`
  - `docs/plans/2026-03-31-graphiti-neo4j-cutover-prompt-chain.md`
  - `docs/plans/2026-03-31-graphiti-neo4j-chain.md`
  - `docs/plans/2026-03-31-graphiti-neo4j-chain-status.json`
  - `docs/plans/2026-03-31-graphiti-neo4j-baseline-dirty.txt`
- startup branch/status snapshot:
  - active branch confirmed: `codex/graphiti-neo4j-overhaul-chain`
  - dirty state re-grounded before work; only baseline dirty files were present outside chain-owned edits
- Ruflo orchestration records:
  - workspace verifier result: `swarm-task-only`
  - workspace launcher swarm id: `swarm-1775017143885-pestw3`
  - backend core task id: `task-1775017143887-79ab02`
  - graph build task id: `task-1775017143888-c6070b`
  - docs/status task id: `task-1775017143888-peuzfw`
- Prompt 1 gap remediation completed before new scope:
  - verified Prompt 1 unit and integration wrapper claims from repo truth
  - fixed the inherited backend dependency pin mismatch by aligning `neo4j` to `>=5.23.0,<6.0.0` so `graphiti-core` and `camel-oasis` no longer conflict at the declared dependency layer
- owned files actually changed:
  - `.env.example`
  - `README.md`
  - `docs/local-probabilistic-operator-runbook.md`
  - `package.json`
  - `backend/pyproject.toml`
  - `backend/requirements.txt`
  - `backend/app/api/graph.py`
  - `backend/app/services/graph_builder.py`
  - `backend/app/services/graph_backend/__init__.py`
  - `backend/app/services/graph_backend/backend.py`
  - `backend/app/services/graph_backend/export_service.py`
  - `backend/app/services/graph_backend/graphiti_factory.py`
  - `backend/app/services/graph_backend/ingestion_service.py`
  - `backend/app/services/graph_backend/namespace_manager.py`
  - `backend/app/services/graph_backend/neo4j_factory.py`
  - `backend/app/services/graph_backend/ontology_compiler.py`
  - `backend/app/services/graph_backend/settings.py`
  - `backend/app/services/graph_backend/types.py`
  - `backend/scripts/verify_graphiti_scaffold.py`
  - `backend/tests/unit/services/graph_backend/test_factory.py`
  - `backend/tests/unit/services/graph_backend/test_namespace_manager.py`
  - `backend/tests/unit/services/graph_backend/test_ontology_compiler.py`
  - `backend/tests/unit/test_graph_builder_service.py`
  - `docs/plans/2026-03-31-graphiti-neo4j-chain.md`
  - `docs/plans/2026-03-31-graphiti-neo4j-chain-status.json`
- architectural decisions implemented:
  - introduced a dedicated `GraphitiGraphBackend` seam that owns namespace creation, ontology registration, ingestion dispatch, and export delegation
  - implemented deterministic namespace policy through `GraphNamespaceManager`, treating base and runtime graph ids as application-managed namespace ids
  - implemented `GraphOntologyCompiler` to convert the current ontology JSON shape into Pydantic models plus an explicit `(source, target) -> edge_names` map
  - upgraded the Graphiti factory from deferred metadata to a lazy OpenAI-compatible client builder and upgraded the Neo4j factory to a lazy sync driver builder with healthcheck support
  - implemented `Neo4jGraphExportService` so build artifacts derive from normalized Neo4j node/edge exports instead of Zep paging
  - rewrote `GraphBuilderService` and `/api/graph/build` so the Step 1 base graph build path no longer depends on `zep_cloud` or `ZEP_API_KEY`
- deviations from the source plan that were intentional in Prompt 2:
  - `verify:graphiti:integration`, `smoke`, and `live` remain readiness/harness checks because `graphiti-core` is still absent locally and the repo `.env` still lacks `NEO4J_PASSWORD`
  - export normalization uses direct Neo4j queries rather than a Graphiti-side export API because that preserves the current artifact field contract with less vendor-specific coupling
- completion summary:
  - failing Prompt 2 tests were written first and observed red before implementation
  - the base graph build code path now runs through the new backend seam, while downstream read/query/runtime update surfaces remain explicitly deferred to later prompts

### Prompt 3

- status: completed
- scope: backend-neutral read-side graph query stack, deterministic scans, multigraph `base_graph_id` + `runtime_graph_id` reads, and report/entity adapters off the legacy Zep client path
- startup grounding completed against:
  - `docs/plans/2026-03-31-graphiti-neo4j-overhaul.md`
  - `docs/plans/2026-03-31-graphiti-neo4j-cutover-prompt-chain.md`
  - `docs/plans/2026-03-31-graphiti-neo4j-chain.md`
  - `docs/plans/2026-03-31-graphiti-neo4j-chain-status.json`
  - `docs/plans/2026-03-31-graphiti-neo4j-baseline-dirty.txt`
- startup branch/status snapshot:
  - active branch confirmed: `codex/graphiti-neo4j-overhaul-chain`
  - dirty state re-grounded before work; only baseline dirty files were present outside chain-owned edits
- Ruflo orchestration records:
  - workspace verifier result: `swarm-task-only`
  - workspace launcher swarm id: `swarm-1775019134311-1a0jrw`
  - query/scan task id: `task-1775019134313-7u6tea`
  - entity-reader task id: `task-1775019134313-055lzi`
  - report-adapter task id: `task-1775019134313-zwp74t`
- Prompt 1 and Prompt 2 repo-truth verification completed before new scope:
  - `git log` confirmed both prompt commits on the active branch
  - `npm run verify:graphiti:unit` and `npm run verify:graphiti:integration` both matched the earlier chain claims before Prompt 3 edits began
- owned files actually changed:
  - `backend/app/services/graph_backend/__init__.py`
  - `backend/app/services/graph_backend/query_service.py`
  - `backend/app/services/graph_backend/scan_service.py`
  - `backend/app/services/zep_entity_reader.py`
  - `backend/app/services/zep_tools.py`
  - `backend/app/utils/graph_scan.py`
  - `backend/tests/unit/services/graph_backend/test_query_service.py`
  - `backend/tests/unit/services/graph_backend/test_scan_service.py`
  - `backend/tests/unit/test_report_agent_hybrid_retrieval.py`
  - `backend/tests/unit/test_zep_entity_reader.py`
  - `backend/tests/unit/test_zep_tools_multigraph.py`
  - `docs/plans/2026-03-31-graphiti-neo4j-chain.md`
  - `docs/plans/2026-03-31-graphiti-neo4j-chain-status.json`
- architectural decisions implemented:
  - introduced `GraphScanService` under `app.services.graph_backend` to load deterministic node/edge scans from persisted project graph artifacts plus runtime transition artifacts without vendor SDKs
  - introduced `GraphQueryService` under `app.services.graph_backend` for normalized node reads, node-edge reads, graph statistics, entity summaries, simulation context, and deterministic keyword search across merged graphs
  - replaced the live Zep dependency inside `zep_entity_reader.py` with artifact-backed scans while preserving the artifact-first `graph_entity_index.json` fast path for single-graph project reads
  - replaced the live Zep dependency inside `zep_tools.py` with the new query service while preserving the existing report-facing tool contract and hybrid evidence/interview surfaces
  - treated runtime graph updates as temporal history edges, keeping panorama/history-style reads aware of runtime transitions when `runtime_graph_id` is present
  - kept the public read-side module names stable for Prompt 3 so report/simulation code paths do not need a parallel rename while the underlying behavior is already backend-neutral
- deviations from the source plan that were intentional in Prompt 3:
  - retained compatibility module names `zep_tools.py` and `zep_entity_reader.py` even though their implementations no longer rely on the Zep client, to minimize blast radius for downstream prompts
  - deterministic search remains artifact-backed keyword retrieval for now; live Graphiti query execution still depends on the unresolved `graphiti-core` installation and `NEO4J_PASSWORD` env gap
- blockers fixed from prior prompts:
  - removed the Prompt 2-era runtime dependency on `ZEP_API_KEY` for read-side search/entity/report paths touched in Prompt 3
- completion summary:
  - failing Prompt 3 tests were written first and observed red before implementation
  - merged base/runtime reads, deterministic scans, report quick search, and entity-context enrichment now run through the new backend-neutral read stack

## Blockers And Resolutions

- blocker: direct MCP Ruflo task tools in this session wrote to `/.claude-flow` instead of the repo workspace
  - resolution: use the repo-local launcher `scripts/ruflo-mcp-workspace.sh`; verifier and manual JSON-RPC task creation both succeeded there
- blocker: Ruflo memory storage remains blocked by the external `sql.js` dependency
  - resolution: proceed in `swarm-task-only` mode as allowed by the prompt and record that memory is not available for the chain
- blocker: sandboxed localhost socket probes reported `Operation not permitted`
  - resolution: rerun the non-secret Neo4j probe outside the sandbox; both `127.0.0.1:7687` and `127.0.0.1:7474` were reachable
- blocker: the current local repo `.env` does not expose `NEO4J_PASSWORD`, so the in-repo readiness surface truthfully reports `configured=false`
  - resolution: leave the user’s `.env` untouched in Prompt 1 and record the gap for later prompts that need live Graphiti execution
- blocker: `graphiti-core` is not installed in the current backend environment
  - resolution: leave the wrapper verdict honest and keep Prompt 1 limited to deferred scaffolding until a later prompt installs or vendors the dependency
- blocker: declared `neo4j` version range conflicted with `camel-oasis` transitive expectations during Prompt 2 environment recheck
  - resolution: align `backend/pyproject.toml` and `backend/requirements.txt` to `neo4j>=5.23.0,<6.0.0`, which satisfies the current repo dependency graph while keeping the Graphiti cutover path viable
- blocker: Prompt 3 needed multigraph reads before live Graphiti query dependencies are locally runnable
  - resolution: implement artifact-backed deterministic scan/query services so the read path no longer depends on Zep while the live Graphiti runtime blockers remain open

## Verification Command Ledger

- `git branch --show-current`
  - result: `main` before branch creation
- `git status --short`
  - result: captured exactly in `docs/plans/2026-03-31-graphiti-neo4j-baseline-dirty.txt`
- `git remote -v`
  - result: `origin https://github.com/bcdannyboy/MiroFishES` for fetch and push
- `[ -f .env ] && echo present || echo missing`
  - result: `present`
- `npm run verify:ruflo`
  - result: PASS in `swarm-task-only` mode; memory blocked by external `sql.js`
- `python3 -c 'socket probe'` outside sandbox
  - result: `127.0.0.1:7687 reachable`, `127.0.0.1:7474 reachable`
- `git switch -c codex/graphiti-neo4j-overhaul-chain`
  - result: branch created and active
- `backend/.venv/bin/python -m pytest backend/tests/unit/services/graph_backend/test_settings.py backend/tests/unit/services/graph_backend/test_factory.py backend/tests/unit/test_graph_backend_readiness_api.py -q`
  - result before implementation: `4 failed`
  - result after implementation: `4 passed`
- `npm run verify:graphiti:all`
  - result: PASS; unit tests green and integration/smoke/live wrappers executed the readiness surface with truthful `configured=false` / `ready=false` output
- `backend/.venv/bin/python -m pytest backend/tests/unit/test_model_routing.py backend/tests/unit/test_graph_data_api.py backend/tests/unit/test_graph_builder_service.py -q`
  - result: `13 passed`
- `backend/.venv/bin/python -m pytest backend/tests/unit/services/graph_backend/test_namespace_manager.py backend/tests/unit/services/graph_backend/test_ontology_compiler.py backend/tests/unit/services/graph_backend/test_factory.py backend/tests/unit/test_graph_builder_service.py -q`
  - result before implementation: `5 failed`
  - result after implementation: `11 passed`
- `npm run verify:graphiti:unit`
  - result: PASS; `14 passed`
- `npm run verify:graphiti:integration`
  - result: PASS; readiness surface reported `configured=false` because `NEO4J_PASSWORD` is still absent and `ready=false` because `graphiti-core` is still not installed
- `backend/.venv/bin/python -m pytest backend/tests/unit/test_forecast_grounding.py backend/tests/unit/test_graph_data_api.py backend/tests/unit/test_runtime_graph_state.py backend/tests/integration/test_runtime_graph_state_flow.py -q`
  - result: `11 passed`
- `npm run verify:graphiti:all`
  - result: PASS; unit plus wrapper sanity checks stayed green after the base build cutover
- `backend/.venv/bin/python -m pytest backend/tests/unit/services/graph_backend/test_settings.py backend/tests/unit/services/graph_backend/test_factory.py backend/tests/unit/services/graph_backend/test_namespace_manager.py backend/tests/unit/services/graph_backend/test_ontology_compiler.py backend/tests/unit/test_graph_backend_readiness_api.py backend/tests/unit/test_graph_builder_service.py backend/tests/unit/test_forecast_grounding.py backend/tests/unit/test_graph_data_api.py backend/tests/unit/test_runtime_graph_state.py backend/tests/integration/test_runtime_graph_state_flow.py -q`
  - result: `25 passed`
- `npm run verify:ruflo`
  - result on Prompt 3 recheck: PASS in `swarm-task-only` mode; memory still blocked by external `sql.js`
- `backend/.venv/bin/python -m pytest backend/tests/unit/services/graph_backend/test_scan_service.py backend/tests/unit/services/graph_backend/test_query_service.py backend/tests/unit/test_zep_entity_reader.py backend/tests/unit/test_zep_tools_multigraph.py backend/tests/unit/test_report_agent_hybrid_retrieval.py -q`
  - result before implementation: `5 failed, 6 passed`
  - result after implementation: `11 passed`
- `npm run verify:graphiti:unit`
  - result on Prompt 3 post-implementation run: `14 passed`
- `npm run verify:graphiti:integration`
  - result on Prompt 3 post-implementation run: PASS; readiness remained honest with `graphiti-core` unavailable and `NEO4J_PASSWORD` missing
- `npm run verify:graphiti:smoke`
  - result on Prompt 3 post-implementation run: PASS; readiness remained honest with `graphiti-core` unavailable and `NEO4J_PASSWORD` missing
- `backend/.venv/bin/python -m pytest backend/tests/unit/test_probabilistic_report_api.py backend/tests/integration/test_runtime_graph_state_flow.py -q`
  - result: `29 passed`
- `backend/.venv/bin/python -m pytest backend/tests/unit/test_probabilistic_prepare.py -q`
  - result: `31 passed`

## Next-Prompt Entry Checklist

- re-read the source plan, prompt-chain doc, chain ledger, chain status JSON, and baseline dirty manifest
- confirm the active branch matches the chain status branch
- confirm baseline dirty paths remain unstaged unless explicitly adopted
- verify Prompt 1 and Prompt 2 commits exist and review their scoped verification evidence
- verify Prompt 3 commit exists and review its scoped verification evidence
- re-run Ruflo workspace readiness before new disjoint work
- expect `graphiti-core` to still be absent and `NEO4J_PASSWORD` to still be missing unless Prompt 3 explicitly changes the environment/install state
- confirm the Step 1 base graph build path now runs through `backend/app/services/graph_backend/` and that `/api/graph/build` no longer gates on `ZEP_API_KEY`
- confirm the read-side search/entity/report paths touched in Prompt 3 no longer require live Zep credentials
- treat the remaining write-side graph memory updater/runtime mutation Zep paths as Prompt 4+ scope
