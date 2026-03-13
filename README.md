# MiroFishES

MiroFishES is a multi-agent simulation and forecasting system. It takes seed material such as reports, news, policy drafts, or fictional scenarios, builds a graph-backed environment, simulates agent interactions over time, and produces both a report and an interactive interface for exploring the result.

## Overview

The project is organized around a pipeline that turns unstructured input into a simulated world:

1. **Graph building**: extract entities, relationships, and memory from the source material.
2. **Environment setup**: generate personas, world state, and simulation parameters.
3. **Simulation run**: execute the multi-agent simulation and update temporal memory over time.
4. **Report generation**: synthesize a prediction or scenario report from the final state.
5. **Interactive exploration**: inspect the generated world and interact with the reporting agent.

The current probabilistic rollout is additive to that legacy path. The single-run flow remains the production default, while probabilistic prepare, stored-run Step 3 replay, bounded Step 4 report context, and bounded Step 5 report-agent grounding are local-development surfaces that must be treated with explicit empirical or observed language.

## Repository Layout

- `frontend/`: Vite/Vue frontend application
- `backend/`: Flask backend, simulation services, and API endpoints
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

Required keys:

```env
# Compatible with OpenAI-style LLM APIs.
# The defaults point at Qwen via DashScope.
LLM_API_KEY=your_api_key_here
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL_NAME=qwen-plus

# Zep memory graph configuration.
ZEP_API_KEY=your_zep_api_key_here

# Probabilistic rollout flags.
# These are all false by default in backend/app/config.py.
# Enable them together for the bounded local probabilistic Step 2 through Step 5 path.
PROBABILISTIC_PREPARE_ENABLED=true
PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED=true
PROBABILISTIC_REPORT_ENABLED=true
PROBABILISTIC_INTERACTION_ENABLED=true

# Keep calibrated language off unless calibrated artifacts exist.
CALIBRATED_PROBABILITY_ENABLED=false

# Optional accelerated LLM configuration.
LLM_BOOST_API_KEY=your_api_key_here
LLM_BOOST_BASE_URL=your_base_url_here
LLM_BOOST_MODEL_NAME=your_model_name_here
```

If those probabilistic flags stay unset or remain `false`, the local probabilistic Step 2 through Step 5 path is intentionally unavailable even when the rest of the stack starts correctly.

### 2. Install dependencies

Install everything:

```bash
npm run setup:all
```

Or install by layer:

```bash
npm run setup
npm run setup:backend
```

### 3. Start the development stack

```bash
npm run dev
```

Default local endpoints:

- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:5001`

You can also start each side independently:

```bash
npm run backend
npm run frontend
```

### 4. Build the frontend

```bash
npm run build
```

## Local Probabilistic Operator Path

The local probabilistic workflow is intentionally bounded. Before treating it as usable, verify the repo-owned evidence ladder in order:

```bash
npx playwright install chromium
npm run verify
npm run verify:smoke
PLAYWRIGHT_LIVE_ALLOW_MUTATION=true npm run verify:operator:local
```

What those commands prove:

- `npm run verify`: frontend unit/runtime tests, frontend build, and backend pytest all pass in the current worktree.
- `npm run verify:smoke`: fixture-backed browser checks cover the bounded Step 2 through Step 5 probabilistic shell, including Step 3 history replay from a saved probabilistic record.
- `PLAYWRIGHT_LIVE_ALLOW_MUTATION=true npm run verify:operator:local`: one mutating local-only non-fixture operator pass runs against a real simulation family and refreshes `output/playwright/live-operator/latest.json`.

Recommended zero-context local operator setup:

```bash
cp .env.example .env
# edit .env and enable the four probabilistic rollout flags plus LLM/Zep keys
npm run setup:all
npm run dev
curl http://localhost:5001/api/simulation/prepare/capabilities
```

Expected capability truth for the bounded local probabilistic path:

- `probabilistic_prepare_enabled=true`
- `probabilistic_ensemble_storage_enabled=true`
- `probabilistic_report_enabled=true`
- `probabilistic_interaction_enabled=true`

Important boundaries:

- Live probabilistic Step 2 still depends on configured `LLM_API_KEY` and `ZEP_API_KEY`.
- The deterministic smoke fixture is QA evidence, not proof that the live prepare path is self-contained.
- Step 3 now supports saved-record re-entry, but compare remains out of scope.
- Step 5 remains probabilistic only in the saved-report report-agent lane; interviews and surveys are still legacy-scoped.

Live operator pass notes:

- The test defaults to `sim_7a6661c37719` if `PLAYWRIGHT_LIVE_SIMULATION_ID` is not set.
- In a fresh workspace, prefer an explicit simulation family:

```bash
PLAYWRIGHT_LIVE_ALLOW_MUTATION=true \
PLAYWRIGHT_LIVE_SIMULATION_ID=<your_simulation_id> \
npm run verify:operator:local
```

- Operator artifacts live under `backend/uploads/simulations/<simulation_id>/ensemble/ensemble_<ensemble_id>/runs/run_<run_id>/`.
- Durable artifacts: `run_manifest.json`, `resolved_config.json`.
- Volatile runtime artifacts that cleanup may remove: `simulation.log`, `twitter/actions.jsonl`, `reddit/actions.jsonl`.

Use the operator runbook for the supported recovery path, prerequisite checklist, and known limitations:

- [Local probabilistic operator runbook](docs/local-probabilistic-operator-runbook.md)

## Docker Compose

If you prefer Docker:

```bash
cp .env.example .env
docker compose up -d
```

Review `docker-compose.yml` if you need to change ports, volumes, or the image source before running it.

## Acknowledgments

The simulation layer is built on top of [OASIS](https://github.com/camel-ai/oasis). The project depends on the open-source work from the CAMEL-AI team.
