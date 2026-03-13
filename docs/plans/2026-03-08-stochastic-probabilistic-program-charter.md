# Stochastic Probabilistic Simulation Program Charter

**Date:** 2026-03-08

## 1. Mission

Extend MiroFishES from a single-trajectory graph-plus-agent simulator into a probabilistic ensemble simulation system that can support uncertainty-aware forecasting without replacing the current product architecture.

## 2. Business objective

Deliver a sidecar probabilistic capability that:

- preserves current graph-derived worldbuilding,
- preserves current agent-based world simulation,
- preserves current report and interaction surfaces,
- adds explicit uncertainty, seeded run families, structured outcome aggregation, and provenance-labeled forecast reporting.

## 3. In scope

- probabilistic schema and artifact model
- seeded resolved-config generation
- ensemble/run orchestration
- per-run metrics
- aggregate summaries
- scenario clusters
- sensitivity outputs
- uncertainty-aware report cards
- ensemble-aware report-agent context
- rollout governance and readiness

## 4. Out of scope for MVP

- monolithic Bayesian network rewrite
- replacement of OASIS runtime
- full checkpoint branching
- calibrated probability claims without benchmark data
- graph-confidence propagation as a blocking dependency

## 5. Success criteria

The MVP is successful when:

- one prepared simulation can launch many explicit seeded runs,
- those runs persist isolated artifacts and metrics,
- reports show top outcomes and scenario families using aggregate artifacts,
- legacy single-run flow remains intact,
- every displayed probability is clearly labeled as empirical or calibrated.

## 6. Non-goals

- proving full determinism across external LLM behavior
- solving calibration before recurring targets and benchmark data exist
- generalizing MiroFishES away from its present product shape in the same program

## 7. Delivery strategy

Use a sidecar rollout:

- preserve current single-run path,
- add probabilistic mode beside it,
- gate the new mode behind feature flags,
- and phase advanced confidence and calibration after the MVP is stable.

## 8. Decision rights

- architecture: backend lead plus technical product lead
- API contract: backend lead plus frontend lead
- probability semantics and report language: product lead plus research/forecasting lead
- rollout and readiness: engineering lead plus product lead

## 9. Core team responsibilities

- Product/Delivery: scope, milestones, release gates
- Research/Forecasting: uncertainty semantics, outcome metrics, allowed claim rules
- Backend/API: artifacts, endpoints, report backend
- Runtime/OASIS: seeded execution and run isolation
- Analytics: metrics, aggregation, clustering, sensitivity
- Frontend/UX: probabilistic controls and report/interaction surfaces
- QA/Release: regression, pilot readiness, rollback, support
