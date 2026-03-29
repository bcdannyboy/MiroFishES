# Structured Uncertainty Experiment Design Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a structured uncertainty and experiment-design layer that preserves backward compatibility while making ensemble assumptions inspectable and reproducible.

**Architecture:** Extend the probabilistic schema with additive structured uncertainty types, introduce a deterministic experiment-design service centered on Latin hypercube metadata, and upgrade resolver plus ensemble persistence to consume stored design rows rather than inventing hidden randomness at resolution time. Keep legacy `random_variables` behavior intact when the new fields are absent.

**Tech Stack:** Python 3.12, Flask backend services, pytest, JSON artifact contracts under `backend/uploads/simulations/`.

---

### Task 1: Extend The Schema Contracts

**Files:**
- Modify: `backend/tests/unit/test_probabilistic_schema.py`
- Modify: `backend/app/models/probabilistic.py`

**Step 1: Write the failing test**

Add schema tests for:
- structured variable groups
- conditional variables
- scenario templates / assumption groups
- experiment design metadata
- run manifest assumption ledger persistence
- backward-compatible round trips for legacy `UncertaintySpec`

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/unit/test_probabilistic_schema.py`

**Step 3: Write minimal implementation**

Add the new dataclasses and normalization helpers in `backend/app/models/probabilistic.py`, keeping all new fields optional and preserving current serialized shapes when unused.

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/unit/test_probabilistic_schema.py`

### Task 2: Add Deterministic Experiment Design

**Files:**
- Create: `backend/app/services/experiment_design.py`
- Modify: `backend/tests/unit/test_uncertainty_resolver.py`
- Create or modify: `backend/tests/unit/test_experiment_design.py`

**Step 1: Write the failing test**

Add tests covering:
- deterministic Latin-hypercube row generation for a fixed seed
- stable dimension ordering
- scenario-template allocation metadata
- backward-compatible no-design behavior when no structured design is requested

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/unit/test_uncertainty_resolver.py backend/tests/unit/test_experiment_design.py`

**Step 3: Write minimal implementation**

Implement `experiment_design.py` with a deterministic plan builder that emits:
- ensemble-level method metadata
- numeric design dimensions
- per-run normalized coordinates / strata
- scenario-template assignments

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/unit/test_uncertainty_resolver.py backend/tests/unit/test_experiment_design.py`

### Task 3: Upgrade Resolver Semantics

**Files:**
- Modify: `backend/tests/unit/test_uncertainty_resolver.py`
- Modify: `backend/app/services/uncertainty_resolver.py`

**Step 1: Write the failing test**

Add resolver tests for:
- consuming a stored design row deterministically
- conditional variable activation
- grouped-variable handling
- assumption ledger details on the returned run manifest
- legacy independent sampling behavior remaining unchanged

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/unit/test_uncertainty_resolver.py`

**Step 3: Write minimal implementation**

Teach `UncertaintyResolver` to:
- resolve from explicit experiment-design metadata when present
- evaluate conditional rules in stable order
- apply scenario-template overrides deterministically
- populate manifest assumption-ledger metadata

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/unit/test_uncertainty_resolver.py`

### Task 4: Persist Design Artifacts Through Prepare And Ensemble Storage

**Files:**
- Modify: `backend/tests/unit/test_ensemble_storage.py`
- Modify: `backend/tests/unit/test_probabilistic_prepare.py`
- Modify: `backend/app/services/ensemble_manager.py`
- Modify: `backend/app/services/simulation_manager.py`

**Step 1: Write the failing test**

Add persistence tests covering:
- experiment-design artifact persistence
- ensemble state/source metadata
- run-manifest assumption ledgers
- prepare-time structured uncertainty defaults / passthrough

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/unit/test_ensemble_storage.py backend/tests/unit/test_probabilistic_prepare.py`

**Step 3: Write minimal implementation**

Update prepare and ensemble storage so design metadata is explicit on disk and ensemble creation stays reproducible with the same inputs.

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/unit/test_ensemble_storage.py backend/tests/unit/test_probabilistic_prepare.py`

### Task 5: Run Focused Verification

**Files:**
- Modify: none

**Step 1: Run the focused backend suite**

Run: `pytest backend/tests/unit/test_probabilistic_schema.py backend/tests/unit/test_uncertainty_resolver.py backend/tests/unit/test_ensemble_storage.py backend/tests/unit/test_probabilistic_prepare.py backend/tests/unit/test_experiment_design.py`

**Step 2: Run any justified downstream check**

If resolver or ensemble artifacts change shared probabilistic contracts, run the smallest additional affected suite.

**Step 3: Summarize the new boundary**

Document exactly which structured uncertainty features are now supported and which remain future work.
