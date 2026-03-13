# Stochastic Probabilistic Simulation Test and Release Plan

**Date:** 2026-03-08

## 1. Purpose

Define how the probabilistic path will be verified and released without destabilizing the existing product.

## 2. Test matrix

### Unit tests

- probabilistic schema validation
- uncertainty resolver sampling
- ensemble storage and manifests
- seeded runtime argument wiring
- outcome extraction
- aggregate summary generation
- scenario clustering
- report-context generation

### Integration tests

- probabilistic prepare -> ensemble create -> ensemble start
- ensemble completion -> aggregate summary -> report generation
- failed run handling
- run cleanup behavior

### Regression tests

- legacy single-run prepare/start/report flow
- legacy Step 2 through Step 5 UI flow

### Smoke tests

- one small probabilistic project end to end
- one legacy project end to end

## 3. Release stages

### R0: Developer-only

- feature flags off by default
- backend artifacts only
- README, `.env.example`, and the local operator runbook must explain how to enable the bounded local probabilistic path explicitly

### R1: Internal pilot

- Step 2 through Step 4 probabilistic flow enabled for selected users
- support FAQ required

### R2: Controlled beta

- limited user cohort
- rollback and incident runbook required
- the current repo only has a bounded local operator runbook, not a full controlled-beta rollback/support package

### R3: Broader rollout

- legacy path still fully supported
- readiness gates all satisfied

## 4. Release gates

- schema gate
- runtime gate
- analytics gate
- UX gate
- support gate

Each gate must have written evidence before advancing.

## 5. Rollback rules

- probabilistic feature flags can be disabled independently
- legacy single-run flow must remain available
- report UI must degrade gracefully if probabilistic artifacts are absent
