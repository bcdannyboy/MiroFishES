# MiroFishES

MiroFishES is a fork-evolved version of MiroFish that pushes the project toward an artifact-first forecasting system rather than only a single-run simulation app. The repo still supports the legacy graph-build -> simulation -> report -> interaction flow, but it now also contains a bounded forecasting control plane with durable grounding, structured uncertainty, ensemble analytics, scoped report context, and bounded compare flows.

## What This Repo Adds Beyond Fork-Era MiroFish

Relative to the original fork-era baseline, this repo now adds:

1. a forecast-first Step 2 path that produces durable control artifacts instead of only transient setup state
2. explicit upstream grounding artifacts for uploaded sources and graph-build provenance
3. ensemble, cluster, and run scope as first-class downstream report and interaction concepts
4. scenario-family clustering and observational sensitivity analysis as inspectable artifacts
5. a narrow confidence lane with observed truth, backtests, and binary-only calibration provenance
6. a bounded compare workspace and scope-aware report-agent chat lane

What it does **not** honestly add yet:

1. comprehensive research or code-analysis grounding in the literal sense
2. broad calibrated forecasting across metric families
3. causal driver analysis
4. release-grade live operator proof

## Current Truth

The current forecasting stack is deliberately conservative.

- Upstream grounding is bounded to uploaded project sources, persisted graph-build outputs, and repo-local code-analysis artifacts only when they actually exist.
- `grounding_bundle.json` can be `ready`, `partial`, or `unavailable`.
- Aggregate summaries and scenario families are empirical.
- Selected runs are observed.
- Sensitivity is observational, not causal.
- Calibration is artifact-gated and binary-only.
- The report body is still legacy-shaped; the probabilistic layer is an evidence surface around it.
- Interviews and surveys remain legacy-scoped even when report-agent chat is scope-aware.

## Docs Map

Start with these documents:

- [Docs index](docs/README.md): fastest path to the right document by audience and task
- [What MiroFishES adds](docs/what-mirofishes-adds.md): canonical fork-delta and positioning note
- [Local probabilistic operator runbook](docs/local-probabilistic-operator-runbook.md): how to run the bounded Step 1 through Step 5 operator path locally
- [Forecasting integration hardening wave](docs/plans/2026-03-29-forecasting-integration-hardening-wave.md): authoritative current artifact, scope, and verification contract
- [North-star forecast upgrades](docs/plans/2026-03-28-mirofish-high-impact-forecasting-upgrades.md): intended higher-level direction and still-open ambition

## Repository Layout

- `frontend/`: Vite/Vue UI and browser tests
- `backend/`: Flask APIs, simulation services, artifacts, and pytest suites
- `docs/`: operator docs, current-state notes, and implementation plans
- `static/`: static assets used by the application

## Quick Start

### Prerequisites

| Tool | Version | Purpose | Check |
| --- | --- | --- | --- |
| `node` | 18+ | frontend runtime and package management | `node -v` |
| `python` | 3.11 to 3.12 | backend runtime | `python --version` |
| `uv` | latest | Python dependency management | `uv --version` |

### 1. Configure environment variables

```bash
cp .env.example .env
```

Fill in the values you need in `.env`.

Required keys for the bounded forecast path:

```env
LLM_API_KEY=your_api_key_here
ZEP_API_KEY=your_zep_api_key_here

PROBABILISTIC_PREPARE_ENABLED=true
PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED=true
PROBABILISTIC_REPORT_ENABLED=true
PROBABILISTIC_INTERACTION_ENABLED=true

CALIBRATED_PROBABILITY_ENABLED=false
```

The backend reads the repo-root `.env` automatically from `backend/app/config.py`. If those probabilistic flags are unset or `false`, the bounded Step 2 through Step 5 forecast flow is intentionally unavailable even when the stack boots.

### 2. Install dependencies

```bash
npm run setup:all
npx playwright install chromium
```

### 3. Start the development stack

```bash
npm run dev
```

Default local endpoints:

- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:5001`

### 4. Confirm forecast capabilities

Before trusting the probabilistic path, confirm the backend capability surface:

```bash
curl http://localhost:5001/api/simulation/prepare/capabilities
```

For the bounded forecast path, these booleans should be `true`:

- `probabilistic_prepare_enabled`
- `probabilistic_ensemble_storage_enabled`
- `probabilistic_report_enabled`
- `probabilistic_interaction_enabled`

## Fresh Forecast Run

If you want to start from a truly fresh local run:

1. create a new project in the UI
2. upload source material
3. complete Step 1 graph build
4. enter simulation setup, which creates a real `simulation_id`
5. stay in `Forecast` mode in Step 2 when probabilistic prepare is available
6. run forecast prepare so the repo can emit artifacts such as `prepared_snapshot.json`, `grounding_bundle.json`, `uncertainty_spec.json`, and `outcome_spec.json`
7. continue into Step 3, Step 4, and Step 5 using the generated simulation family

Important boundaries:

- A manual fresh start does **not** need `PLAYWRIGHT_LIVE_SIMULATION_ID`; that variable is only for the live Playwright operator harness.
- A meaningful run still requires upstream source material. The repo does not support “blank simulation with no uploaded inputs” as a truthful forecast workflow.
- Step 2 may still truthfully block the forecast handoff if required sidecar artifacts are missing.

## Verification Ladder

Use these commands in order when you want evidence instead of intuition:

```bash
npm run verify
npm run verify:smoke
PLAYWRIGHT_LIVE_ALLOW_MUTATION=true npm run verify:operator:local
```

What each command proves:

- `npm run verify`: frontend tests, frontend build, and backend pytest pass in the current worktree
- `npm run verify:smoke`: the bounded Step 2 through Step 5 browser shell still renders and routes correctly against deterministic fixtures
- `PLAYWRIGHT_LIVE_ALLOW_MUTATION=true npm run verify:operator:local`: one mutating local operator pass attempts to run against a real simulation family and records fresh evidence or the exact blocker

Current live-proof boundary:

- the default live family `sim_7a6661c37719` is not forecast-ready enough for a full pass because `grounding_bundle.json` is missing
- until you supply a forecast-ready `simulation_id`, fresh live evidence is currently a truthful readiness block, not a successful end-to-end Step 2 through Step 5 proof

If you already have a prepared simulation family and want the live harness to use it:

```bash
PLAYWRIGHT_LIVE_ALLOW_MUTATION=true \
PLAYWRIGHT_LIVE_SIMULATION_ID=<simulation_id> \
npm run verify:operator:local
```

For the confidence-specific lane, use:

```bash
npm run verify:confidence
```

## Current Forecasting Architecture

The current forecasting stack is organized around an explicit artifact ladder:

1. Step 1 persists `source_manifest.json` and `graph_build_summary.json`.
2. Step 2 emits `forecast_brief.json`, `uncertainty_spec.json`, `outcome_spec.json`, `prepared_snapshot.json`, and `grounding_bundle.json`.
3. Ensemble creation and Step 3 replay persist `ensemble_spec.json`, `ensemble_state.json`, `run_manifest.json`, and `resolved_config.json`.
4. Observed run truth is extracted into `metrics.json`.
5. Ensemble analytics persist `aggregate_summary.json`, `scenario_clusters.json`, and `sensitivity.json`.
6. Historical scoring persists `backtest_summary.json`, and binary-only calibration persists `calibration_summary.json`.
7. Step 4 and Step 5 consume `probabilistic_report_context.json`, which always includes `confidence_status` and only includes `calibrated_summary` when a named metric is actually ready.

The authoritative current-state note for those contracts is:

- [Forecasting integration hardening wave](docs/plans/2026-03-29-forecasting-integration-hardening-wave.md)

## Docker Compose

If you prefer Docker:

```bash
cp .env.example .env
docker compose up -d
```

Review `docker-compose.yml` if you need to change ports, volumes, or the image source before running it.

## Acknowledgments

The simulation layer is built on top of [OASIS](https://github.com/camel-ai/oasis). The project depends on the open-source work from the CAMEL-AI team.
