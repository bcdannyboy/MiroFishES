# MiroFishES

MiroFishES is a multi-agent simulation and forecasting system. It takes seed material such as reports, news, policy drafts, or fictional scenarios, builds a graph-backed environment, simulates agent interactions over time, and produces both a report and an interactive interface for exploring the result.

## Overview

The project is organized around a pipeline that turns unstructured input into a simulated world:

1. **Graph building**: extract entities, relationships, and memory from the source material.
2. **Environment setup**: generate personas, world state, and simulation parameters.
3. **Simulation run**: execute the multi-agent simulation and update temporal memory over time.
4. **Report generation**: synthesize a prediction or scenario report from the final state.
5. **Interactive exploration**: inspect the generated world and interact with the reporting agent.

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

# Optional accelerated LLM configuration.
LLM_BOOST_API_KEY=your_api_key_here
LLM_BOOST_BASE_URL=your_base_url_here
LLM_BOOST_MODEL_NAME=your_model_name_here
```

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

- Frontend: `http://localhost:3000`
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

## Docker Compose

If you prefer Docker:

```bash
cp .env.example .env
docker compose up -d
```

Review `docker-compose.yml` if you need to change ports, volumes, or the image source before running it.

## Acknowledgments

The simulation layer is built on top of [OASIS](https://github.com/camel-ai/oasis). The project depends on the open-source work from the CAMEL-AI team.
