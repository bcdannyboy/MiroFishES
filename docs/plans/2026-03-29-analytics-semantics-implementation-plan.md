# Analytics Semantics And Scenario Analysis Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a shared analytics-policy layer and upgrade scenario-family and sensitivity behavior so probabilistic analytics use explicit support semantics and less lossy heuristics.

**Architecture:** Introduce a shared analytics-policy service that centralizes run eligibility, support thresholds, and warning propagation. Reuse that policy in aggregate summary, scenario clustering, sensitivity analysis, and report context. Replace z-score bucket clustering with deterministic medoid-radius clustering, and replace exact-value numeric sensitivity grouping with support-aware ordered bands.

**Tech Stack:** Python 3.12, Flask backend services, pytest, JSON artifacts under `backend/uploads/simulations/`.

---

### Task 1: Define Shared Analytics Semantics

**Files:**
- Create: `backend/app/services/analytics_policy.py`
- Modify: `backend/tests/unit/test_aggregate_summary.py`
- Modify: `backend/tests/unit/test_scenario_clusterer.py`
- Modify: `backend/tests/unit/test_sensitivity_analyzer.py`

**Step 1: Write the failing test**

Add tests for:
- shared eligibility classification
- explicit support counts and exclusion reasons
- minimum-support defaults reused across analyses

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/unit/test_aggregate_summary.py backend/tests/unit/test_scenario_clusterer.py backend/tests/unit/test_sensitivity_analyzer.py`

**Step 3: Write minimal implementation**

Implement `analytics_policy.py` with mode-aware run eligibility and reusable support/warning helpers.

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/unit/test_aggregate_summary.py backend/tests/unit/test_scenario_clusterer.py backend/tests/unit/test_sensitivity_analyzer.py`

### Task 2: Upgrade Aggregate Summary Support Semantics

**Files:**
- Modify: `backend/tests/unit/test_aggregate_summary.py`
- Modify: `backend/app/services/ensemble_manager.py`

**Step 1: Write the failing test**

Add tests for:
- support counts in metric summaries
- metric-level minimum-support warnings
- additive sample-policy metadata in the artifact

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/unit/test_aggregate_summary.py`

**Step 3: Write minimal implementation**

Use the shared policy to drive aggregate inclusion and persist explicit support metadata without changing empirical semantics.

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/unit/test_aggregate_summary.py`

### Task 3: Replace Lossy Scenario Clustering

**Files:**
- Modify: `backend/tests/unit/test_scenario_clusterer.py`
- Modify: `backend/app/services/scenario_clusterer.py`

**Step 1: Write the failing test**

Add tests for:
- deterministic medoid-radius clustering
- support counts and minimum-support warnings
- preserved prototype runs and interpretable dispersion metadata
- updated schema/version metadata if the artifact meaning changes

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/unit/test_scenario_clusterer.py`

**Step 3: Write minimal implementation**

Replace bucket-signature grouping with deterministic distance-threshold clustering using standardized vectors and medoid prototypes.

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/unit/test_scenario_clusterer.py`

### Task 4: Replace Exact-Value Numeric Sensitivity Grouping

**Files:**
- Modify: `backend/tests/unit/test_sensitivity_analyzer.py`
- Modify: `backend/app/services/sensitivity_analyzer.py`

**Step 1: Write the failing test**

Add tests for:
- numeric drivers grouped into support-respecting ordered bands
- support counts and stability warnings in group summaries
- observational semantics staying explicit
- updated schema/version metadata if required

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/unit/test_sensitivity_analyzer.py`

**Step 3: Write minimal implementation**

Use the shared policy plus deterministic numeric banding to compute more defensible observational driver impacts.

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/unit/test_sensitivity_analyzer.py`

### Task 5: Propagate Support Semantics Into Report Context

**Files:**
- Modify: `backend/tests/unit/test_probabilistic_report_context.py`
- Modify: `backend/app/services/probabilistic_report_context.py`

**Step 1: Write the failing test**

Add tests for:
- support counts surfacing in report context
- scenario-family stability warnings surfacing in report context
- sensitivity remaining observational only

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/unit/test_probabilistic_report_context.py`

**Step 3: Write minimal implementation**

Thread the new artifact metadata into the report-context summaries without changing the honesty of the semantics.

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/unit/test_probabilistic_report_context.py`

### Task 6: Run Focused Verification

**Files:**
- Modify: none

**Step 1: Run the focused backend suite**

Run: `pytest backend/tests/unit/test_aggregate_summary.py backend/tests/unit/test_scenario_clusterer.py backend/tests/unit/test_sensitivity_analyzer.py backend/tests/unit/test_probabilistic_report_context.py`

**Step 2: Run one downstream regression check**

Run: `pytest backend/tests/unit/test_probabilistic_report_api.py backend/tests/unit/test_probabilistic_ensemble_api.py`

**Step 3: Summarize the new statistical boundary**

Document exactly what is now better-grounded, what remains heuristic, and why the artifacts are still empirical or observational rather than causal.
