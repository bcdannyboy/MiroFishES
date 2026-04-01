# MiroFishES

MiroFishES keeps the original MiroFish graph -> simulation -> report -> interaction flow, but it also adds a bounded forecasting layer built from persisted artifacts, stored Step 3 run shells, and scoped report context.

That newer path is only as strong as the artifacts and verification behind it. When those are missing or blocked, the repo should be treated as the legacy single-run simulation app plus some forecast-oriented sidecars, not as a stronger forecasting system than the code supports.

## What This Repo Actually Adds

- Step 2 can prepare forecast-oriented artifacts instead of only transient setup state.
- Step 2 handoff can create or reopen stored Step 3 run shells instead of launching a run immediately.
- Step 4 and the Report Agent lane in Step 5 can consume explicit `ensemble`, `cluster`, or `run` scope.
- The repo can persist source-unit grounding, prepared world and agent state, structured runtime state, simulation-market artifacts, scenario clusters, designed-comparison sensitivity, backtests, and calibration artifacts.
- History can reopen saved probabilistic Step 3, Step 4, and Step 5 state when the required scope metadata exists.

## What It Still Does Not Truthfully Add

- comprehensive research grounding
- exhaustive code-analysis grounding
- causal scenario analysis
- broad calibrated forecasting beyond the supported evaluated binary, categorical, and numeric answer lanes with validated provenance
- release-grade live operator proof

## Current Boundaries

- Upstream grounding is limited to uploaded project artifacts, graph-build outputs, and repo-local code-analysis only when that evidence was actually attached to `grounding_bundle.json`.
- Step 2 proves artifact preparation and workflow handoff eligibility. It does not prove report quality, forecast certainty, or calibrated confidence.
- Step 3 shows one stored shell and its recovery actions. A prepared shell stays passive until the operator launches it.
- Step 4 adds empirical, regime-aware, and designed-comparison-aware context around the legacy report body.
- Step 5 makes only the Report Agent lane scope-aware and answer-confidence-aware. Interviews and surveys remain legacy-scoped.
- `answer_confidence_status.status` can be `absent`, `not_ready`, or `ready`. `ready` requires valid calibration and backtest artifacts plus provenance that links calibration back to the saved backtest artifact.

## Workflow And Evidence Terms

- `artifact completeness`: the required Step 2 probabilistic files exist. In practice that means `forecast_brief.json`, `grounding_bundle.json`, `uncertainty_spec.json`, `outcome_spec.json`, and `prepared_snapshot.json`.
- `grounding attachment status`: `grounding_bundle.json` exists and its `status` is `ready` only when upstream grounding was actually attached.
- `workflow handoff status`: the Step 2 stored-run handoff gate. It passes only when artifact completeness and grounding attachment status both pass.
- `confidence gate status`: the Step 4 and Step 5 calibration gate. It passes only when the supported answer lane carries type-correct backtest and calibration artifacts and the calibration provenance matches the stored backtest artifact.

## Docs Map

- [Docs index](docs/README.md): short reading guide
- [What MiroFishES adds](docs/what-mirofishes-adds.md): plain-language fork delta
- [Local probabilistic operator runbook](docs/local-probabilistic-operator-runbook.md): local Step 1 through Step 5 operating guide
- [Forecast readiness chain ledger](docs/plans/2026-03-31-forecast-readiness-chain.md): current implementation contract, handoffs, and final readiness evidence
- [Forecast readiness status](docs/plans/2026-03-31-forecast-readiness-status.json): machine-readable phase status and verification record
- [North-star forecast upgrades](docs/plans/2026-03-28-mirofish-high-impact-forecasting-upgrades.md): historical ambition, not current contract

## Repository Layout

- `frontend/`: Vite/Vue UI and browser tests
- `backend/`: Flask APIs, simulation services, artifacts, and pytest suites
- `docs/`: front-door docs, runbooks, and historical plans
- `static/`: static assets used by the app

## Quick Start

### Prerequisites

| Tool | Version | Purpose | Check |
| --- | --- | --- | --- |
| `node` | 18+ | frontend runtime and package management | `node -v` |
| `python` | 3.11 to 3.12 | backend runtime | `python --version` |
| `uv` | latest | Python dependency management | `uv --version` |

### Install dependencies

```bash
npm run setup:all
npx playwright install chromium
```

### Configure live environment

```bash
cp .env.example .env
```

For real local Step 2 through Step 5 use, the backend needs a real LLM key, the probabilistic flags, and a reachable Neo4j CE instance. No Zep keys are used.

```env
LLM_API_KEY=your_api_key_here

PROBABILISTIC_PREPARE_ENABLED=true
PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED=true
PROBABILISTIC_REPORT_ENABLED=true
PROBABILISTIC_INTERACTION_ENABLED=true

CALIBRATED_PROBABILITY_ENABLED=false
```

The backend reads the repo-root `.env` from `backend/app/config.py`. Those rollout flags default to `false`, so a fresh local environment does not expose the bounded forecast path unless you opt in.

The simplest local Graphiti + Neo4j CE flow is to start the managed helper container first:

```bash
sh ./scripts/ensure-graphiti-live-neo4j.sh
```

With that helper running, use these graph-backend values:

```env
GRAPH_BACKEND=graphiti_neo4j
NEO4J_URI=bolt://127.0.0.1:17687
NEO4J_USER=neo4j
NEO4J_PASSWORD=mirofish-graphiti-live
GRAPHITI_EXTRACTION_MODEL=gpt-4.1-mini
GRAPHITI_EMBEDDING_MODEL=text-embedding-3-small
GRAPH_BACKEND_BATCH_SIZE=3
GRAPH_BACKEND_SEARCH_LIMIT=12
GRAPH_BACKEND_SCAN_LIMIT=250
GRAPH_BACKEND_RUNTIME_BATCH_SIZE=25
```

If you already run your own Neo4j instance, keep `GRAPH_BACKEND=graphiti_neo4j` and override `NEO4J_URI`, `NEO4J_USER`, and `NEO4J_PASSWORD` accordingly.

The Step 1 base build, read/query path, runtime update path, and the active graph/report/simulation consumer lanes now run through the Graphiti + Neo4j backend seam. No runtime Zep services or Zep credentials are required.

### Start the stack

```bash
sh ./scripts/ensure-graphiti-live-neo4j.sh
npm run dev
```

Default endpoints:

- frontend: `http://localhost:5173`
- backend: `http://localhost:5001`

### Check readiness and capabilities

```bash
curl -sS http://127.0.0.1:5001/health | jq .
curl -sS http://127.0.0.1:5001/api/graph/backend/readiness | jq .
curl -sS http://127.0.0.1:5001/api/graph/backend/capabilities | jq .
curl -sS http://127.0.0.1:5001/api/simulation/prepare/capabilities | jq .
```

For the graph backend checks, expect:

- `/api/graph/backend/readiness` to report `backend=graphiti_neo4j`
- `/api/graph/backend/capabilities` to report merged base/runtime namespace reads and the `verify:graphiti:*` ladder

For the bounded probabilistic path, these booleans from `/api/simulation/prepare/capabilities` should be `true`:

- `probabilistic_prepare_enabled`
- `probabilistic_ensemble_storage_enabled`
- `probabilistic_report_enabled`
- `probabilistic_interaction_enabled`

## Fresh Local Forecast Path

1. Create a project in the UI.
2. Upload source material and complete Step 1 graph build.
3. Enter Step 2 and stay in `Forecast` mode when probabilistic prepare is available.
4. Run forecast prepare. This writes or refreshes the Step 2 control artifacts. It does not launch a run.
5. Use the Step 2 handoff to create or reopen a stored Step 3 shell.
6. In Step 3, choose a shell and launch it only when you are ready to run it.
7. Generate or reopen a scoped report in Step 4, then use Step 5 against that saved report context.

Important limits:

- `PLAYWRIGHT_LIVE_SIMULATION_ID` is only for the live Playwright harness. A manual local run does not need it.
- A truthful fresh forecast path still depends on uploaded source material. Blank simulations are not a real forecast workflow here.
- If Step 2 helper text says handoff is blocked, treat that as the real gate. The UI copy is wired to backend readiness and artifact checks.

## Verification Ladder

Run these from the repo root when you want evidence instead of intuition.

### 1. Broad repo verify

```bash
npm run verify
```

This runs frontend unit tests, the frontend production build, and backend pytest. It proves code and build health in the current worktree. It does not inspect persisted forecast artifacts or browser routing.

### 2. Targeted non-binary verify

```bash
npm run verify:nonbinary
```

Use this when the change touches the active typed forecast path for `binary`, `categorical`, or `numeric` questions and you want the narrowest backend plus runtime signal before running the broader wrappers.

### Graphiti scaffold verify

```bash
npm run verify:graphiti:unit
npm run verify:graphiti:integration
npm run verify:graphiti:smoke
npm run verify:graphiti:live
npm run verify:graphiti:all
```

These wrappers prove the Graphiti + Neo4j backend seam exists, that the readiness and capabilities surfaces execute, and that the repo can run the rewritten base plus runtime unit/integration tests plus smoke/live probes. The smoke, live, and local operator wrappers automatically start the managed local Neo4j CE helper and inject the managed local graph defaults when the real `.env` omits them. The integration wrapper stays stricter and reports the actual repo `.env` state without those managed fallbacks.

The Prompt 5 unit wrapper now also covers the graph API multigraph read contract, report graph-query tools, simulation entity endpoints, and graph-backed consumer scaffolding.

For an explicit runtime live probe against the current repo `.env` plus the managed local Neo4j binding, run:

```bash
backend/.venv/bin/python backend/scripts/verify_runtime_graph_live.py
```

### 3. Confidence verify

```bash
npm run verify:confidence
```

Use this when the change touches confidence, backtests, calibration, report context, or Step 2 through Step 5 copy that depends on those states. This is the narrow contract for `answer_confidence_status`, provenance, and artifact-gated wording.

### 4. Forecasting verify

```bash
npm run verify:forecasting
```

This wrapper runs five surfaces in order:

1. `npm run verify`
2. `npm run verify:nonbinary`
3. `npm run verify:confidence`
4. `npm run verify:forecasting:artifacts`
5. `npm run verify:smoke`

It is the broad non-mutating forecasting check.

### 5. Fixture-backed smoke verify

```bash
npm run verify:smoke
```

This suite boots a local backend and frontend with Playwright-owned env overrides from `playwright.config.mjs`, seeds deterministic fixture data, and checks the bounded Step 2 through Step 5 browser path.

It covers:

- Step 2 prepared artifact summary
- honest blocked Step 3 handoff copy
- stored Step 3 shell rendering and analytics
- Step 4 observed report context and compare workspace
- Step 5 scoped evidence banner and compare handoff
- history replay back into Step 3 and Step 5

It does not prove live LLM access, authenticated live Graphiti ingestion against a custom external Neo4j deployment, live Step 2 prepare, or live Report Agent chat responses.
It does start the managed local Neo4j helper and use the same managed local graph defaults as `verify:graphiti:smoke` and `verify:graphiti:live`.

### 6. Live mutating operator verify

```bash
PLAYWRIGHT_LIVE_ALLOW_MUTATION=true npm run verify:operator:local
```

This suite mutates a real local simulation family. Only run it when that is explicitly acceptable.

It exercises:

- Step 2 handoff
- Step 3 launch, stop, retry, cleanup, and child rerun
- Step 4 probabilistic report generation on a real saved scope
- Step 4 compare handoff into Step 5
- one real Step 5 Report Agent message against a saved live report context

If `PLAYWRIGHT_LIVE_SIMULATION_ID` is unset, Step 2/3 uses the newest non-archived prepared-and-grounded local simulation, while the live Step 4/5 path prefers the newest prepared-and-grounded simulation family that already has completed ready run-scoped evidence. Archived records and smoke fixtures are skipped automatically.

## Historical Artifact Policy

Active forecasting evidence and historical evidence are intentionally separated.

- `npm run verify:forecasting:artifacts` scans active non-archived simulations only.
- `npm run verify:forecasting:artifacts:all` scans the full backlog, including archived records.
- `npm run forecasting:archive:historical` writes `forecast_archive.json` markers for saved simulations that no longer satisfy the current active contract.
- Archived simulations remain readable on disk and through explicit history requests such as `/api/simulation/history?include_archived=true`, but they stop counting as active readiness evidence by default.

## Current Artifact Ladder

1. Step 1 persists `source_manifest.json` and `graph_build_summary.json`.
2. Step 2 prepare emits `forecast_brief.json`, `uncertainty_spec.json`, `outcome_spec.json`, `prepared_snapshot.json`, and `grounding_bundle.json`, plus readiness summaries.
3. Step 2 handoff and Step 3 shell creation persist `ensemble_spec.json`, `ensemble_state.json`, `run_manifest.json`, and `resolved_config.json` for stored shells.
4. Launching a shell in Step 3 produces runtime state, timelines, action logs, and run metrics such as `metrics.json`.
5. Ensemble analytics persist `aggregate_summary.json`, `scenario_clusters.json`, and `sensitivity.json`.
6. Backtesting and calibration persist `backtest_summary.json` and `calibration_summary.json` when those artifacts exist.
7. Step 4 and Step 5 consume `probabilistic_report_context.json`. It always includes `grounding_context` and `answer_confidence_status`, and it only includes `calibrated_summary` or `calibration_provenance` when the confidence gate is actually ready.

## Docker Compose

If you prefer Docker:

```bash
cp .env.example .env
docker compose up -d
```

Review `docker-compose.yml` before running it if you need different ports, volumes, or image sources.

## Acknowledgments

The simulation layer is built on top of [OASIS](https://github.com/camel-ai/oasis). The project depends on open-source work from the CAMEL-AI team.
