# Upstream Grounding Layer Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add one truthful upstream grounding layer so forecast preparation, report context, and report-agent chat can rely on durable research/source/code-analysis artifacts instead of only downstream simulation outputs.

**Architecture:** Keep the current downstream probabilistic artifact ladder intact. Add one upstream artifact family rooted in Step 1 project state: `source_manifest.json` for uploaded-source identity and extraction provenance, `graph_build_summary.json` for ontology/chunk/graph-build provenance, and `grounding_bundle.json` in the simulation directory as the forecast-facing evidence bundle that later phases consume. Step 2 only mirrors a compact grounding summary into `forecast_brief.json`, `prepared_snapshot.json`, and `prepared_artifact_summary`; Step 4 and Step 5 consume the same upstream bundle through `probabilistic_report_context.json` and prompt-safe report-agent formatting.

**Tech Stack:** Python 3.11+, Flask, pytest, Vue 3, Vite, Node test runner, JSON artifact contracts under `backend/uploads/projects/` and `backend/uploads/simulations/`.

---

## Current Repo Truth

- Step 1 persists `project.json`, uploaded files, extracted text, ontology, and `analysis_summary`, but it does not persist a durable source manifest with file hashes, extraction status, or citation anchors.
- Graph build returns task results and saves `graph_id` on the project, but it does not persist a durable `graph_build_summary.json` artifact with chunk settings, counts, and upstream references.
- Step 2 already emits durable probabilistic control artifacts, but none of them currently attach a durable upstream research/source/code-analysis bundle.
- `probabilistic_report_context.json` currently carries downstream empirical, observed, observational, and calibration provenance only; it does not expose upstream source grounding separately.
- Zep retrieval and report-agent tool usage are currently runtime-only seams. They produce transient tool text, not durable forecast-grounding artifacts.

## Phase Decisions

### Exact Artifact Contract Later Phases Should Use

Later phases should treat one repo-owned upstream contract as canonical:

1. `backend/uploads/projects/<project_id>/source_manifest.json`
2. `backend/uploads/projects/<project_id>/graph_build_summary.json`
3. `backend/uploads/simulations/<simulation_id>/grounding_bundle.json`

The canonical forecast-facing artifact is `grounding_bundle.json`. Later phases should not infer grounding readiness from raw project metadata, ad hoc Zep queries, or report-agent tool output when the bundle is absent.

### `source_manifest.json`

Purpose:

- Canonical ledger for uploaded sources and extraction provenance.

Required contents:

- `artifact_type`, `schema_version`, `generator_version`, `project_id`, `created_at`
- `simulation_requirement`
- one record per uploaded file with:
  - stable `source_id`
  - `original_filename`
  - stored filename/path metadata
  - `size_bytes`
  - `sha256`
  - `content_kind` such as `document`, `text`, `code`, or `unknown`
  - extraction status, extracted text length, and parser warnings if any
- one repo-truth `boundary_note` stating this artifact reflects uploaded project sources only

### `graph_build_summary.json`

Purpose:

- Durable provenance for the graph that later forecasting artifacts rely on.

Required contents:

- `artifact_type`, `schema_version`, `generator_version`, `project_id`, `graph_id`, `generated_at`
- reference to `source_manifest.json`
- ontology summary, `analysis_summary`, `chunk_size`, `chunk_overlap`, `chunk_count`
- graph counts such as `node_count`, `edge_count`, and task/build status
- warnings when build data is partial or unavailable

### `grounding_bundle.json`

Purpose:

- One deterministic, forecast-facing upstream evidence bundle consumed by Step 2, Step 4, and Step 5.

Required contents:

- `artifact_type`, `schema_version`, `generator_version`, `project_id`, `simulation_id`, `graph_id`, `generated_at`
- `status`: `ready`, `partial`, or `unavailable`
- `source_artifacts` references to `source_manifest.json` and `graph_build_summary.json`
- `boundary_note` that explicitly says grounding is limited to uploaded sources, graph-derived facts, and repo-local code analysis only when available
- `warnings` listing every missing or degraded grounding prerequisite
- `source_summary`
- `graph_summary`
- `code_analysis_summary`
- `citation_index`
- bounded `evidence_items`

`evidence_items` must use stable IDs and locators:

- source evidence citations: `[S#]` with filename plus section/offset locator
- graph evidence citations: `[G#]` with node/edge IDs or named entity/fact locator
- code evidence citations: `[C#]` with repo-local path and line numbers

`code_analysis_summary` is explicitly optional and repo-local only:

- if repo-local code evidence exists, record it with `[C#]` citations
- if no repo-local code evidence is requested or available, set an explicit status such as `not_requested` or `unavailable`
- do not silently treat missing code analysis as comprehensive coverage

### Readiness Rule

`grounding_bundle.json` is:

- `ready` when `source_manifest.json` and `graph_build_summary.json` exist and at least one bounded evidence item is attached
- `partial` when some upstream prerequisites or evidence sections are missing but at least one grounding section is still usable
- `unavailable` when no durable upstream evidence can be attached

Later phases may assume only `ready` or `partial` bundle states exist. They must not fabricate upstream grounding when the state is `unavailable`.

## Attachment Contract

### Forecast Briefs and Prepare Summaries

- If `forecast_brief.json` exists, attach a `grounding_summary` block rather than duplicating the full bundle.
- Do not force-create `forecast_brief.json` just to hold grounding.
- Always attach `artifacts.grounding_bundle` plus `grounding_summary` to `prepared_snapshot.json`.
- Always expose the same `grounding_summary` through `SimulationManager.get_prepare_artifact_summary(...)`.

`grounding_summary` should contain:

- `status`
- `artifact_filename`
- `evidence_count`
- citation counts by kind
- short `boundary_note`
- warnings

### Step 4 and Step 5 Report Context

- Add a separate top-level `grounding_context` block to `probabilistic_report_context.json`.
- Keep `grounding_context` separate from `aggregate_summary`, `scenario_clusters`, `sensitivity`, and `calibrated_summary`.
- Add `source_artifacts.grounding_bundle` to `probabilistic_report_context.json`.
- Preserve the current `probability_semantics` contract; upstream grounding does not change empirical or observational semantics.

### Report-Agent Prompting

- `ReportAgent` should receive a compact upstream grounding block derived from `grounding_context`, not the entire bundle dump.
- Prompt formatting must surface stable citations, explicit evidence boundaries, and warnings when grounding is partial.
- Prompt formatting must not imply that upstream grounding is comprehensive web research, exhaustive graph coverage, or calibrated evidence.

## Provenance and Evidence Boundaries

The repo should expose these boundaries explicitly:

- uploaded-source provenance is about files stored in the project directory, not about the live public web
- graph provenance is about a specific `graph_id` built from the stored project inputs and chunk settings
- code-analysis provenance is repo-local only and must cite file paths plus line numbers
- simulation outputs remain downstream empirical or observed artifacts and must stay separate from upstream grounding artifacts
- report text may cite upstream evidence IDs, but the phase does not promise statement-level citation coverage for every generated sentence

## Out Of Scope

This phase should not claim or attempt:

- live internet research, source freshness checks, or crawling beyond uploaded project files
- cross-project memory, Ruflo memory, or external research persistence
- exhaustive graph export or full graph-to-report traceability for every node and edge
- deep static-analysis completeness across dependencies, generated files, or external repos
- calibrated forecast claims sourced from upstream grounding alone
- automatic resolution of source reliability disputes beyond surfacing file identity, hashes, and locators

## Task 1: Persist Step 1 source and graph provenance artifacts

**Files:**
- Create: `backend/app/models/grounding.py`
- Modify: `backend/app/models/project.py`
- Modify: `backend/app/api/graph.py`
- Modify: `backend/app/services/graph_builder.py`
- Create: `backend/tests/unit/test_forecast_grounding.py`
- Modify: `backend/tests/unit/test_graph_builder_service.py`
- Modify: `backend/tests/unit/test_graph_data_api.py`

**Step 1: Write failing backend tests**

- Assert uploaded-source handling persists `source_manifest.json` with per-file hashes, extraction metadata, and a project-level boundary note.
- Assert graph-build completion persists `graph_build_summary.json` with chunk settings, counts, and a reference back to `source_manifest.json`.
- Assert project API payloads can expose artifact summaries without dumping the full artifacts inline.

**Step 2: Run the targeted backend tests**

Run: `cd /Users/danielbloom/Desktop/MiroFishES/backend && pytest tests/unit/test_forecast_grounding.py tests/unit/test_graph_builder_service.py tests/unit/test_graph_data_api.py -q`

**Step 3: Implement the minimal provenance artifact layer**

- Add lightweight grounding dataclasses or helpers in `backend/app/models/grounding.py`.
- Extend `ProjectManager` with helper methods for source-manifest and graph-summary paths plus read/write helpers.
- Update `/api/graph/ontology/generate` flow to write `source_manifest.json` after extraction succeeds.
- Update graph-build completion flow to write `graph_build_summary.json` after graph counts are known.
- Keep Step 1 API behavior backward-compatible while adding compact artifact-summary fields.

**Step 4: Re-run the targeted backend tests**

Run: `cd /Users/danielbloom/Desktop/MiroFishES/backend && pytest tests/unit/test_forecast_grounding.py tests/unit/test_graph_builder_service.py tests/unit/test_graph_data_api.py -q`

## Task 2: Build and attach the forecast-facing grounding bundle during Step 2 prepare

**Files:**
- Create: `backend/app/services/grounding_bundle_builder.py`
- Modify: `backend/app/models/probabilistic.py`
- Modify: `backend/app/services/simulation_manager.py`
- Modify: `backend/tests/unit/test_probabilistic_prepare.py`
- Modify: `backend/tests/unit/test_forecast_grounding.py`

**Step 1: Write failing backend tests**

- Assert probabilistic prepare writes `grounding_bundle.json` in the simulation directory.
- Assert `prepared_snapshot.json` and `get_prepare_artifact_summary(...)` expose `artifacts.grounding_bundle` and a compact `grounding_summary`.
- Assert `forecast_brief.json` gains `grounding_summary` only when a forecast brief exists.
- Assert missing `source_manifest.json` or `graph_build_summary.json` yields `partial` or `unavailable` grounding explicitly, not a silent omission.
- Assert `code_analysis_summary` can be absent or `not_requested` without breaking the bundle contract.

**Step 2: Run the targeted backend tests**

Run: `cd /Users/danielbloom/Desktop/MiroFishES/backend && pytest tests/unit/test_forecast_grounding.py tests/unit/test_probabilistic_prepare.py -q`

**Step 3: Implement the minimal grounding bundle builder**

- Build `GroundingBundleBuilder` to read project provenance artifacts and compose a bounded evidence set.
- Keep evidence selection deterministic and bounded; phase quality is about durable provenance, not perfect research ranking.
- Extend `ForecastBrief` serialization with an optional `grounding_summary`.
- Extend `SimulationManager.PREPARE_ARTIFACT_FILENAMES` and `prepared_snapshot` assembly to include `grounding_bundle`.
- Preserve backward compatibility for legacy prepare and for probabilistic prepare runs that do not include a forecast brief.

**Step 4: Re-run the targeted backend tests**

Run: `cd /Users/danielbloom/Desktop/MiroFishES/backend && pytest tests/unit/test_forecast_grounding.py tests/unit/test_probabilistic_prepare.py -q`

## Task 3: Thread upstream grounding into Step 4 and Step 5 backend context

**Files:**
- Modify: `backend/app/services/probabilistic_report_context.py`
- Modify: `backend/app/services/report_agent.py`
- Modify: `backend/app/api/report.py`
- Modify: `backend/tests/unit/test_probabilistic_report_context.py`
- Modify: `backend/tests/unit/test_probabilistic_report_api.py`

**Step 1: Write failing backend tests**

- Assert `probabilistic_report_context.json` includes a distinct `grounding_context` block plus `source_artifacts.grounding_bundle`.
- Assert `grounding_context` carries stable citations, warnings, and explicit boundary notes separate from downstream analytics.
- Assert report generation and report-agent chat receive bounded grounding context when present.
- Assert chat/report prompts remain explicit when grounding is `partial` or `unavailable`.

**Step 2: Run the targeted backend tests**

Run: `cd /Users/danielbloom/Desktop/MiroFishES/backend && pytest tests/unit/test_probabilistic_report_context.py tests/unit/test_probabilistic_report_api.py -q`

**Step 3: Implement the minimal backend context changes**

- Load `grounding_bundle.json` inside `ProbabilisticReportContextBuilder`.
- Add `grounding_context` and `source_artifacts.grounding_bundle` without changing current downstream semantics.
- Replace raw JSON dumping in report-agent grounding formatting with a compact summary plus citation list.
- Keep all prompt text explicit that upstream grounding is bounded and separate from calibration.

**Step 4: Re-run the targeted backend tests**

Run: `cd /Users/danielbloom/Desktop/MiroFishES/backend && pytest tests/unit/test_probabilistic_report_context.py tests/unit/test_probabilistic_report_api.py -q`

## Task 4: Surface grounding truth in Step 2, Step 4, and Step 5 operator surfaces

**Files:**
- Modify: `frontend/src/utils/probabilisticRuntime.js`
- Modify: `frontend/src/components/Step2EnvSetup.vue`
- Modify: `frontend/src/components/ProbabilisticReportContext.vue`
- Modify: `frontend/src/components/Step5Interaction.vue`
- Modify: `frontend/tests/unit/probabilisticRuntime.test.mjs`
- Modify: `tests/smoke/probabilistic-runtime.spec.mjs`
- Modify: `output/playwright/fixtures/probabilistic-runtime-primary.json`
- Modify: `output/playwright/fixtures/probabilistic-runtime-secondary.json`

**Step 1: Write failing frontend and smoke checks**

- Assert Step 2 can render grounding readiness, evidence counts, and boundary copy from `prepared_artifact_summary.grounding_summary`.
- Assert Step 4 cards can render upstream grounding separately from observed downstream analytics.
- Assert Step 5 helper copy can state whether report-agent chat is grounded by upstream bundle evidence, not only by downstream probabilistic context.
- Assert the existing probabilistic smoke path remains truthful with the new grounding cards or banners.

**Step 2: Run the targeted frontend tests**

Run: `cd /Users/danielbloom/Desktop/MiroFishES && node --test frontend/tests/unit/probabilisticRuntime.test.mjs`

**Step 3: Implement the smallest UI changes that expose the new contract**

- Add grounding-summary derivation helpers in `frontend/src/utils/probabilisticRuntime.js`.
- Add one Step 2 prepared-artifact card or note for upstream grounding state.
- Add one Step 4 evidence card for upstream grounding with citations and boundaries.
- Keep Step 5 UI changes small and copy-first; the main behavior change is backend report-agent grounding, not a new workflow.
- Update deterministic smoke fixtures only as needed to cover the new cards without widening scope.

**Step 4: Re-run the targeted frontend tests and build**

Run: `cd /Users/danielbloom/Desktop/MiroFishES && node --test frontend/tests/unit/probabilisticRuntime.test.mjs`

Run: `cd /Users/danielbloom/Desktop/MiroFishES/frontend && npm run build`

## Task 5: Refresh docs and operator truth

**Files:**
- Modify: `README.md`
- Modify: `docs/local-probabilistic-operator-runbook.md`
- Modify: `docs/plans/2026-03-29-forecasting-integration-hardening-wave.md`

**Step 1: Update the artifact ladder and truth boundaries**

- Add the new Step 1 project artifacts and Step 2 grounding bundle to the documented architecture.
- State exactly what later phases can assume from `grounding_bundle.json`.
- State clearly that upstream grounding is still in-repo only and does not imply comprehensive web research.

**Step 2: Update operator-facing evidence language**

- Clarify what Step 2, Step 4, and Step 5 now show about upstream grounding.
- Clarify what remains unsupported when grounding is partial or unavailable.

## Task 6: Final verification and phase closeout

**Files:**
- Verify only the surfaces changed above

**Step 1: Run the targeted backend suite**

Run: `cd /Users/danielbloom/Desktop/MiroFishES/backend && pytest tests/unit/test_forecast_grounding.py tests/unit/test_probabilistic_prepare.py tests/unit/test_probabilistic_report_context.py tests/unit/test_probabilistic_report_api.py tests/unit/test_graph_builder_service.py tests/unit/test_graph_data_api.py -q`

**Step 2: Run the targeted frontend suite**

Run: `cd /Users/danielbloom/Desktop/MiroFishES && node --test frontend/tests/unit/probabilisticRuntime.test.mjs`

**Step 3: Run the frontend build**

Run: `cd /Users/danielbloom/Desktop/MiroFishES/frontend && npm run build`

**Step 4: Run the relevant fixture-backed smoke checks**

Run: `cd /Users/danielbloom/Desktop/MiroFishES && npm run verify:smoke -- --grep "Step 4 shows the observed empirical report addendum|Step 5 shows scoped probabilistic report-agent support explicitly bounded"`

**Step 5: Run the broader repo gate**

Run: `cd /Users/danielbloom/Desktop/MiroFishES && npm run verify`

## Acceptance Criteria

- Every Step 1 project created through the normal upload flow writes `source_manifest.json` with stable file identity, hashes, extraction status, and an explicit uploaded-source boundary note.
- Every successful graph build writes `graph_build_summary.json` with graph counts, chunk settings, ontology summary, and a reference back to the source manifest.
- Every probabilistic prepare can write `grounding_bundle.json` and expose a truthful `grounding_summary` through `prepared_snapshot.json` and `get_prepare_artifact_summary(...)`.
- `forecast_brief.json` includes `grounding_summary` only when a forecast brief exists; the system does not fabricate a forecast brief just to carry grounding.
- `probabilistic_report_context.json` exposes upstream `grounding_context` separately from downstream probabilistic analytics.
- Step 4 and Step 5 surfaces can show upstream grounding readiness, boundaries, and citations without implying comprehensive research or calibrated forecasting.
- Missing source, graph, or code-analysis inputs degrade to explicit `partial` or `unavailable` states instead of silent omission.
- README, the local operator runbook, and the March 29 hardening snapshot all describe the same artifact ladder and the same grounding boundaries.

## What The Next Phase May Assume

- `grounding_bundle.json` is the canonical upstream grounding contract when present.
- `prepared_artifact_summary.grounding_summary` is the Step 2 summary surface for that contract.
- `probabilistic_report_context.grounding_context` is the Step 4 and Step 5 summary surface for that contract.
- If `grounding_bundle.json` is `partial` or `unavailable`, later phases must say so explicitly and must not present forecasts as comprehensively research-grounded.
