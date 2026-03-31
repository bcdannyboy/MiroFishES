# Forecast Readiness Chain

Date: 2026-03-31
Branch: `codex/forecast-readiness-chain`
Status file: `docs/plans/2026-03-31-forecast-readiness-status.json`
Updated at: 2026-03-31T15:34:15-07:00

## Chain Contract

Every later prompt in this chain must:

- read this ledger and the prior phase handoff before changing code
- own only its designated scope and avoid redesigning unrelated forecasting subsystems
- use TDD strictly: write failing tests first, verify the failure, then implement the smallest fix
- run fixture or unit tests before any live or `.env` smoke
- update this ledger and the status JSON before stopping
- avoid claiming success without fresh verification evidence recorded here
- commit only if every phase gate for that prompt passes

## Phase Map

| Phase | Goal | Initial status |
| --- | --- | --- |
| P01 | model routing, Responses wrapper, embeddings, local evidence index | complete |
| P02 | ingestion compatibility hooks over the new evidence foundation | pending |
| P03 | ontology and claim extraction alignment | pending |
| P04 | retrieval wiring over persisted local evidence records | pending |
| P05 | simulation evidence bridge | pending |
| P06 | forecast aggregation compatibility adoption | pending |
| P07 | report and analyst surfaces adoption | pending |
| P08 | live workflow stabilization | pending |
| P09 | readiness verification ladder | pending |
| P10 | final chain closeout and follow-up truth audit | pending |

## P01

### Scope

- `backend/app/config.py`
- `backend/app/utils/llm_client.py`
- `backend/app/utils/model_routing.py`
- `backend/app/utils/embedding_client.py`
- `backend/app/services/local_evidence_index.py`
- backend unit tests covering the same surface

### TDD Record

1. Wrote failing tests for config/model routing, structured Responses support, embeddings, and local evidence index persistence.
2. Verified the initial failure was due to missing routing and indexing modules plus missing router-aware structured response support in `LLMClient`.
3. Hit one implementation bug during the GREEN pass: router override arguments were coupled too tightly to one router signature.
4. Traced that failure to the caller contract, not the router logic itself, then fixed it by letting callers apply local overrides after `resolve(task)`.
5. Implemented the smallest additive foundation without changing ingestion, retrieval, simulation, or aggregation behavior.

### Verification

- Targeted unit suite:
  - command: `backend/.venv/bin/python -m pytest backend/tests/unit/test_model_routing.py backend/tests/unit/test_llm_client.py backend/tests/unit/test_embedding_client_and_evidence_index.py -q`
  - result: `6 passed, 1 warning in 0.13s`
- Live structured Responses smoke:
  - command: `PYTHONPATH=backend backend/.venv/bin/python - <<'PY' ... LLMClient().create_structured_response(..., schema=Extraction, task="reasoning") ... PY`
  - result model: `gpt-4o-mini-2024-07-18`
  - result payload: `{"verdict":"Strong demand is indicated in the market.","rationale":"The increase in foot traffic over three weeks and the fall in vacancy rates suggest a strengthening demand for space."}`
- Live embedding smoke:
  - command: `PYTHONPATH=backend backend/.venv/bin/python - <<'PY' ... LocalEmbeddingClient().embed_text("forecast readiness embedding smoke") ... PY`
  - result length: `1536`
  - result norm: `1.0`
  - first 8 values: `[0.023095925929640427, 0.04603930281086843, 0.02289761216670428, -0.04307985127166748, -0.011990355205216232, -0.009747884193553654, 0.04204251774246302, -0.03282855521835284]`
- Full repo gate:
  - command: `npm run verify`
  - result: `frontend verify passed, vite build passed, backend pytest passed`
  - exact backend summary: `333 passed, 1 warning in 36.48s`

### Files Touched

- `backend/app/config.py`
- `backend/app/utils/llm_client.py`
- `backend/app/utils/model_routing.py`
- `backend/app/utils/embedding_client.py`
- `backend/app/services/local_evidence_index.py`
- `backend/tests/unit/test_model_routing.py`
- `backend/tests/unit/test_llm_client.py`
- `backend/tests/unit/test_embedding_client_and_evidence_index.py`
- `docs/plans/2026-03-31-forecast-readiness-chain.md`
- `docs/plans/2026-03-31-forecast-readiness-status.json`

### Delivered Foundation

- task-scoped model routing for `default`, `reasoning`, `report`, and `embedding`
- compatibility-safe env fallbacks from existing `LLM_*` settings into the new OpenAI routing surface
- additive Responses-based wrapper methods on `LLMClient` while keeping existing `chat(...)` and `chat_json(...)` behavior
- local embedding client with normalized vectors and optional dimension override support
- persisted local evidence index with namespace-scoped upsert, cosine search, and lightweight stats

### Commit Gate

- All required P01 gates passed.
- Commit is allowed for this phase.

## Handoff To P02

Prompt 2 must consume the foundation from P01 instead of inventing a parallel path:

- use `Config.get_task_model_routes()` and `TaskModelRouter.resolve(...)` for task-scoped model selection
- use `LLMClient.create_response(...)` or `LLMClient.create_structured_response(...)` for Responses-based work
- use `LocalEmbeddingClient.embed_text(...)` / `embed_texts(...)` for embedding generation
- use `LocalEvidenceIndex` plus `EvidenceIndexRecord` for persisted local vector records
- reuse `Config.get_local_evidence_index_path()` for any default evidence-index storage path
- preserve `LLMClient.chat(...)` and `LLMClient.chat_json(...)` for any legacy callers that are not migrating yet

Prompt 2 must treat this phase as additive infrastructure. It should wire ingestion or retrieval hooks onto these interfaces rather than replacing them.
