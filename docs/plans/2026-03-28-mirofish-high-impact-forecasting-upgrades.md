# MiroFish High-Impact Forecasting Upgrades Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Upgrade MiroFishES from a bounded empirical simulation pipeline into a more decision-useful forecasting system with richer measurable outcomes, stronger uncertainty structure, calibrated confidence, and probabilistic-native report synthesis.

**Architecture:** Start by expanding what the system can measure, because every later improvement depends on outcome quality. Then unify analytics semantics and upgrade clustering and sensitivity so scenario analysis is statistically coherent. After that, add calibration and backtesting so any confidence claim is empirically grounded. Finally, expand uncertainty modeling and wire the probabilistic artifact layer directly into report and interaction flows.

**Tech Stack:** Python 3.11+, Flask, pytest, Vue 3, Vite, Playwright, OASIS runtime scripts, Zep graph services, JSON artifact contracts under `backend/uploads/simulations/`.

---

## Status Note: 2026-03-29

The bounded control-plane slices described in this plan are now largely present in the repo:

- forecast briefs exist as first-class prepare artifacts
- richer outcome metrics, structured uncertainty, analytics semantics, backtesting, and calibration provenance all have implemented artifact contracts
- Step 4 and the Step 5 report-agent lane now consume scoped probabilistic report context directly instead of treating it only as a sidecar

What still remains for final reassessment is narrower than this original plan:

- integration cleanup and contract drift checks
- stronger end-to-end verification coverage
- a dedicated compare workspace instead of prompt-only compare entry points
- broader calibration/recalibration depth beyond the current binary backtested v1
- release-grade operator hardening rather than local bounded evidence only

Read this document now as the north-star sequence that informed the implemented waves, not as a list of untouched future work.

## Priority Summary

| Priority | Improvement | Impact | Effort | Why First |
| --- | --- | --- | --- | --- |
| P1 | Expand outcome registry and truth mapping | Very high | Medium, 4 to 6 engineer-days | Current outcome space is too thin to support high-confidence forecasting |
| P2 | Unify analytics semantics and upgrade scenario analytics | Very high | Medium, 5 to 7 engineer-days | Current summary, clustering, and sensitivity layers use inconsistent eligibility rules |
| P3 | Add calibration and backtesting layer | Very high | High, 7 to 10 engineer-days | `high confidence` is not defensible without historical scoring and recalibration |
| P4 | Expand uncertainty modeling and controlled perturbation support | High | High, 6 to 9 engineer-days | Current uncertainty space is mostly independent scalar perturbations |
| P5 | Make report and interaction flows probabilistic-native | High | Medium, 4 to 6 engineer-days | Probabilistic context is still mostly a sidecar, not the report's reasoning substrate |

## Recommended Delivery Order

1. Land P1 first.
2. Land P2 second.
3. Land P3 third.
4. Land P4 fourth.
5. Land P5 fifth.

Do not start P3 before P1 and P2 are merged. Calibration on poor targets and inconsistent samples will create false rigor.

---

### Task 1: Expand Outcome Registry and Truth Mapping

**Impact:** Very high

**Effort:** Medium, 4 to 6 engineer-days

**Files:**
- Modify: `backend/app/models/probabilistic.py`
- Modify: `backend/app/services/outcome_extractor.py`
- Modify: `backend/app/services/ensemble_manager.py`
- Modify: `backend/app/services/probabilistic_report_context.py`
- Modify: `backend/app/api/simulation.py`
- Modify: `frontend/src/utils/probabilisticRuntime.js`
- Modify: `frontend/src/components/ProbabilisticReportContext.vue`
- Test: `backend/tests/unit/test_probabilistic_schema.py`
- Test: `backend/tests/unit/test_outcome_extractor.py`
- Test: `backend/tests/unit/test_aggregate_summary.py`
- Test: `frontend/tests/unit/probabilisticRuntime.test.mjs`

**Target outcome additions:**
- Binary event occurrence metrics
- Time-to-event metrics
- Severity-band metrics
- Reach and concentration metrics
- Cross-platform lag metrics
- Sentiment and polarization metrics
- Topic-shift or topic-dominance metrics
- Intervention uptake metrics

**Implementation Steps:**
1. Add failing schema tests for new metric IDs in `backend/tests/unit/test_probabilistic_schema.py`.
2. Run `cd /Users/danielbloom/Desktop/MiroFishES/backend && pytest tests/unit/test_probabilistic_schema.py -v`.
3. Extend `SUPPORTED_OUTCOME_METRIC_DEFINITIONS` in `backend/app/models/probabilistic.py`.
4. Add extractor fixtures covering the new metric families in `backend/tests/unit/test_outcome_extractor.py`.
5. Run `cd /Users/danielbloom/Desktop/MiroFishES/backend && pytest tests/unit/test_outcome_extractor.py -v`.
6. Implement minimal extraction paths in `backend/app/services/outcome_extractor.py` without changing existing count behavior.
7. Add aggregate-summary tests for continuous, binary, and categorical handling in `backend/tests/unit/test_aggregate_summary.py`.
8. Run `cd /Users/danielbloom/Desktop/MiroFishES/backend && pytest tests/unit/test_aggregate_summary.py -v`.
9. Update `backend/app/services/ensemble_manager.py` so summary payloads preserve the new metric metadata cleanly.
10. Update `backend/app/services/probabilistic_report_context.py` to expose the new metrics through `top_outcomes`.
11. Update `frontend/src/utils/probabilisticRuntime.js` to render richer summary text without implying calibration.
12. Add or update frontend unit tests in `frontend/tests/unit/probabilisticRuntime.test.mjs`.
13. Run `cd /Users/danielbloom/Desktop/MiroFishES/frontend && npm test -- probabilisticRuntime.test.mjs`.
14. Run `cd /Users/danielbloom/Desktop/MiroFishES && npm run verify`.

**Definition of done:**
- Outcome registry supports more than simple action counts.
- Extracted metrics are stable and test-covered.
- Aggregate summaries and report context can carry those metrics without special cases.
- Frontend renders the richer metrics as empirical or observational only.

---

### Task 2: Unify Analytics Semantics and Upgrade Scenario Analytics

**Impact:** Very high

**Effort:** Medium, 5 to 7 engineer-days

**Files:**
- Modify: `backend/app/services/ensemble_manager.py`
- Modify: `backend/app/services/scenario_clusterer.py`
- Modify: `backend/app/services/sensitivity_analyzer.py`
- Modify: `backend/app/services/probabilistic_report_context.py`
- Modify: `frontend/src/utils/probabilisticRuntime.js`
- Modify: `frontend/src/components/Step3Simulation.vue`
- Modify: `frontend/src/components/ProbabilisticReportContext.vue`
- Test: `backend/tests/unit/test_scenario_clusterer.py`
- Test: `backend/tests/unit/test_sensitivity_analyzer.py`
- Test: `backend/tests/unit/test_probabilistic_report_context.py`

**Design rules:**
- Every analytics artifact must expose both `complete_only` and `all_observed` sample semantics, or one explicit canonical rule reused everywhere.
- Sensitivity must not group continuous values by exact identity without binning or minimum-support checks.
- Clustering should operate on richer feature vectors than final count metrics alone.

**Implementation Steps:**
1. Add failing tests that demonstrate current sample inconsistency across summary, clusters, and sensitivity.
2. Run `cd /Users/danielbloom/Desktop/MiroFishES/backend && pytest tests/unit/test_scenario_clusterer.py tests/unit/test_sensitivity_analyzer.py tests/unit/test_probabilistic_report_context.py -v`.
3. Introduce one shared run-eligibility helper in `backend/app/services/` or inside `ensemble_manager.py` and reuse it from clustering and sensitivity.
4. Change aggregate summary in `backend/app/services/ensemble_manager.py` to report sample semantics explicitly.
5. Update `backend/app/services/scenario_clusterer.py` to build feature vectors from richer metrics and timeline-derived features where available.
6. Add deterministic binning for continuous drivers and minimum group-size rules in `backend/app/services/sensitivity_analyzer.py`.
7. Add stability warnings when cluster support or sensitivity support is too small.
8. Update `backend/app/services/probabilistic_report_context.py` so its `quality_summary` reports exact supporting sample rules.
9. Update frontend warning and provenance copy in `frontend/src/utils/probabilisticRuntime.js`.
10. Update Step 3 and Step 4 cards to show support counts and sample mode, not just status chips.
11. Run targeted backend tests again.
12. Run `cd /Users/danielbloom/Desktop/MiroFishES && npm run verify`.

**Definition of done:**
- Summary, clustering, sensitivity, and report context agree on which runs count.
- Continuous drivers no longer create misleading singleton sensitivity groups.
- Operators can see support counts and degraded-run effects directly.

---

### Task 3: Add Calibration and Backtesting Layer

**Impact:** Very high

**Effort:** High, 7 to 10 engineer-days

**Files:**
- Create: `backend/app/services/calibration_manager.py`
- Create: `backend/app/services/backtest_manager.py`
- Create: `backend/app/models/calibration.py`
- Modify: `backend/app/config.py`
- Modify: `backend/app/api/simulation.py`
- Modify: `backend/app/services/probabilistic_report_context.py`
- Modify: `backend/app/services/ensemble_manager.py`
- Modify: `frontend/src/utils/probabilisticRuntime.js`
- Modify: `frontend/src/components/ProbabilisticReportContext.vue`
- Test: `backend/tests/unit/test_calibration_manager.py`
- Test: `backend/tests/unit/test_backtest_manager.py`
- Test: `backend/tests/unit/test_probabilistic_report_context.py`

**Backtest scope for v1:**
- Historical case registry with frozen input snapshot
- Observed truth payload per case
- Brier score
- Log score
- CRPS for supported continuous metrics
- Reliability bins and calibration summary
- Confidence gating rules for any future `high confidence` label

**Implementation Steps:**
1. Add config tests or basic unit coverage for calibration-off and calibration-on behavior.
2. Create `backend/app/models/calibration.py` with versioned artifact contracts.
3. Create failing tests for calibration scoring in `backend/tests/unit/test_calibration_manager.py`.
4. Run `cd /Users/danielbloom/Desktop/MiroFishES/backend && pytest tests/unit/test_calibration_manager.py -v`.
5. Implement score computation in `backend/app/services/calibration_manager.py`.
6. Create failing tests for case ingestion and rolling evaluation in `backend/tests/unit/test_backtest_manager.py`.
7. Implement benchmark-case storage and rolling evaluation in `backend/app/services/backtest_manager.py`.
8. Add new API responses in `backend/app/api/simulation.py` for calibration availability and calibration summaries.
9. Update `backend/app/services/probabilistic_report_context.py` to include calibration provenance only when valid calibration artifacts exist.
10. Update frontend capability rendering so calibrated labels remain hidden unless artifacts are present and valid.
11. Add confidence gating logic in `frontend/src/utils/probabilisticRuntime.js`.
12. Run backend unit tests for calibration and report context.
13. Run `cd /Users/danielbloom/Desktop/MiroFishES && npm run verify`.

**Definition of done:**
- Historical cases can be scored automatically.
- Calibration artifacts exist separately from empirical summary artifacts.
- UI cannot imply calibrated confidence unless calibration artifacts exist and pass readiness checks.

---

### Task 4: Expand Uncertainty Modeling and Controlled Perturbation Support

**Impact:** High

**Effort:** High, 6 to 9 engineer-days

**Files:**
- Modify: `backend/app/models/probabilistic.py`
- Modify: `backend/app/services/simulation_manager.py`
- Modify: `backend/app/services/uncertainty_resolver.py`
- Modify: `backend/app/services/ensemble_manager.py`
- Create: `backend/app/services/experiment_design.py`
- Test: `backend/tests/unit/test_probabilistic_schema.py`
- Test: `backend/tests/unit/test_probabilistic_prepare.py`
- Test: `backend/tests/unit/test_uncertainty_resolver.py`
- Test: `backend/tests/unit/test_ensemble_storage.py`

**Target additions:**
- Correlated variable groups
- Conditional variables
- Exogenous event process definitions
- Narrative scenario templates to parameter deltas
- Controlled perturbation plans using Latin hypercube or Sobol-style sampling metadata
- Assumption ledger per run

**Implementation Steps:**
1. Add failing schema tests for correlated and conditional uncertainty contracts.
2. Run `cd /Users/danielbloom/Desktop/MiroFishES/backend && pytest tests/unit/test_probabilistic_schema.py tests/unit/test_uncertainty_resolver.py -v`.
3. Extend `backend/app/models/probabilistic.py` with new uncertainty contract types while preserving backward compatibility.
4. Add `backend/app/services/experiment_design.py` with deterministic experiment-plan generation.
5. Update `backend/app/services/simulation_manager.py` so prepare can emit structured scenario templates and assumption metadata.
6. Update `backend/app/services/uncertainty_resolver.py` to resolve correlated or conditional groups coherently.
7. Update `backend/app/services/ensemble_manager.py` so run manifests store the new assumption ledger cleanly.
8. Add tests for deterministic reproducibility and backward-compatible legacy behavior.
9. Run targeted backend tests.
10. Run `cd /Users/danielbloom/Desktop/MiroFishES && npm run verify`.

**Definition of done:**
- MiroFish can generate coherent worlds, not just disconnected scalar perturbations.
- Each run has an inspectable assumption ledger.
- Experiment design metadata is available for stronger future sensitivity analysis.

---

### Task 5: Make Report and Interaction Flows Probabilistic-Native

**Impact:** High

**Effort:** Medium, 4 to 6 engineer-days

**Files:**
- Modify: `backend/app/api/report.py`
- Modify: `backend/app/services/report_agent.py`
- Modify: `backend/app/services/probabilistic_report_context.py`
- Modify: `backend/app/api/simulation.py`
- Modify: `frontend/src/components/ProbabilisticReportContext.vue`
- Modify: `frontend/src/components/Step5Interaction.vue`
- Modify: `frontend/src/utils/probabilisticRuntime.js`
- Test: `backend/tests/unit/test_probabilistic_report_context.py`
- Test: `backend/tests/unit/test_probabilistic_report_api.py`
- Test: `frontend/tests/unit/probabilisticRuntime.test.mjs`

**Target behavior:**
- Step 4 report generation can reason over probabilistic context during outline and section generation.
- Step 5 report-agent chat can build probabilistic context even without a saved report ID when `simulation_id`, `ensemble_id`, and `run_id` are present.
- Evidence objects are inspectable: support, provenance, warnings, representative runs, selected-run assumptions.

**Implementation Steps:**
1. Add failing tests proving report generation currently ignores probabilistic context at generation time.
2. Run `cd /Users/danielbloom/Desktop/MiroFishES/backend && pytest tests/unit/test_probabilistic_report_api.py tests/unit/test_probabilistic_report_context.py -v`.
3. Update `backend/app/api/report.py` so scoped report generation builds report context before dispatching report-agent work.
4. Update `backend/app/services/report_agent.py` prompts to preserve probability semantics, warnings, and support counts explicitly.
5. Update Step 5 report-agent chat in `backend/app/api/report.py` so direct scoped chat can build or fetch report context without requiring a saved `report_id`.
6. Update frontend utilities and Step 5 copy to distinguish report-agent probabilistic scope from legacy agent-chat and survey scope.
7. Expand `frontend/src/components/ProbabilisticReportContext.vue` to show provenance, support, representative runs, and selected-run assumptions.
8. Run targeted backend and frontend tests.
9. Run `cd /Users/danielbloom/Desktop/MiroFishES && npm run verify`.

**Definition of done:**
- Probabilistic context is part of report reasoning, not only post-hoc display.
- Report-agent chat can answer from scoped ensemble/run context directly.
- Operators can inspect why a scenario is considered likely or uncertain.

---

## Milestone Checkpoints

### Milestone A: Measurable Forecast Quality
- Task 1 merged
- Task 2 merged
- Result: richer outputs and coherent ensemble analytics

### Milestone B: Defensible Confidence
- Task 3 merged
- Result: calibration and backtesting artifacts exist

### Milestone C: Coherent Worlds
- Task 4 merged
- Result: scenario generation reflects structured uncertainty

### Milestone D: Operator-Useful Synthesis
- Task 5 merged
- Result: reports and chat use probabilistic evidence directly

## Verification Commands

Run after each task block:

```bash
cd /Users/danielbloom/Desktop/MiroFishES && npm run verify
```

Run targeted backend checks while iterating:

```bash
cd /Users/danielbloom/Desktop/MiroFishES/backend && pytest tests/unit/test_probabilistic_schema.py tests/unit/test_outcome_extractor.py tests/unit/test_aggregate_summary.py tests/unit/test_scenario_clusterer.py tests/unit/test_sensitivity_analyzer.py tests/unit/test_probabilistic_report_context.py -v
```

Run targeted frontend checks while iterating:

```bash
cd /Users/danielbloom/Desktop/MiroFishES/frontend && npm test -- probabilisticRuntime.test.mjs
```

## Suggested Commit Boundaries

1. `feat: expand probabilistic outcome metric registry`
2. `feat: unify ensemble analytics sample semantics`
3. `feat: add calibration and backtesting artifacts`
4. `feat: add structured uncertainty and experiment design`
5. `feat: make probabilistic report context generation-native`

## Recommended Staffing

- One backend engineer can deliver Tasks 1 through 3 sequentially.
- A second backend engineer can work on Task 4 once Task 1 is stable.
- A frontend engineer can start the read-path work for Tasks 2 and 5 once the backend contracts are settled.
- If only one engineer is available, still do not reorder Tasks 3 through 5 ahead of Tasks 1 and 2.

## Recommendation

If only one improvement can be funded now, do **Task 1**.

If two improvements can be funded now, do **Task 1** and **Task 3**.

If the goal is the highest near-term user-visible trust gain, do **Task 1**, **Task 2**, and **Task 5** in that order.
