# Outcome Layer Expansion Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Expand the backend probabilistic outcome layer with richer observed metric families, normalized topic and metric payload shapes, and aggregate summaries that preserve semantics without fabricating unsupported truths.

**Architecture:** Extend the explicit outcome registry first, then add the minimum extractor logic needed to compute the new metrics from current logs and timestamps. Finally, harden aggregate summary normalization so richer run-level metrics and topic payloads survive through the stored ensemble pipeline with warnings intact.

**Tech Stack:** Python 3.12, Flask backend services, pytest, JSON artifact contracts under `backend/uploads/simulations/`.

---

### Task 1: Lock Down Registry Additions

**Files:**
- Modify: `backend/tests/unit/test_probabilistic_schema.py`
- Modify: `backend/app/models/probabilistic.py`

**Step 1: Write the failing test**

Add schema assertions for the new allowlisted metric families and any new metadata expected to describe them clearly.

**Step 2: Run test to verify it fails**

Run: `cd /Users/danielbloom/Desktop/MiroFishES/backend && pytest tests/unit/test_probabilistic_schema.py -v`

**Step 3: Write minimal implementation**

Extend `SUPPORTED_OUTCOME_METRIC_DEFINITIONS` with only the explicitly supported new metrics.

**Step 4: Run test to verify it passes**

Run: `cd /Users/danielbloom/Desktop/MiroFishES/backend && pytest tests/unit/test_probabilistic_schema.py -v`

### Task 2: Lock Down Richer Extraction

**Files:**
- Modify: `backend/tests/unit/test_outcome_extractor.py`
- Modify: `backend/app/services/outcome_extractor.py`

**Step 1: Write the failing test**

Add extraction tests for the new metric families, topic normalization, and explicit warning behavior when raw artifacts are insufficient.

**Step 2: Run test to verify it fails**

Run: `cd /Users/danielbloom/Desktop/MiroFishES/backend && pytest tests/unit/test_outcome_extractor.py -v`

**Step 3: Write minimal implementation**

Implement conservative extraction and normalization paths while preserving existing metric behavior.

**Step 4: Run test to verify it passes**

Run: `cd /Users/danielbloom/Desktop/MiroFishES/backend && pytest tests/unit/test_outcome_extractor.py -v`

### Task 3: Lock Down Aggregate Summary Semantics

**Files:**
- Modify: `backend/tests/unit/test_aggregate_summary.py`
- Modify: `backend/app/services/ensemble_manager.py`

**Step 1: Write the failing test**

Add summary tests for richer metric metadata, warning propagation, and normalization of inconsistent topic or metric entry shapes.

**Step 2: Run test to verify it fails**

Run: `cd /Users/danielbloom/Desktop/MiroFishES/backend && pytest tests/unit/test_aggregate_summary.py -v`

**Step 3: Write minimal implementation**

Update aggregate summary normalization without changing empirical versus observational semantics.

**Step 4: Run test to verify it passes**

Run: `cd /Users/danielbloom/Desktop/MiroFishES/backend && pytest tests/unit/test_aggregate_summary.py -v`

### Task 4: Run Focused Verification

**Files:**
- Modify: none

**Step 1: Run the focused backend suite**

Run: `cd /Users/danielbloom/Desktop/MiroFishES/backend && pytest tests/unit/test_probabilistic_schema.py tests/unit/test_outcome_extractor.py tests/unit/test_aggregate_summary.py -v`

**Step 2: Run justified downstream checks**

Run the smallest additional probabilistic tests affected by richer aggregate outputs if the previous task changes downstream expectations.

**Step 3: Summarize the boundary**

Document which metric families are now available and which remain deferred.
