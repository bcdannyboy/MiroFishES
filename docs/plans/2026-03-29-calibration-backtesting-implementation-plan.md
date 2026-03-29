# Calibration And Backtesting Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a minimal but real calibration/backtesting slice with durable artifacts, binary scoring, readiness gating, and report-context exposure only when valid calibration artifacts exist.

**Architecture:** Introduce additive observed-truth, backtest, and calibration artifacts beside the existing empirical aggregate summary. Keep empirical and calibrated semantics separate by using a `backtest_manager` for case-level scoring, a `calibration_manager` for binary calibration summaries, and report-context gating that surfaces calibrated summaries only when readiness-passing artifacts are present.

**Tech Stack:** Python 3.12, Flask backend services, pytest, JSON artifact contracts under `backend/uploads/simulations/`.

---

### Task 1: Extend Artifact Models And Capability Metadata

**Files:**
- Modify: `backend/tests/unit/test_probabilistic_schema.py`
- Modify: `backend/app/models/probabilistic.py`
- Modify: `backend/app/config.py`

**Step 1: Write the failing test**

Add tests for:
- observed-truth registry serialization
- backtest-summary serialization
- calibration-summary serialization
- readiness metadata validation
- any conservative config/capability exposure needed for the new slice

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/unit/test_probabilistic_schema.py backend/tests/unit/test_probabilistic_prepare.py`

**Step 3: Write minimal implementation**

Add additive dataclasses and any helper validation needed for the historical-case, backtest, and calibration artifact shapes. Keep current probabilistic prepare and empirical summary contracts intact.

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/unit/test_probabilistic_schema.py backend/tests/unit/test_probabilistic_prepare.py`

### Task 2: Add Backtest Scoring

**Files:**
- Create: `backend/app/services/backtest_manager.py`
- Create or modify: `backend/tests/unit/test_backtest_manager.py`
- Modify: `backend/app/services/ensemble_manager.py`

**Step 1: Write the failing test**

Add tests covering:
- deterministic Brier scoring on binary cases
- conservative log-score handling with clipping metadata
- unsupported metric/value-kind handling
- persistence of `observed_truth_registry.json` and `backtest_summary.json`

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/unit/test_backtest_manager.py`

**Step 3: Write minimal implementation**

Implement `backtest_manager.py` to validate stored case records, compute supported proper scores, write one backtest artifact, and expose small load/build helpers through `ensemble_manager.py`.

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/unit/test_backtest_manager.py`

### Task 3: Add Calibration Summaries And Readiness Gates

**Files:**
- Create: `backend/app/services/calibration_manager.py`
- Create or modify: `backend/tests/unit/test_calibration_manager.py`
- Modify: `backend/app/services/ensemble_manager.py`

**Step 1: Write the failing test**

Add tests for:
- reliability-bin construction
- readiness false below the 10-case threshold
- readiness true when the threshold and non-empty bin requirements are met
- calibration summaries staying limited to supported binary metrics

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/unit/test_calibration_manager.py`

**Step 3: Write minimal implementation**

Implement `calibration_manager.py` to derive calibration artifacts from persisted backtest data, compute reliability bins, and emit explicit readiness/confidence metadata without claiming recalibration.

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/unit/test_calibration_manager.py`

### Task 4: Gate Report Context On Valid Calibration Artifacts

**Files:**
- Modify: `backend/tests/unit/test_probabilistic_report_context.py`
- Modify: `backend/tests/unit/test_probabilistic_report_api.py`
- Modify: `backend/app/services/probabilistic_report_context.py`
- Modify: `backend/app/api/simulation.py`

**Step 1: Write the failing test**

Add tests for:
- no calibrated summary when calibration artifacts are absent
- no calibrated summary when readiness is false
- calibrated summary present only when a ready calibration artifact exists
- API/report behavior never implying calibration without the artifact

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/unit/test_probabilistic_report_context.py backend/tests/unit/test_probabilistic_report_api.py`

**Step 3: Write minimal implementation**

Teach the report-context builder and any needed API surface to load calibration artifacts conservatively and surface them only when the readiness gate passes.

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/unit/test_probabilistic_report_context.py backend/tests/unit/test_probabilistic_report_api.py`

### Task 5: Run Focused Verification

**Files:**
- Modify: none

**Step 1: Run the focused backend suite**

Run: `pytest backend/tests/unit/test_probabilistic_schema.py backend/tests/unit/test_backtest_manager.py backend/tests/unit/test_calibration_manager.py backend/tests/unit/test_probabilistic_report_context.py backend/tests/unit/test_probabilistic_report_api.py backend/tests/unit/test_probabilistic_prepare.py`

**Step 2: Run one downstream storage check**

Run: `pytest backend/tests/unit/test_ensemble_storage.py backend/tests/unit/test_probabilistic_ensemble_api.py`

**Step 3: Summarize the new calibration boundary**

Document exactly what now qualifies as calibrated in the codebase and what remains empirical-only or future work.
