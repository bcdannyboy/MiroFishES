# Stochastic Probabilistic Simulation Delivery Governance

**Date:** 2026-03-08

## 1. Purpose

This document defines the delivery governance, readiness gates, risk register, and support policies for the probabilistic simulation program.

Live evidence companions:

- `docs/plans/2026-03-08-stochastic-probabilistic-status-audit.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-readiness-dashboard.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-gate-evidence-ledger.md`

## 2. Governance model

### Decision owners

- Architecture decisions: backend lead plus technical product lead
- API contract decisions: backend lead plus frontend lead
- Report language and provenance decisions: product lead plus report/backend lead
- Rollout decisions: engineering lead plus product lead

### Required standing reviews

- weekly cross-lane dependency review
- backend artifact review when new JSON contracts are introduced
- frontend copy and provenance review before Step 4 merge
- rollout readiness review before feature flag expansion

## 3. Feature-flag policy

The probabilistic path should be feature-flagged from day one.

Required flags:

- `probabilistic_prepare_enabled`
- `probabilistic_ensemble_storage_enabled`
- `probabilistic_report_enabled`
- `probabilistic_interaction_enabled`
- `calibrated_probability_enabled`
- a distinct runtime-launch flag may still be introduced later if launch semantics need separation from storage-only APIs

Policy:

- Step 2 controls should be hidden or disabled when the prepare flag is off.
- Storage-only ensemble endpoints may exist before runtime launch, but they remain off by default.
- Runtime launch must not be implied until a distinct runtime-capability contract exists.
- Calibrated probability UI must remain off until valid calibration artifacts exist.

## 4. Risk register

| Risk ID | Risk | Trigger | Impact | Mitigation |
| --- | --- | --- | --- | --- |
| R1 | Pseudo-quantification | Report shows precise probabilities without aggregate artifacts | Trust damage | Require provenance labels and artifact-backed probabilities only |
| R2 | Run collision | Multiple runs overwrite the same logs or DB files | Broken ensembles | Run-scoped directories and run-scoped `SimulationRunner` maps |
| R3 | Hidden nondeterminism | Seeded runs still differ because of uncontrolled randomness | Reproducibility confusion | Explicitly disclose seed-controlled vs non-seed-controlled stages |
| R4 | Frontend/backend contract churn | UI builds against unstable aggregate payloads | Rework and delay | Lock contracts before Step 4 final integration |
| R5 | Runtime explosion | Too many runs or too many agent actions | Slow or failed execution | Cap run counts, add max concurrency, define MVP budgets |
| R6 | Narrative/probability contradiction | One vivid run dominates report language | Misleading output | Use scenario clusters and representative-run labeling |
| R7 | Calibration misuse | Team enables calibrated labels without benchmark data | False rigor | Separate flag and explicit readiness gate for calibration |
| R8 | Legacy regression | Single-run flow breaks during refactor | Product instability | Keep compatibility path and run regression checks every phase |

## 5. Readiness gates

### Gate G1: Schema and artifact readiness

Required evidence:

- probabilistic schemas exist,
- artifacts persist consistently,
- example JSON fixtures are reviewed,
- legacy prepare path still works.

### Gate G2: Runtime readiness

Required evidence:

- run-scoped execution works,
- stop and cleanup semantics work,
- seeded runs are reproducible where supported,
- concurrency behavior is measured.

### Gate G3: Analytics readiness

Required evidence:

- metrics extraction is reliable,
- aggregate summary generation works,
- scenario clusters render from structured metrics,
- observational sensitivity artifacts exist and are clearly labeled as non-causal.

### Gate G4: UX readiness

Required evidence:

- Step 2 controls are understandable,
- Step 3 ensemble monitor is usable,
- Step 4 probabilities carry provenance,
- Step 5 interaction distinguishes ensemble vs run vs cluster answers.

### Gate G5: Rollout readiness

Required evidence:

- feature flags are wired,
- smoke tests pass,
- support runbook exists,
- known limits are documented,
- failure modes are acceptable.

## 6. QA and verification policy

### Backend verification

- unit tests for probabilistic schemas
- unit tests for uncertainty resolver
- unit tests for run manifest and storage layout
- unit tests for metrics extraction
- unit tests for aggregate summaries and clustering
- regression checks for legacy single-run endpoints

### Frontend verification

- Step 2 control-state checks
- Step 3 ensemble monitor checks
- Step 4 probabilistic card rendering checks
- Step 5 provenance-label checks
- history and routing checks if comparison is added

### Integration verification

- prepare to ensemble-launch happy path
- ensemble to report happy path
- failed-run handling
- legacy single-run flow
- feature-flag off-path behavior

## 7. Rollout stages

### Stage 0: Internal developer only

Allowed:

- backend artifact generation
- seeded runtime experiments
- JSON artifact inspection

Not allowed:

- external-facing probability claims

### Stage 1: Internal product validation

Allowed:

- Step 2 through Step 4 probabilistic UI
- limited report-agent support

Requirements:

- provenance labels visible
- run counts and artifact versions visible

### Stage 2: Controlled beta

Allowed:

- selected users with known scenarios

Requirements:

- support runbook
- stable failure recovery
- explicit limits on calibration claims

### Stage 3: Broader availability

Allowed:

- default-visible probabilistic path

Requirements:

- operational metrics stable
- known edge cases documented
- regression history acceptable

## 8. Support and runbook requirements

Before controlled beta, create operational documentation for:

- how to identify a stuck ensemble run
- how to stop one run without destroying the ensemble
- how to inspect `run_manifest.json`
- how to verify whether a probability is empirical or calibrated
- how to explain representative runs to users

Current repo-grounded state on 2026-03-10:

- `docs/local-probabilistic-operator-runbook.md` now covers bounded local enablement flags, capability checks, retry/rerun/cleanup recovery, and artifact inspection paths
- this is still not the full controlled-beta package; release-grade support ownership, dashboards/alerts, and rollback materials remain required before promotion beyond local/operator use

## 9. Documentation maintenance rules

- The architecture design doc is the source of truth for concepts.
- The implementation plan is the source of truth for execution tasks.
- This governance doc is the source of truth for gates and risk posture.
- The status audit and readiness dashboard are the source of truth for live repo-grounded readiness.
- The gate ledger is the source of truth for gate evidence and closure posture.
- If a JSON contract changes, the integration/dependency map must be updated in the same change.
- If user-facing copy changes, the frontend workstream doc and this governance doc must both be reviewed.

## 10. Exit conditions for this program

The program can be considered complete when:

- the probabilistic path is stable,
- the UI exposes it coherently,
- reports are artifact-backed and provenance-labeled,
- legacy mode remains intact,
- and the team has an explicit policy for calibrated vs uncalibrated forecast claims.
