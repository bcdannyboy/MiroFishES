# Stochastic Probabilistic Simulation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a probabilistic ensemble simulation capability to MiroFishES that preserves the current single-run product while introducing explicit uncertainty specs, seeded multi-run orchestration, structured outcome aggregation, and uncertainty-aware reporting.

**Architecture:** Keep the current graph, profile-generation, simulation-config, OASIS runtime, and report pipeline intact. Add a new probabilistic sidecar architecture consisting of uncertainty specs, resolved per-run configs, run manifests, per-run storage, aggregate artifacts, and a report surface that consumes aggregate metrics instead of inferring probabilities from one trajectory.

**Tech Stack:** Flask, Python dataclasses and service classes, OASIS runtime scripts, JSON artifact storage under `backend/uploads`, Vue frontend, pytest.

---

### Task 1: Introduce Probabilistic Core Schemas

**Files:**
- Create: `backend/app/models/probabilistic.py`
- Modify: `backend/app/services/simulation_config_generator.py`
- Modify: `backend/app/services/simulation_manager.py`
- Test: `backend/tests/unit/test_probabilistic_schema.py`

**Step 1: Write the failing test**

Create tests that assert:

- `RandomVariableSpec` validates supported distributions.
- `EnsembleSpec` validates run counts and seed policy.
- `RunManifest` serializes deterministic metadata.
- `SimulationManager` can persist and reload `uncertainty_spec.json`.

**Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/danielbloom/Desktop/MiroFishES/backend && pytest backend/tests/unit/test_probabilistic_schema.py -q
```

Expected:

- failure because `backend/app/models/probabilistic.py` and new persistence behavior do not exist yet.

**Step 3: Write minimal implementation**

Add dataclasses and helpers for:

- `RandomVariableSpec`
- `UncertaintySpec`
- `EnsembleSpec`
- `RunManifest`
- `OutcomeMetricDefinition`

Add persistence helpers in `SimulationManager` for:

- `simulation_config.base.json`
- `uncertainty_spec.json`
- `outcome_spec.json`

**Step 4: Run test to verify it passes**

Run:

```bash
cd /Users/danielbloom/Desktop/MiroFishES/backend && pytest backend/tests/unit/test_probabilistic_schema.py -q
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add backend/app/models/probabilistic.py backend/app/services/simulation_config_generator.py backend/app/services/simulation_manager.py backend/tests/unit/test_probabilistic_schema.py
git commit -m "feat: add probabilistic simulation core schemas"
```

### Task 2: Split Baseline Config From Uncertainty Spec

**Files:**
- Modify: `backend/app/services/simulation_config_generator.py`
- Modify: `backend/app/services/simulation_manager.py`
- Modify: `backend/app/api/simulation.py`
- Test: `backend/tests/unit/test_probabilistic_prepare.py`

**Step 1: Write the failing test**

Create tests that assert:

- prepare flow can emit a baseline scalar config and a probabilistic spec in the same simulation directory,
- legacy mode still emits a usable single-run config,
- probabilistic mode defaults are stable and versioned.

**Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/danielbloom/Desktop/MiroFishES/backend && pytest backend/tests/unit/test_probabilistic_prepare.py -q
```

Expected:

- failure because prepare mode still writes only `simulation_config.json`.

**Step 3: Write minimal implementation**

Change prepare output so it writes:

- `simulation_config.base.json`
- legacy-compatible `simulation_config.json` in non-probabilistic mode
- `uncertainty_spec.json`
- `outcome_spec.json`
- `prepared_snapshot.json`

Extend `/api/simulation/prepare` to accept:

- `probabilistic_mode`
- `uncertainty_profile`
- `outcome_metrics`

**Step 4: Run test to verify it passes**

Run:

```bash
cd /Users/danielbloom/Desktop/MiroFishES/backend && pytest backend/tests/unit/test_probabilistic_prepare.py -q
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add backend/app/services/simulation_config_generator.py backend/app/services/simulation_manager.py backend/app/api/simulation.py backend/tests/unit/test_probabilistic_prepare.py
git commit -m "feat: split baseline config from uncertainty artifacts"
```

### Task 3: Add Uncertainty Resolution For One Concrete Run

**Files:**
- Create: `backend/app/services/uncertainty_resolver.py`
- Modify: `backend/app/models/probabilistic.py`
- Test: `backend/tests/unit/test_uncertainty_resolver.py`

**Step 1: Write the failing test**

Create tests that assert:

- fixed fields remain unchanged,
- beta, categorical, truncated normal, and lognormal samples resolve correctly,
- sampled values are recorded in `RunManifest`,
- the same seed produces the same resolved config.

**Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/danielbloom/Desktop/MiroFishES/backend && pytest backend/tests/unit/test_uncertainty_resolver.py -q
```

Expected:

- failure because the resolver does not exist.

**Step 3: Write minimal implementation**

Implement:

- distribution sampling helpers,
- object-path patching into resolved config,
- seeded resolution,
- manifest capture of sampled values,
- validation that resolved values stay within support bounds.

**Step 4: Run test to verify it passes**

Run:

```bash
cd /Users/danielbloom/Desktop/MiroFishES/backend && pytest backend/tests/unit/test_uncertainty_resolver.py -q
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add backend/app/services/uncertainty_resolver.py backend/app/models/probabilistic.py backend/tests/unit/test_uncertainty_resolver.py
git commit -m "feat: add seeded uncertainty resolution"
```

### Task 4: Add Ensemble And Run Storage Management

**Files:**
- Create: `backend/app/services/ensemble_manager.py`
- Modify: `backend/app/services/simulation_manager.py`
- Modify: `backend/app/api/simulation.py`
- Test: `backend/tests/unit/test_ensemble_storage.py`

**Step 1: Write the failing test**

Create tests that assert:

- an ensemble directory is created under one prepared simulation,
- each run receives its own `run_<run_id>/` directory,
- `run_manifest.json` and `resolved_config.json` live inside the run directory,
- cleanup of one run does not destroy sibling runs.

**Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/danielbloom/Desktop/MiroFishES/backend && pytest backend/tests/unit/test_ensemble_storage.py -q
```

Expected:

- failure because all current runtime artifacts live directly under `<simulation_id>/`.

**Step 3: Write minimal implementation**

Implement:

- ensemble creation,
- run-id generation,
- run directory creation,
- metadata persistence,
- helpers to list runs and load manifests.

Add endpoints for:

- create ensemble
- inspect ensemble
- list ensemble runs

**Step 4: Run test to verify it passes**

Run:

```bash
cd /Users/danielbloom/Desktop/MiroFishES/backend && pytest backend/tests/unit/test_ensemble_storage.py -q
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add backend/app/services/ensemble_manager.py backend/app/services/simulation_manager.py backend/app/api/simulation.py backend/tests/unit/test_ensemble_storage.py
git commit -m "feat: add ensemble and run storage management"
```

### Task 5: Make Runtime Execution Run-Scoped And Seeded

**Files:**
- Modify: `backend/app/services/simulation_runner.py`
- Modify: `backend/scripts/run_parallel_simulation.py`
- Modify: `backend/scripts/run_twitter_simulation.py`
- Modify: `backend/scripts/run_reddit_simulation.py`
- Modify: `backend/scripts/action_logger.py`
- Test: `backend/tests/unit/test_seeded_runtime.py`

**Step 1: Write the failing test**

Create tests that assert:

- `SimulationRunner` can launch multiple run IDs under one simulation without key collisions,
- run subprocess commands include `--run-id`, `--seed`, and `--run-dir`,
- seeded activation logic produces stable active-agent selection for identical inputs.

**Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/danielbloom/Desktop/MiroFishES/backend && pytest backend/tests/unit/test_seeded_runtime.py -q
```

Expected:

- failure because runtime is keyed only by `simulation_id` and uses module-global random state.

**Step 3: Write minimal implementation**

Refactor runtime so:

- process maps are keyed by `run_id`,
- each run writes logs into its own directory,
- RNG instances are created from explicit seeds,
- parallel mode uses separate RNG objects per platform,
- action logs optionally carry `run_id`.

**Step 4: Run test to verify it passes**

Run:

```bash
cd /Users/danielbloom/Desktop/MiroFishES/backend && pytest backend/tests/unit/test_seeded_runtime.py -q
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add backend/app/services/simulation_runner.py backend/scripts/run_parallel_simulation.py backend/scripts/run_twitter_simulation.py backend/scripts/run_reddit_simulation.py backend/scripts/action_logger.py backend/tests/unit/test_seeded_runtime.py
git commit -m "feat: make runtime execution seeded and run-scoped"
```

### Task 6: Add Per-Run Outcome Extraction

**Files:**
- Create: `backend/app/services/outcome_extractor.py`
- Modify: `backend/app/services/simulation_runner.py`
- Modify: `backend/app/api/simulation.py`
- Test: `backend/tests/unit/test_outcome_extractor.py`

**Step 1: Write the failing test**

Create tests that assert:

- action logs can be converted into standardized metrics,
- binary, categorical, continuous, and count metrics serialize predictably,
- metric extraction writes `metrics.json` into the run directory.

**Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/danielbloom/Desktop/MiroFishES/backend && pytest backend/tests/unit/test_outcome_extractor.py -q
```

Expected:

- failure because no standardized metrics file exists.

**Step 3: Write minimal implementation**

Implement metric extraction for first-pass metrics:

- total actions,
- time to first official post,
- top agents by activity,
- platform action share,
- peak round volume,
- dominant topic or hot-topic persistence.

Hook extraction into run completion.

**Step 4: Run test to verify it passes**

Run:

```bash
cd /Users/danielbloom/Desktop/MiroFishES/backend && pytest backend/tests/unit/test_outcome_extractor.py -q
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add backend/app/services/outcome_extractor.py backend/app/services/simulation_runner.py backend/app/api/simulation.py backend/tests/unit/test_outcome_extractor.py
git commit -m "feat: add per-run outcome extraction"
```

### Task 7: Add Ensemble Aggregation, Clustering, And Sensitivity

**Files:**
- Create: `backend/app/services/scenario_clusterer.py`
- Create: `backend/app/services/sensitivity_analyzer.py`
- Modify: `backend/app/services/ensemble_manager.py`
- Modify: `backend/app/api/simulation.py`
- Test: `backend/tests/unit/test_ensemble_aggregation.py`

**Step 1: Write the failing test**

Create tests that assert:

- aggregated outcome frequencies are computed correctly,
- runs can be grouped into scenario clusters from structured metrics,
- perturbation runs produce ranked sensitivity outputs,
- ensemble summary artifacts are persisted.

**Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/danielbloom/Desktop/MiroFishES/backend && pytest backend/tests/unit/test_ensemble_aggregation.py -q
```

Expected:

- failure because aggregate artifacts do not exist.

**Step 3: Write minimal implementation**

Implement:

- empirical outcome probabilities,
- quantile summaries,
- simple feature-vector clustering over per-run metrics,
- first-pass one-at-a-time perturbation sensitivity ranking,
- `aggregate_summary.json`, `scenario_clusters.json`, and `sensitivity.json`.

**Step 4: Run test to verify it passes**

Run:

```bash
cd /Users/danielbloom/Desktop/MiroFishES/backend && pytest backend/tests/unit/test_ensemble_aggregation.py -q
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add backend/app/services/scenario_clusterer.py backend/app/services/sensitivity_analyzer.py backend/app/services/ensemble_manager.py backend/app/api/simulation.py backend/tests/unit/test_ensemble_aggregation.py
git commit -m "feat: add ensemble aggregation and scenario clustering"
```

### Task 8: Extend Report Generation To Consume Ensemble Artifacts

**Files:**
- Modify: `backend/app/services/report_agent.py`
- Modify: `backend/app/api/report.py`
- Create: `backend/tests/unit/test_probabilistic_report_context.py`

**Step 1: Write the failing test**

Create tests that assert:

- report generation can target an `ensemble_id`,
- report context prefers aggregate probabilistic artifacts over single-run raw logs,
- probabilities are labeled as empirical ensemble estimates unless calibrated.

**Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/danielbloom/Desktop/MiroFishES/backend && pytest backend/tests/unit/test_probabilistic_report_context.py -q
```

Expected:

- failure because reports only understand one `simulation_id`.

**Step 3: Write minimal implementation**

Add:

- ensemble-aware report context loading,
- new report sections or cards for top outcomes, scenario families, drivers, and tail risks,
- explicit probability provenance labels,
- optional `probabilistic_report_context.json` persistence.

**Step 4: Run test to verify it passes**

Run:

```bash
cd /Users/danielbloom/Desktop/MiroFishES/backend && pytest backend/tests/unit/test_probabilistic_report_context.py -q
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add backend/app/services/report_agent.py backend/app/api/report.py backend/tests/unit/test_probabilistic_report_context.py
git commit -m "feat: add ensemble-aware probabilistic reporting"
```

### Task 9: Add Probabilistic Frontend Controls And Views

**Files:**
- Modify: `frontend/src/components/Step2EnvSetup.vue`
- Modify: `frontend/src/components/Step3Simulation.vue`
- Modify: `frontend/src/components/Step4Report.vue`
- Modify: `frontend/src/components/Step5Interaction.vue`
- Modify: `frontend/src/api/simulation.js`
- Modify: `frontend/src/api/report.js`
- Optionally Modify: `frontend/src/router/index.js`

**Step 1: Write the failing test**

If frontend test infrastructure exists by then, add component tests. If it does not, write a manual verification checklist first and treat it as the failing artifact:

- Step 2 can toggle probabilistic mode and show uncertainty summaries.
- Step 3 can display ensemble progress and run counts.
- Step 4 can render outcome distributions, scenario clusters, and sensitivity cards.
- Step 5 can query the report agent about probabilistic artifacts.

**Step 2: Run test to verify it fails**

Run the available frontend test or manual smoke path and verify the UI cannot yet render any of the above.

**Step 3: Write minimal implementation**

Add:

- probabilistic mode controls in Step 2,
- ensemble monitor in Step 3,
- probabilistic report cards in Step 4,
- ensemble-aware chat context in Step 5,
- API bindings for ensemble summary endpoints.

**Step 4: Run test to verify it passes**

Re-run the smoke path and verify:

- probabilistic prepare works,
- ensemble run progress renders,
- probabilistic report cards render,
- chat references aggregate artifacts.

**Step 5: Commit**

```bash
git add frontend/src/components/Step2EnvSetup.vue frontend/src/components/Step3Simulation.vue frontend/src/components/Step4Report.vue frontend/src/components/Step5Interaction.vue frontend/src/api/simulation.js frontend/src/api/report.js frontend/src/router/index.js
git commit -m "feat: add probabilistic ensemble UI surfaces"
```

### Task 10: Add Graph Confidence And Calibration In Phase 2

**Files:**
- Modify: `backend/app/models/project.py`
- Modify: `backend/app/services/ontology_generator.py`
- Modify: `backend/app/services/graph_builder.py`
- Modify: `backend/app/services/zep_entity_reader.py`
- Modify: `backend/app/services/zep_tools.py`
- Create: `backend/app/services/calibration_manager.py`
- Test: `backend/tests/unit/test_graph_uncertainty.py`
- Test: `backend/tests/unit/test_calibration_manager.py`

**Step 1: Write the failing test**

Create tests that assert:

- node and edge confidence attributes are preserved end-to-end,
- graph read helpers surface those fields,
- calibration artifacts can be fitted, versioned, and loaded for recurring targets.

**Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/danielbloom/Desktop/MiroFishES/backend && pytest backend/tests/unit/test_graph_uncertainty.py backend/tests/unit/test_calibration_manager.py -q
```

Expected:

- failure because graph confidence propagation and calibration management do not exist.

**Step 3: Write minimal implementation**

Add:

- graph-side confidence attributes,
- read-path propagation,
- basic calibration artifact persistence,
- score and provenance fields for calibrated targets.

**Step 4: Run test to verify it passes**

Run:

```bash
cd /Users/danielbloom/Desktop/MiroFishES/backend && pytest backend/tests/unit/test_graph_uncertainty.py backend/tests/unit/test_calibration_manager.py -q
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add backend/app/models/project.py backend/app/services/ontology_generator.py backend/app/services/graph_builder.py backend/app/services/zep_entity_reader.py backend/app/services/zep_tools.py backend/app/services/calibration_manager.py backend/tests/unit/test_graph_uncertainty.py backend/tests/unit/test_calibration_manager.py
git commit -m "feat: add graph confidence propagation and calibration artifacts"
```

## Verification Checklist

- Legacy single-run simulation still works end to end.
- Probabilistic prepare emits baseline and uncertainty artifacts without breaking legacy config consumers.
- Multiple runs for one simulation can execute concurrently without collisions.
- Identical seeds reproduce identical resolved configs and runtime sampling decisions where supported.
- Aggregate probabilities are computed from stored run metrics, not from report prose.
- Report cards label empirical, calibrated, and exemplar outputs distinctly.
- Frontend can inspect both ensemble-level and run-level detail.

## Rollout Order

1. Tasks 1 through 3
2. Task 4
3. Tasks 5 and 6
4. Task 7
5. Tasks 8 and 9
6. Task 10

## Notes

- Do not attempt calibration before Tasks 1 through 9 are stable.
- Do not claim complete determinism across external LLM behavior until the system explicitly versions and discloses those limits.
- Do not refactor the existing single-run path away until the ensemble path is proven in production.
