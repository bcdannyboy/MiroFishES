# Forecast Readiness Chain

Date: 2026-03-31
Branch: `codex/forecast-readiness-chain`
Status file: `docs/plans/2026-03-31-forecast-readiness-status.json`
Updated at: 2026-03-31T16:44:20-07:00

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

| Phase | Goal | Current status |
| --- | --- | --- |
| P01 | model routing, Responses wrapper, embeddings, local evidence index | complete |
| P02 | ingestion compatibility hooks over the new evidence foundation | complete |
| P03 | layered forecast-native ontology and graph build | complete |
| P04 | retrieval wiring over persisted local evidence records | complete |
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

## P02

### Scope

- `backend/app/utils/file_parser.py`
- `backend/app/services/text_processor.py`
- `backend/app/api/graph.py`
- `backend/app/models/source_units.py`
- `backend/app/models/project.py`
- backend unit/API tests covering parser, text processing, and graph upload/build compatibility

### TDD Record

1. Wrote failing tests for parser metadata extraction, preprocessing normalization, semantic source-unit segmentation, source-unit-aware chunking, and ontology upload artifact persistence.
2. Verified the initial failures were the missing `extract_document(...)` parser surface, missing source-unit builders, missing source-unit-aware chunking, and missing `source_units.json` persistence.
3. Hit two GREEN-pass issues:
   - semantic chunking still orphaned short headings because the size limit was enforced too rigidly
   - `/api/graph/build` always passed a `source_units=` keyword and broke fallback call sites when no source-unit artifact existed
4. Fixed the root causes by:
   - allowing a bounded heading-plus-following-unit chunk when that keeps structure intact
   - only passing `source_units` into `TextProcessor.split_text(...)` when the artifact actually exists
5. Corrected one test fixture after verification showed the synthetic source-unit payload omitted `unit_type`, which the real contract includes.

### Verification

- Targeted parser/text processor/graph upload suite:
  - command: `backend/.venv/bin/python -m pytest backend/tests/unit/test_file_parser_source_units.py backend/tests/unit/test_text_processor_source_units.py backend/tests/unit/test_forecast_grounding.py -q`
  - result: `10 passed, 1 warning in 0.12s`
- Live `.env` ontology upload smoke:
  - command: `PYTHONPATH=backend backend/.venv/bin/python - <<'PY' ... Flask test client POST /api/graph/ontology/generate with market-update.md ... PY`
  - result: `200`, `success=True`, `project_id=proj_1e7b4a4fc199`
  - persisted source-unit evidence:
    - `unit_count: 6`
    - `unit_type_counts: {"heading": 1, "paragraph": 1, "list_item": 2, "quote": 1, "speaker_turn": 1}`
    - first unit id: `su-c99dae8aa98a-0001`
    - `grounding_artifacts.source_units.exists: true`
- Full repo gate:
  - command: `npm run verify`
  - result: frontend verify passed, vite build passed, backend pytest passed
  - exact backend summary: `337 passed, 1 warning in 5.64s`

### Files Touched

- `backend/app/utils/file_parser.py`
- `backend/app/services/text_processor.py`
- `backend/app/api/graph.py`
- `backend/app/models/source_units.py`
- `backend/app/models/project.py`
- `backend/tests/unit/test_file_parser_source_units.py`
- `backend/tests/unit/test_text_processor_source_units.py`
- `backend/tests/unit/test_forecast_grounding.py`
- `docs/plans/2026-03-31-forecast-readiness-chain.md`
- `docs/plans/2026-03-31-forecast-readiness-status.json`

### Delivered Foundation

- parser-level document extraction metadata with deterministic file hash and extraction warnings
- semantic source units for headings, paragraphs, list items, quotes, tables, and speaker turns with source-local and combined-text spans
- stable `stable_source_id` and `unit_id` generation for deterministic downstream embedding and citation work
- persisted `source_units.json` artifact alongside `source_manifest.json`
- source-unit-aware chunking in graph build with compatibility fallback to the old fixed-character splitter when the artifact is absent
- grounding artifact discovery updated so upload responses can report `source_units`

### Compatibility Fixes

- added `ProjectManager.save_source_units(...)`, `get_source_units(...)`, and artifact description support as a minimal compatibility shim so later phases can consume the new artifact without changing project ownership or graph schema
- preserved existing `FileParser.extract_text(...)`, `TextProcessor.extract_from_files(...)`, and upload/build endpoint behavior for older call sites
- kept graph build compatible with pre-P02 projects that only have `source_manifest.json`

### Commit Gate

- All required P02 gates passed.
- Commit is allowed for this phase.

## Handoff To P03

Prompt 3 must consume the new ingestion artifacts directly instead of reconstructing text boundaries from `extracted_text.txt`:

- load project source units with `ProjectManager.get_source_units(project_id)`
- treat `source_units.json` as the canonical upstream boundary artifact for embedding, claim extraction, graph evidence mapping, and citations
- rely on these per-unit fields:
  - `unit_id`
  - `source_id`
  - `stable_source_id`
  - `source_sha256`
  - `original_filename`
  - `relative_path`
  - `source_order`
  - `unit_order`
  - `unit_type`
  - `char_start`
  - `char_end`
  - `combined_text_start`
  - `combined_text_end`
  - `text`
  - `metadata`
  - `extraction_warnings`
- preserve `source_manifest.json` as the file-level provenance artifact and use `source_manifest.source_artifacts.source_units == "source_units.json"` as the linkage
- preserve `stable_source_id` and `unit_id` verbatim in any embedding, claim, or retrieval records so Prompt 4+ can join back to file provenance without fuzzy matching

## P03

### Scope

- `backend/app/services/ontology_generator.py`
- `backend/app/services/graph_builder.py`
- `backend/app/services/zep_entity_reader.py`
- `backend/app/services/forecast_graph.py`
- `backend/app/api/graph.py`
- backend unit/API tests covering layered ontology normalization, graph summaries, and provenance-aware graph artifacts

### TDD Record

1. Wrote failing tests for layered ontology defaults, source-unit-aware chunk planning, graph snapshot type breakdown, actor-safe default entity filtering, and graph-build artifact provenance.
2. Verified the RED failures were the expected missing pieces:
   - no layered schema metadata/defaults in ontology normalization
   - no source-unit-aware chunk record builder
   - no layered graph counts in snapshots/summaries
   - analytical labels still leaking into default actor reads
   - no provenance-aware analytical object index in `/api/graph/build`
3. Hit two GREEN-pass issues after the first implementation:
   - the original ontology normalization test still assumed actor-specific custom types would survive the layered schema untouched
   - the first semantic chunk planner over-merged source units and made the live/API fixture brittle
4. Fixed the root causes by:
   - keeping the layered schema authoritative while mapping unknown actor-like references back to `Person` or `Organization`
   - switching semantic graph chunking to deterministic source-unit chunks
   - using persisted source-unit text when available instead of trusting spans alone
   - keeping actor filtering backward-safe by excluding analytical labels unless they are explicitly requested

### Verification

- Targeted layered graph backend suite:
  - command: `backend/.venv/bin/python -m pytest backend/tests/unit/test_ontology_generator.py backend/tests/unit/test_graph_builder_service.py backend/tests/unit/test_zep_entity_reader.py backend/tests/unit/test_forecast_grounding.py backend/tests/unit/test_graph_data_api.py -q`
  - result: `23 passed, 1 warning in 0.16s`
- Live `.env` layered ontology smoke:
  - command: `curl -sS -X POST http://127.0.0.1:5001/api/graph/ontology/generate ... files=@/tmp/p03-live-smoke.md`
  - result: `success=True`, `project_id=proj_62646edbad5f`
  - returned ontology evidence:
    - `schema_mode: forecast_layered`
    - `actor_types: ["Person", "Organization"]`
    - `analytical_types: ["Event", "Claim", "Evidence", "Topic", "Metric", "TimeWindow", "Scenario", "UncertaintyFactor"]`
    - `entity_type_count: 10`
    - `edge_type_count: 9`
- Live `.env` layered graph-build smoke:
  - command: `curl -sS -X POST http://127.0.0.1:5001/api/graph/build -d '{"project_id":"proj_62646edbad5f"}'` plus task polling
  - final task result:
    - `status: completed`
    - `task_id: c52152e2-6193-4d0c-aabb-6d026225673c`
    - `graph_id: mirofish_7a3656f8e25647fe`
    - `chunk_count: 8`
    - `node_count: 11`
    - `edge_count: 4`
  - persisted artifact evidence:
    - `graph_build_summary.json.chunking_strategy: semantic_source_units`
    - `graph_build_summary.json.graph_counts.actor_count: 2`
    - `graph_build_summary.json.graph_counts.analytical_object_count: 9`
    - `graph_build_summary.json.citation_coverage.source_unit_backed_edge_count: 4`
    - `graph_entity_index.json.entity_types: ["Organization", "Person"]`
    - `graph_entity_index.json.analytical_types: ["Evidence", "Scenario", "Topic", "UncertaintyFactor"]`
    - example analytical provenance:
      - object: `Evidence / payroll preview`
      - `source_unit_ids: ["su-14f1ddf9bece-0003"]`
      - citation file: `p03-live-smoke.md`
- Full repo gate:
  - command: `npm run verify`
  - result: frontend verify passed, vite build passed, backend pytest passed
  - exact backend summary: `342 passed, 1 warning in 5.71s`

### Files Touched

- `backend/app/api/graph.py`
- `backend/app/services/forecast_graph.py`
- `backend/app/services/graph_builder.py`
- `backend/app/services/ontology_generator.py`
- `backend/app/services/zep_entity_reader.py`
- `backend/tests/unit/test_forecast_grounding.py`
- `backend/tests/unit/test_graph_builder_service.py`
- `backend/tests/unit/test_ontology_generator.py`
- `backend/tests/unit/test_zep_entity_reader.py`
- `docs/plans/2026-03-31-forecast-readiness-chain.md`
- `docs/plans/2026-03-31-forecast-readiness-status.json`

### Delivered Foundation

- layered forecast ontology defaults with actors plus analytical objects under one compatibility-safe `entity_types` surface
- canonical layered edge vocabulary for claims, evidence, topics, time windows, scenarios, and uncertainty factors
- deterministic source-unit chunk records for graph build, preserving `source_unit_ids`, `source_ids`, and `stable_source_ids`
- graph snapshots and build summaries with actor/analytical breakdowns plus node and edge type counts
- backward-compatible `graph_entity_index.json` actor payloads plus additive `analytical_objects` records with citation metadata
- provenance linking from graph edges and analytical objects back to `source_units.json` citations through episode-to-chunk mapping

### Compatibility Fixes

- default `ZepEntityReader.filter_defined_entities(...)` now keeps actor-style labels by default and excludes analytical labels unless they are explicitly requested, so existing simulation prepare flows do not start treating claims or evidence nodes as agents
- graph build still falls back to legacy fixed-character chunking when `source_units.json` is absent
- `graph_entity_index.json` keeps the legacy actor-facing `entities` / `entity_types` surface while adding `analytical_objects`, `analytical_types`, and `citation_coverage`
- project ontology storage remains additive: old callers still read `entity_types` / `edge_types`, while later prompts can consume `schema_mode`, `actor_types`, and `analytical_types`

### Commit Gate

- All required P03 gates passed.
- Commit is allowed for this phase.

## Handoff To P04

Prompt 4 must treat the graph-side layered artifacts from P03 as the canonical retrieval inputs:

- load `project.ontology` and require `schema_mode == "forecast_layered"` before assuming analytical objects exist
- use `graph_build_summary.json` for high-level graph coverage, especially:
  - `graph_counts.actor_count`
  - `graph_counts.analytical_object_count`
  - `graph_counts.actor_types`
  - `graph_counts.analytical_types`
  - `graph_counts.node_type_counts`
  - `graph_counts.edge_type_counts`
  - `citation_coverage.*`
- consume `graph_entity_index.json` directly instead of re-reading raw graph data when possible
- keep actor and analytical retrieval lanes distinct:
  - actor lane: `graph_entity_index.json.entities`
  - analytical lane: `graph_entity_index.json.analytical_objects`
- each analytical object record now carries:
  - `uuid`
  - `name`
  - `labels`
  - `summary`
  - `attributes`
  - `related_edges`
  - `related_nodes`
  - `object_type`
  - `layer`
  - `provenance`
- retrieval must consume the `provenance` payload rather than inventing fuzzy citations:
  - `match_reason`
  - `episode_ids`
  - `chunk_ids`
  - `source_unit_ids`
  - `source_ids`
  - `stable_source_ids`
  - `citation_count`
  - `citations[]`
- each `citations[]` item carries:
  - `unit_id`
  - `source_id`
  - `stable_source_id`
  - `original_filename`
  - `relative_path`
  - `unit_type`
  - `source_order`
  - `unit_order`
  - `char_start`
  - `char_end`
  - `combined_text_start`
  - `combined_text_end`
  - `text_excerpt`
  - `reason`
- Prompt 4 must continue preserving `source_units.json` as the authoritative text/citation boundary and must not collapse actors and analytical objects into one undifferentiated retrieval pool without an explicit reason

## P04

### Scope

- `backend/app/services/evidence_bundle_service.py`
- `backend/app/services/grounding_bundle_builder.py`
- `backend/app/services/zep_tools.py`
- `backend/app/services/report_agent.py`
- `backend/app/services/hybrid_evidence_retriever.py`
- `backend/app/services/forecast_hint_service.py`
- backend tests covering hybrid retrieval ranking, evidence bundle generation, retrieval tool wiring, and downstream compatibility

### TDD Record

1. Wrote failing tests first for hybrid retrieval ranking, contradiction propagation, grounding-bundle retrieval contracts, Zep hybrid search wrapping, report-agent tool routing, and bundle generation with real forecast hints.
2. Verified the RED failures were the expected missing surfaces:
   - no `HybridEvidenceRetriever`
   - no `forecast_hints` derivation layer
   - no `retrieval_contract` in the grounding bundle
   - no `hybrid_evidence_search` in `ZepToolsService`
   - no report-agent integration for hybrid evidence lookup
3. Hit one GREEN-pass regression after the first implementation: legacy grounding-bundle-only evidence cases were downgraded to partial because hybrid-only missing markers leaked into the provider status.
4. Traced that regression to status propagation in `UploadedLocalArtifactEvidenceProvider.collect(...)`, then fixed the root cause by preserving the legacy grounding fallback as `ready` when it satisfies the old contract and only hybrid-local artifacts are absent.
5. Added a narrow end-to-end integration test for bundle generation so the phase has real multi-module evidence, not only unit coverage.

### Verification

- Targeted hybrid retrieval and evidence bundle suite:
  - command: `backend/.venv/bin/python -m pytest backend/tests/unit/test_hybrid_evidence_retriever.py backend/tests/unit/test_evidence_bundle_service.py backend/tests/unit/test_forecast_grounding.py backend/tests/unit/test_zep_tools_multigraph.py backend/tests/unit/test_report_agent_hybrid_retrieval.py backend/tests/integration/test_hybrid_evidence_bundle_flow.py -q`
  - result: `20 passed, 1 warning in 0.17s`
- Downstream compatibility subset:
  - command: `backend/.venv/bin/python -m pytest backend/tests/unit/test_forecast_engine.py::test_hybrid_engine_assembles_best_estimate_without_let_simulation_dominate backend/tests/unit/test_hybrid_forecast_service.py::test_hybrid_forecast_service_aggregates_non_simulation_workers_without_let_simulation_dominate backend/tests/unit/test_forecast_manager.py::test_forecast_manager_acquires_evidence_bundle_with_provider_fallbacks backend/tests/unit/test_forecast_api.py::test_forecast_evidence_bundle_round_trip_with_public_aliases_does_not_duplicate_provider_entries -q`
  - result: `4 passed, 1 warning in 0.16s`
- Live `.env` hybrid retrieval smoke:
  - command: `cd backend && .venv/bin/python - <<'PY' ... HybridEvidenceRetriever(... LocalEvidenceIndex('/tmp/mirofish_p04_live.sqlite3')).retrieve(project_id='proj_62646edbad5f', query='What evidence supports a June rate cut after weaker hiring?', question_type='binary', limit=4) ... PY`
  - result summary:
    - `project_id: proj_62646edbad5f`
    - `total_count: 4`
    - `missing_markers: []`
    - `index_stats.record_count: 17`
    - `index_stats.namespace_count: 2`
  - top cited hits:
    - rank 1: `source_unit / speaker_turn / [SUbece0003] / files/c1481f17.md#chars=121-230 / supports / estimate 0.6886`
    - rank 2: `source_unit / paragraph / [SUbece0002] / files/c1481f17.md#chars=17-119 / supports / estimate 0.6748`
    - rank 3: `graph_object / Topic / [GO83d48f6e] / files/c1481f17.md#chars=17-119 / supports / estimate 0.6743`
    - rank 4: `graph_object / Evidence / [GOf4a9b8e6] / files/c1481f17.md#chars=121-230 / supports / estimate 0.6684`
- Full repo gate:
  - command: `npm run verify`
  - result: frontend verify passed, vite build passed, backend pytest passed
  - exact backend summary: `348 passed, 1 warning in 5.85s`

### Files Touched

- `backend/app/services/evidence_bundle_service.py`
- `backend/app/services/grounding_bundle_builder.py`
- `backend/app/services/zep_tools.py`
- `backend/app/services/report_agent.py`
- `backend/app/services/hybrid_evidence_retriever.py`
- `backend/app/services/forecast_hint_service.py`
- `backend/tests/unit/test_hybrid_evidence_retriever.py`
- `backend/tests/unit/test_evidence_bundle_service.py`
- `backend/tests/unit/test_forecast_grounding.py`
- `backend/tests/unit/test_zep_tools_multigraph.py`
- `backend/tests/unit/test_report_agent_hybrid_retrieval.py`
- `backend/tests/integration/test_hybrid_evidence_bundle_flow.py`
- `docs/plans/2026-03-31-forecast-readiness-chain.md`
- `docs/plans/2026-03-31-forecast-readiness-status.json`

### Delivered Foundation

- `HybridEvidenceRetriever` now performs hybrid local ranking across:
  - embedded `source_units.json`
  - graph-native `graph_entity_index.json.analytical_objects`
  - graph linkage and lexical overlap as additive ranking signals
- `ForecastHintService` now derives structured evidence signals per hit:
  - `forecast_hints[]`
  - `conflict_status`
  - `conflict_markers[]`
- `GroundingBundleBuilder` now emits a deterministic `retrieval_contract` for later phases with:
  - `status`
  - `source_unit_count`
  - `actor_count`
  - `analytical_object_count`
  - `graph_id`
  - `index_namespaces.source_units`
  - `index_namespaces.graph_objects`
  - `citation_coverage`
- `UploadedLocalArtifactEvidenceProvider` now normalizes hybrid hits into additive `EvidenceSourceEntry` records with:
  - `kind in {"uploaded_source", "graph_provenance"}`
  - `citation_id`
  - `locator`
  - `provenance.project_id`
  - `provenance.simulation_id`
  - `provenance.retrieval.record_type`
  - `provenance.retrieval.score`
  - `metadata.forecast_hints`
  - `metadata.hybrid_retrieval`
- `ZepToolsService.hybrid_evidence_search(...)` now exposes cited hybrid evidence to report and analyst surfaces.
- `ReportAgent` now supports `hybrid_evidence_search` and resolves `project_id` from saved forecast workspace context when available.

### Compatibility Fixes

- Preserved the legacy grounding-bundle-only evidence path as `ready` when hybrid-local artifacts are absent but the old grounding contract still exists.
- Kept evidence bundle consumers additive: existing `EvidenceSourceEntry` fields remain valid while new retrieval signals live under `metadata.forecast_hints` and `metadata.hybrid_retrieval`.
- Filtered report-agent hybrid-search kwargs against the target method signature so existing narrow Zep-tool doubles and older call surfaces do not break.
- Left forecast aggregation logic unchanged; this phase only injects structured retrieval signals and citations for later consumers.

### Commit Gate

- All required P04 gates passed.
- Commit is allowed for this phase.

## Handoff To P05

Prompt 5 must consume the P04 evidence interfaces directly instead of reconstructing evidence state from raw text:

- use `GroundingBundleBuilder.build(...)[\"retrieval_contract\"]` as the authoritative retrieval readiness surface
- treat these bundle entry kinds as real retrieval-backed world-state inputs:
  - `uploaded_source`
  - `graph_provenance`
- each retrieval-backed `EvidenceSourceEntry` now carries the simulation-init inputs P05 should use:
  - `citation_id`
  - `locator`
  - `summary`
  - `conflict_status`
  - `conflict_markers[]`
  - `freshness`
  - `relevance`
  - `quality`
  - `provenance.project_id`
  - `provenance.simulation_id`
  - `provenance.source_unit_ids`
  - `provenance.source_ids`
  - `provenance.stable_source_ids`
  - `provenance.retrieval.record_type`
  - `provenance.retrieval.score`
  - `provenance.retrieval.score_components`
- consume `metadata.forecast_hints[]` as the structured evidence-signal layer rather than re-inferring support from free text
- each `forecast_hints[]` item may carry:
  - `signal`
  - `estimate`
  - `confidence_weight`
  - `assumption`
  - `counterevidence`
  - `citation_ids`
  - `source_unit_ids`
  - `object_type`
- preserve bundle-level and provider-level gap semantics:
  - `missing_evidence_markers[]`
  - `uncertainty_summary`
  - `retrieval_contract.status`
- if Prompt 5 needs an on-demand retrieval path, reuse:
  - `HybridEvidenceRetriever.retrieve(...)`
  - `ZepToolsService.hybrid_evidence_search(...)`
- Prompt 5 must not redesign forecast aggregation. It should only consume these structured evidence and citation inputs to improve simulation initialization and world-state grounding.
