# Hybrid Forecasting Utility Design

**Date:** 2026-03-30

**Phase:** NB Active-Path Readiness Expansion

## Goal

Make the active supported path genuinely ready for `binary`, `categorical`, and true `numeric` forecast questions end to end while explicitly preserving simulation as a first-class scenario worker rather than the default answer source.

This phase does not attempt to turn MiroFishES into a strategic recommendation engine. It also does not reopen archived historical backlog as an active-path blocker beyond the existing explicit quarantine semantics.

## Scope And Non-Goals

In scope:

- active-path `binary`, `categorical`, and `numeric` forecast questions
- typed prediction ledgers, evaluation cases, backtests, calibration, and forecast answers
- hybrid worker orchestration with simulation preserved as a supporting scenario worker
- Step 4, Step 5, smoke, operator-local, and artifact-tooling truthfulness for the active path

Out of scope:

- strategic recommendation or ranking mode
- treating simulation frequencies as real-world probabilities without evaluation earning that
- archived historical backlog as a readiness blocker beyond honest `quarantined_non_ready` semantics

## Canonical Support Matrix

- `binary`: fully supported and calibratable
- `categorical`: fully supported and calibratable through normalized named-outcome distributions
- `numeric`: fully supported and calibratable through scalar estimates with units plus interval-aware evaluation/calibration
- `scenario`: simulation-backed scenario exploration only unless non-simulation evidence earns a defended forecast answer

Important boundaries:

- threshold questions belong to `binary`, not `numeric`
- `numeric` means scalar-value forecasting such as value-by-horizon or bounded range-by-horizon
- simulation `observed_run_share` remains descriptive scenario evidence, not a real-world probability claim

## Canonical Architecture

The canonical forecast workspace remains composed of:

- `forecast_question`
- `resolution_criteria`
- `evidence_bundle`
- `forecast_worker`
- `prediction_ledger`
- `evaluation_case`
- `forecast_answer`
- `simulation_worker_contract`

Object roles:

- `forecast_question` is the primary persisted question object and now carries type-correct question specs for binary, categorical, and numeric lanes.
- `evidence_bundle` is the bounded evidence substrate with provenance, freshness, relevance, contradiction markers, missing-evidence markers, and explicit uncertainty causes.
- `forecast_worker` includes base-rate, reference-class, retrieval-synthesis, and simulation workers behind one typed interface.
- `prediction_ledger` remains append-only and stores immutable typed issued predictions, revisions, linked worker outputs, and final resolution state.
- `evaluation_case` stores comparable historical cases with type-correct observed outcomes, timestamps, split/window metadata, and benchmark linkage.
- `forecast_answer` remains the bounded hybrid answer surface and now supports answer-native categorical and numeric payloads.
- `simulation_worker_contract` keeps simulation available as supporting scenario analysis and prevents scenario frequency from being mislabeled as real-world probability.

## Question-Type Semantics

- `binary`
  - yes/no questions, including threshold-style formulations such as “will value exceed X by date Y?”
  - answer payloads use probability semantics when appropriate
- `categorical`
  - mutually exclusive named outcomes
  - answer payloads use normalized forecast distributions with top-label and rival-label context
- `numeric`
  - scalar outcomes with units
  - calibrated lane requires point estimate plus interval structure
  - templates include `numeric_value_by_horizon` and `numeric_range_by_horizon`
- `scenario`
  - descriptive scenario exploration lane
  - simulation-heavy and intentionally separated from calibrated forecast claims

## Evaluation And Calibration Contract

The repo now distinguishes these surfaces everywhere:

- `evidence available`
- `evaluation available`
- `benchmark available`
- `backtest ready`
- `calibration ready`
- `calibrated confidence earned`

The contract is answer-bound for forecast workspaces:

- a forecast answer may surface `calibrated confidence earned` only when:
  - the answer is explicitly marked `confidence_semantics = "calibrated"`
  - resolved evaluation cases exist for that answer
  - benchmark status is available for that answer
  - backtest status is ready or available for that answer
  - calibration status is ready for that answer
  - the answer payload shape matches the question type

Type-specific expectations:

- `binary`
  - probability-bearing answer payloads
  - evaluation and calibration through supported binary scoring surfaces
- `categorical`
  - normalized named-outcome distributions
  - evaluation through multiclass log loss, multiclass Brier score, and top-1 accuracy
  - calibration through top-label reliability and support-aware class coverage checks
- `numeric`
  - scalar value with units plus interval structure
  - evaluation through error and interval-coverage summaries
  - calibration through interval coverage, bias/drift, and sharpness summaries

Separate boundary:

- ensemble metric calibration remains a scenario-lane artifact about named simulation metrics
- forecast-answer categorical/numeric calibration must not inherit from ensemble `confidence_status`

## Acceptance Criteria

### P0: Truthfulness Hardening

Acceptance criteria:

- public docs and UI text stay free of inflated forecasting claims
- workflow labels and epistemic labels remain separate
- simulation-frequency language remains descriptive rather than probabilistic

Status:

- complete

### P1: Canonical Foundation, Question Service, Evidence Foundation, and Hybrid Engine Base

Acceptance criteria:

- forecast workspace primitives remain intact
- forecast questions, evidence bundles, and prediction ledgers remain canonical
- the hybrid engine remains real and simulation remains one worker inside it
- legacy workspace routes still function

Status:

- complete

### P2: Integrated Hybrid Utility

Acceptance criteria:

- evaluation registries carry timestamps, comparable classes, and split/window metadata
- benchmark harnesses compare the system against simple baselines
- calibration and backtest reporting carry explicit provenance on supported lanes
- prediction ledger and forecast answers surface evaluation outputs honestly
- Step 4 and Step 5 expose the hybrid workspace and distinguish evidence, evaluation, calibrated confidence, and simulation-only surfaces
- supported-question templates and abstain UX are visible in the product
- active versus historical artifact readiness is explicit
- saved-history cards can reopen Step 3 and Step 5 from valid saved state
- live operator report generation reaches the configured backend through browser API clients and frontend proxy requests

Status:

- complete

### NB0: Canonical Non-Binary Architecture Reset

Acceptance criteria:

- the support matrix explicitly names `binary`, `categorical`, `numeric`, and `scenario`
- threshold-style questions are treated as `binary`
- true numeric templates exist and are visible in the domain contract
- canonical answer payload shapes and calibration kinds are published through the forecasting capability contract

Status:

- complete

### NB1: Non-Binary Domain, Storage, Prediction Ledger, and API Generalization

Acceptance criteria:

- categorical questions carry named outcome sets
- numeric questions carry units, bounds, and interval expectations
- prediction ledgers and evaluation cases preserve type-correct payloads and outcomes
- service and API layers reject binary-only payload leakage into categorical/numeric questions
- simulation-linked records remain interoperable without stronger-than-earned semantics

Status:

- complete

### NB2: Non-Binary Evaluation Registry, Benchmark Harness, and Backtesting

Acceptance criteria:

- categorical evaluation supports resolved named outcomes plus multiclass scoring
- numeric evaluation supports scalar outcomes, interval coverage, and benchmark baselines
- out-of-sample and rolling evaluation metadata can flow through forecast answers and ledgers where available
- non-binary evaluation exists as real scored evidence before any calibration claim is surfaced

Status:

- complete

### NB3: Non-Binary Calibration And Confidence-Semantics Hardening

Acceptance criteria:

- categorical answers earn calibration only through reliability/support evidence
- numeric answers earn calibration only through interval-aware evidence
- evaluation availability and calibrated confidence earned remain separate everywhere
- unsupported or weakly supported lanes abstain or stay explicitly uncalibrated

Status:

- complete

### NB4: Hybrid Non-Binary Workers And Aggregation

Acceptance criteria:

- base-rate, reference-class, retrieval-synthesis, and simulation workers emit type-correct outputs
- aggregation produces answer-native categorical and numeric answers
- disagreement, counterevidence, assumption ledgers, and abstention remain explicit
- simulation remains available and useful without dominating stronger workers

Status:

- complete

### NB5: Report, Runtime, Step 4/5, and Operator Integration

Acceptance criteria:

- Step 4 and Step 5 render categorical answers as named distributions and numeric answers as point-plus-interval estimates
- percentage formatting is not used as a universal best-estimate representation
- supported-question templates and abstain UX are visible in the product
- smoke and operator-local flows cover active-path typed hybrid answers without semantic drift

Status:

- complete

### NB6: Artifact And Tooling Compatibility Plus Final Hardening

Acceptance criteria:

- `npm run verify:nonbinary` exists and is used as the canonical targeted non-binary surface
- active artifact scans understand truthful typed calibrated forecast answers
- runbooks and wrapper scripts describe the active non-binary contract honestly
- archived historical simulations remain out of scope beyond explicit quarantine semantics

Status:

- complete

## Verified Evidence

Fresh verification on 2026-03-30:

- `npm run verify:nonbinary`
  - backend: `92 passed`
  - frontend: `79 passed`
- `npm run verify:confidence`
  - backend: `100 passed`
  - frontend: `79 passed`
- `npm run verify:forecasting:artifacts`
  - active scan passed
  - `125` active simulations inspected
- `npm run verify:forecasting:artifacts:all`
  - passed
  - `141` archived simulations remain explicitly quarantined as non-ready historical evidence
- `npm run verify:smoke`
  - `10 passed`
  - includes categorical and numeric Step 4/5 coverage plus history replay
- `PLAYWRIGHT_LIVE_ALLOW_MUTATION=true npm run verify:operator:local`
  - `2 passed`
- `npm run verify`
  - frontend: `84` tests passed and `vite build` succeeded
  - backend: `295 passed`

Current repo snapshot note:

- the default persisted forecast workspace directory currently has no standalone workspaces checked into this repo snapshot
- typed forecast-workspace artifact scanning is still covered through the scanner unit suite and the active hybrid Step 4/5 runtime path

## Residual Risks

- strategic recommendation mode remains a separate future expansion
- archived historical simulations can still be `quarantined_non_ready`; they remain read-only historical evidence and must not be read as active readiness
- live Step 2 prepare still depends on real environment configuration for LLM/Zep-backed flows
- existing frontend chunk-size warnings remain
- existing backend `PytestConfigWarning` remains
