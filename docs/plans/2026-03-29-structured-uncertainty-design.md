# Structured Uncertainty Design

**Date:** 2026-03-29

**Goal:** Upgrade MiroFish's probabilistic preparation layer from independent scalar perturbations toward inspectable, deterministic structured experiment design.

## Scope

This wave stays inside the backend probabilistic control plane:

- `backend/app/models/probabilistic.py`
- `backend/app/services/uncertainty_resolver.py`
- `backend/app/services/ensemble_manager.py`
- `backend/app/services/simulation_manager.py`
- a new `backend/app/services/experiment_design.py`
- backend unit tests covering schema, resolver behavior, and artifact persistence

It does not rewrite runtime execution, calibration, or downstream report behavior.

## Recommended Approach

Use an additive experiment-design layer.

Keep the existing `random_variables` contract valid, then add optional structured uncertainty fields that can express:

- grouped variables for shared design-space treatment and coarse correlation metadata
- conditional variables that activate only when earlier resolved values satisfy explicit rules
- scenario templates / assumption groups that apply named overrides or deltas
- per-run assumption ledgers and per-ensemble experiment-design metadata

For seeded numeric sampling, use deterministic Latin hypercube as the default space-filling design. Persist the design row and normalized coordinates in artifacts so operators can inspect what was actually sampled.

## Artifact Strategy

### Uncertainty Spec

Extend `UncertaintySpec` with optional structured fields rather than replacing `random_variables`.

Expected additions:

- `variable_groups`
- `scenario_templates`
- `experiment_design`

Legacy callers that only send `random_variables` must continue to round-trip unchanged.

### Ensemble-Level Design Artifact

Add a first-class ensemble design artifact generated before run resolution. It should include:

- design method, seed, and generator version
- ordered variable dimensions
- deterministic row assignments for each run
- scenario-template allocation per run

This keeps the design inspectable and reproducible without forcing future readers to reverse-engineer resolver internals.

### Run-Level Assumption Ledger

Each run manifest should persist an assumption ledger containing:

- design row identifier
- active scenario templates / assumption groups
- conditional branches that fired
- grouped-variable metadata
- resolved values already written today

## Resolver Strategy

`UncertaintyResolver` should stop being responsible for inventing the design. Instead, it should consume explicit design-row metadata when present.

For this wave:

- grouped numeric variables share one Latin-hypercube row and deterministic rank ordering
- conditional variables evaluate simple explicit predicates against already resolved values
- scenario templates apply named overrides or additive/multiplicative deltas in a deterministic order

This is conservative. It does not claim full copula-based correlation modeling or arbitrary probabilistic programs.

## Determinism

Determinism should come from:

- `root_seed`
- stable dimension ordering
- stable run ordering
- stored design rows

Re-running ensemble creation with the same prepare artifacts and seeds should reproduce the same design metadata, assumption ledgers, and resolved configs.

## Deferred

This wave intentionally defers:

- high-dimensional Sobol or Halton sequence support
- full covariance-matrix or copula correlation models
- exogenous event process generation
- arbitrary rule engines for conditional logic
- runtime engine changes
