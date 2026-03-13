# Stochastic Probabilistic Step 2 Smoke / Evidence Baseline

**Date:** 2026-03-09

> This document is intentionally a Step 2-focused smoke and evidence baseline. It does not close full `F5.1`, and it must not be used as evidence that probabilistic aggregation, report, or interaction support is complete. As of the current implementation, Step 3 now has a truthful probabilistic ensemble browser, Step 4 has only an initial additive report-context addendum, and Step 5 still lacks grounded ensemble-aware interaction even though it now renders an explicit unsupported-state banner.

## 1. Purpose

This baseline defines the minimum rigorous QA and evidence standard for the current Step 2 probabilistic slice as it exists in the repository today.

Its job is to answer one narrow question:

- can the current Step 2 flow safely preserve the legacy baseline prepare path, discover whether probabilistic prepare is available, and explicitly re-prepare the same simulation to persist probabilistic sidecar artifacts without overstating downstream support?

This document is not a release signoff, not an end-to-end probabilistic readiness claim, and not a substitute for the broader `F5.1` frontend QA matrix that still needs to exist.

## 2. Scope Boundaries

### In scope

- Step 2 capability discovery through `GET /api/simulation/prepare/capabilities`
- the current legacy baseline prepare path
- the current explicit probabilistic re-prepare path
- Step 2 UI state and copy for prepare mode, prepared-run count, uncertainty profile, outcome metrics, and prepared artifact summary
- backend prepare validation for probabilistic inputs
- prepare-status behavior that distinguishes legacy-ready from probabilistic-ready
- file-level artifact evidence written under the simulation directory
- degraded and off-state behavior that Step 2 currently handles

### Explicitly out of scope

- ensemble creation
- seeded runtime execution from probabilistic artifacts
- aggregate analytics
- probabilistic report generation
- probabilistic chat grounding
- calibrated probability surfaces
- Step 3, Step 4, or Step 5 probabilistic UX
- release gate closure for the full stochastic probabilistic program

### Current downstream boundary that must be stated in every evidence readout

Even after a successful probabilistic re-prepare, the current runtime and downstream UX remain constrained:

- Step 3 now supports one stored probabilistic run shell and its raw runtime/timeline state, not broader ensemble browsing
- Step 4 is still a simulation-scoped report workflow, but it now has an initial additive report-context addendum rather than a fully ensemble-aware report body
- Step 5 still uses the legacy report/agent model and now says so explicitly in probabilistic mode
- backend run instructions still point runtime execution at `simulation_config.json`

Probabilistic Step 2 evidence therefore proves only prepare-path capability, artifact persistence, and guardrail behavior. It does not prove probabilistic execution or reporting.

## 3. Repo-Grounded Current Baseline

The following statements are grounded in the current repository implementation and should be treated as the source-of-truth baseline for Step 2 smoke:

| Area | Current repo-grounded truth | Primary evidence |
| --- | --- | --- |
| Capability discovery | Step 2 calls `GET /api/simulation/prepare/capabilities` before prepare work starts | `backend/app/api/simulation.py`, `frontend/src/api/simulation.js`, `frontend/src/components/Step2EnvSetup.vue` |
| Feature flag | probabilistic prepare is gated by `Config.PROBABILISTIC_PREPARE_ENABLED` | `backend/app/config.py`, `backend/app/api/simulation.py` |
| Legacy baseline behavior | Step 2 auto-starts the legacy prepare path on mount, even when probabilistic prepare is available | `frontend/src/components/Step2EnvSetup.vue` |
| Explicit re-prepare behavior | after the legacy baseline is ready, the user can switch to Probabilistic mode and explicitly trigger re-prepare for the same `simulation_id` | `frontend/src/components/Step2EnvSetup.vue`, `backend/app/api/simulation.py`, `backend/tests/unit/test_probabilistic_prepare.py` |
| Sidecar artifacts | probabilistic prepare preserves legacy `simulation_config.json` and additionally writes `simulation_config.base.json`, `uncertainty_spec.json`, `outcome_spec.json`, and `prepared_snapshot.json` | `backend/app/services/simulation_manager.py`, `backend/tests/unit/test_probabilistic_prepare.py` |
| Summary semantics | the Step 2 prepared artifact summary is a provenance/setup surface, not a runtime, calibration, or probability claim | `frontend/src/components/Step2EnvSetup.vue`, `backend/app/services/simulation_manager.py` |
| Probabilistic status semantics | `POST /api/simulation/prepare/status` accepts `probabilistic_mode` so legacy prepare is not misread as probabilistic-ready | `backend/app/api/simulation.py`, `backend/tests/unit/test_probabilistic_prepare.py` |
| Downstream limit | Step 3 now contains a truthful probabilistic ensemble browser, Step 4 now has an initial additive report-context addendum, and Step 5 now has an explicit unsupported-state banner, but grounded report/chat semantics are still incomplete | `frontend/src/components/Step3Simulation.vue`, `frontend/src/components/Step4Report.vue`, `frontend/src/components/Step5Interaction.vue` |

## 4. Prerequisites

### Product and data prerequisites

- a project exists with a valid `simulation_requirement`
- the project has a built graph and usable `graph_id`
- the user can enter the existing simulation flow far enough to reach Step 2
- the test project has enough graph entities to complete baseline prepare

### Local environment prerequisites

- frontend dependencies installed
- backend dependencies installed
- backend can start successfully
- frontend can start successfully
- `LLM_API_KEY` is configured
- `ZEP_API_KEY` is configured

### Flag prerequisites by scenario

- legacy-only off-state scenarios: `PROBABILISTIC_PREPARE_ENABLED=false`
- dual-path baseline and re-prepare scenarios: `PROBABILISTIC_PREPARE_ENABLED=true`

### Runtime inspection prerequisites

- access to browser devtools or another way to inspect network requests
- access to inspect the simulation directory under `backend/uploads/simulations/<simulation_id>/`
- access to collect command output for automated evidence

### Local default endpoints if repo defaults are unchanged

- backend: `http://localhost:5001`
- frontend: Vite default frontend host from `npm run frontend`

If local overrides are used, the evidence log must record the actual host and port values used during the run.

## 5. Commands and Evidence Sources

### Primary code evidence

- `backend/app/config.py`
- `backend/app/models/probabilistic.py`
- `backend/app/api/simulation.py`
- `backend/app/services/simulation_manager.py`
- `backend/app/services/uncertainty_resolver.py`
- `backend/tests/unit/test_probabilistic_prepare.py`
- `backend/tests/unit/test_probabilistic_schema.py`
- `backend/tests/unit/test_uncertainty_resolver.py`
- `frontend/src/api/index.js`
- `frontend/src/api/simulation.js`
- `frontend/src/components/Step2EnvSetup.vue`
- `frontend/src/components/Step3Simulation.vue`
- `frontend/src/components/Step4Report.vue`
- `frontend/src/components/Step5Interaction.vue`
- `.github/workflows/verify.yml`
- `package.json`

### Minimum automated verification commands

Run from the repository root unless otherwise noted:

```bash
npm run verify
cd backend && python3 -m pytest tests/unit/test_probabilistic_prepare.py -q
cd backend && python3 -m pytest tests/unit/test_probabilistic_schema.py tests/unit/test_uncertainty_resolver.py -q
```

These commands support the current baseline because they verify:

- frontend build stability
- prepare-path validation rules
- legacy versus probabilistic artifact persistence
- probabilistic re-prepare after legacy prepare
- prepare-status probabilistic intent handling
- schema and resolver contract coverage

### Local run commands for manual smoke

```bash
npm run backend
npm run frontend
```

### API probe commands

Use these only when a manual UI observation needs direct API confirmation. Replace placeholders with real values from the active run.

Capability probe:

```bash
curl -sS http://localhost:5001/api/simulation/prepare/capabilities | jq .
```

Legacy prepare probe:

```bash
curl -sS -X POST http://localhost:5001/api/simulation/prepare \
  -H 'Content-Type: application/json' \
  -d '{
    "simulation_id": "<simulation_id>",
    "use_llm_for_profiles": true,
    "parallel_profile_count": 5
  }' | jq .
```

Probabilistic re-prepare probe:

```bash
curl -sS -X POST http://localhost:5001/api/simulation/prepare \
  -H 'Content-Type: application/json' \
  -d '{
    "simulation_id": "<simulation_id>",
    "probabilistic_mode": true,
    "uncertainty_profile": "balanced",
    "outcome_metrics": ["simulation.total_actions"]
  }' | jq .
```

Probabilistic status probe:

```bash
curl -sS -X POST http://localhost:5001/api/simulation/prepare/status \
  -H 'Content-Type: application/json' \
  -d '{
    "simulation_id": "<simulation_id>",
    "probabilistic_mode": true
  }' | jq .
```

### Filesystem evidence probe

After each prepare scenario, inspect the simulation directory:

```bash
ls -la backend/uploads/simulations/<simulation_id>
```

For probabilistic scenarios, also capture the key artifact payloads:

```bash
jq . backend/uploads/simulations/<simulation_id>/uncertainty_spec.json
jq . backend/uploads/simulations/<simulation_id>/outcome_spec.json
jq . backend/uploads/simulations/<simulation_id>/prepared_snapshot.json
```

## 6. Manual Smoke Scenarios

The current baseline should be executed as a scenario set, not a single binary check. The goal is to prove that the repo supports the implemented Step 2 contract and does not overclaim beyond it.

### Scenario S1: Legacy baseline prepare when probabilistic prepare is enabled

**Purpose**

Prove that the current Step 2 flow preserves the legacy auto-prepare baseline even when probabilistic capability is available.

**Setup**

- set `PROBABILISTIC_PREPARE_ENABLED=true`
- start backend and frontend
- use a project that can successfully enter Step 2

**Steps**

1. Enter Step 2 for a fresh simulation.
2. Observe that Step 2 first performs capability discovery.
3. Observe the Step 2 logs and prepare-mode panel.
4. Let the automatic legacy prepare complete without manually switching modes.
5. Inspect the initial `POST /api/simulation/prepare` request.
6. Inspect the resulting simulation directory.

**Expected results**

- the capability endpoint returns `probabilistic_prepare_enabled=true`
- the UI indicates probabilistic prepare is available
- Step 2 still starts the legacy baseline prepare automatically
- the initial prepare request does not send `probabilistic_mode`, `uncertainty_profile`, or `outcome_metrics`
- Step 2 completes normal profile generation and configuration loading
- no probabilistic prepared-artifact summary panel is shown after the legacy-only baseline
- the simulation directory contains legacy baseline files:
  - `state.json`
  - `reddit_profiles.json`
  - `twitter_profiles.csv`
  - `simulation_config.json`
- the simulation directory does not yet contain:
  - `simulation_config.base.json`
  - `uncertainty_spec.json`
  - `outcome_spec.json`
  - `prepared_snapshot.json`

**Evidence to capture**

- screenshot of the Step 2 prepare-mode panel with probabilistic availability visible
- network capture for `GET /api/simulation/prepare/capabilities`
- network capture for the first legacy `POST /api/simulation/prepare`
- filesystem listing for the simulation directory after baseline prepare completes

### Scenario S2: Explicit probabilistic re-prepare on the same simulation

**Purpose**

Prove that a legacy-prepared simulation can be explicitly re-prepared in probabilistic mode and that the current implementation persists the sidecar artifact set without replacing the legacy runtime config.

**Setup**

- begin immediately after Scenario S1 or another confirmed legacy baseline prepare
- remain on the same `simulation_id`

**Steps**

1. In Step 2, switch the mode toggle from `Legacy` to `Probabilistic`.
2. Confirm the uncertainty profile selector and outcome metric controls are visible.
3. Leave the default selections or pick a supported profile and supported metric set.
4. Click `Prepare probabilistic artifact set`.
5. Observe the request payload and response payload.
6. Wait for the re-prepare to finish.
7. Inspect the prepared artifact summary panel.
8. Inspect the simulation directory contents and JSON payloads.

**Expected results**

- the request includes:
  - `probabilistic_mode: true`
  - `uncertainty_profile`
  - `outcome_metrics`
- Step 2 does not treat the existing legacy baseline as probabilistic-ready
- the response returns a `prepared_artifact_summary`
- while the re-prepare is still in flight, the summary may describe planned sidecars; this is not yet file-write evidence
- after completion, the summary resolves to a probabilistic artifact set with real files
- the simulation directory retains `simulation_config.json`
- the simulation directory now also contains:
  - `simulation_config.base.json`
  - `uncertainty_spec.json`
  - `outcome_spec.json`
  - `prepared_snapshot.json`
- `prepared_snapshot.json` reports `mode: "probabilistic"`
- the prepared artifact summary exposes schema and generator version metadata
- Step 2 wording remains provenance-oriented and does not claim runtime sampling, calibrated probabilities, or report support

**Evidence to capture**

- screenshot of the probabilistic controls before submit
- network capture for probabilistic `POST /api/simulation/prepare`
- screenshot of the Step 2 prepared artifact summary after completion
- filesystem listing for the simulation directory after re-prepare
- `jq` capture for `uncertainty_spec.json`
- `jq` capture for `outcome_spec.json`
- `jq` capture for `prepared_snapshot.json`

### Scenario S3: Probabilistic-ready status check does not false-green from legacy artifacts

**Purpose**

Prove that the status contract distinguishes legacy-ready from probabilistic-ready, which is the key guardrail that makes the explicit re-prepare path meaningful.

**Setup**

- use a simulation that has completed legacy prepare but has not yet completed probabilistic re-prepare

**Steps**

1. Call `POST /api/simulation/prepare/status` with the same `simulation_id`.
2. Include `probabilistic_mode: true`.

**Expected results**

- the response does not report the legacy-only simulation as already probabilistic-prepared
- the result stays in a not-ready state for probabilistic intent until sidecars exist
- if the system reports detail, it should indicate that legacy prepare artifacts exist but probabilistic sidecars are missing

**Evidence to capture**

- raw `POST /api/simulation/prepare/status` request body
- raw response body

### Scenario S4: Legacy-only off-state when the backend flag is disabled

**Purpose**

Prove that Step 2 degrades to a safe legacy-only posture when probabilistic prepare is disabled.

**Setup**

- set `PROBABILISTIC_PREPARE_ENABLED=false`
- restart the backend

**Steps**

1. Enter Step 2 for a fresh simulation.
2. Observe the prepare-mode status and copy.
3. Attempt a direct API probabilistic prepare call if additional proof is needed.

**Expected results**

- the capability surface reports `probabilistic_prepare_enabled=false`
- the Step 2 UI shows a legacy-only state
- no probabilistic controls are available
- Step 2 continues with the legacy baseline prepare path
- a direct probabilistic API request is rejected with `400`

**Evidence to capture**

- screenshot of the Step 2 legacy-only state
- network capture for `GET /api/simulation/prepare/capabilities`
- optional raw 400 response from a direct probabilistic prepare request

### Scenario S5: Invalid probabilistic request values are rejected cleanly

**Purpose**

Prove that the current prepare contract rejects unsupported probabilistic values instead of silently accepting bad state.

**Setup**

- set `PROBABILISTIC_PREPARE_ENABLED=true`
- use direct API probes for negative cases

**Steps**

Run these negative probes one at a time:

1. send `uncertainty_profile` without `probabilistic_mode=true`
2. send an unsupported `uncertainty_profile`
3. send an unsupported outcome metric id

**Expected results**

- each invalid request returns `400`
- the error text clearly states the violated contract
- no partial probabilistic sidecar artifact set is created as a side effect of rejected validation

**Evidence to capture**

- request payload and response body for each rejected case
- filesystem check confirming no new sidecars were produced for the rejected attempt

### Scenario S6: Step 3 through Step 5 still stop short of grounded probabilistic downstream support after probabilistic re-prepare

**Purpose**

Prevent false interpretation of a successful Step 2 probabilistic re-prepare as evidence that the rest of the simulation workflow has grounded end-to-end probabilistic support.

**Setup**

- complete Scenario S2 first

**Steps**

1. Proceed into the normal start/run/report/interaction flow.
2. Observe the Step 3, Step 4, and Step 5 surfaces.
3. Inspect whether any ensemble, run-family, cluster, or probabilistic report controls appear.

**Expected results**

- Step 3 still does not prove happy-path browser evidence by itself
- Step 4 may show the initial additive report-context addendum, but it does not prove a fully ensemble-aware report body
- Step 5 may show an explicit unsupported-state banner, but it does not prove grounded ensemble/run/cluster interaction
- any evidence readout must explicitly say the probabilistic implementation still stops short of grounded runtime/report/interaction support

**Evidence to capture**

- one screenshot each from Step 3, Step 4, and Step 5 after a successful probabilistic re-prepare
- brief written note that any observed downstream probabilistic surface remained additive or unsupported rather than fully grounded

## 7. Expected Results Summary

The current Step 2 baseline should be considered healthy only if all of the following are true:

- legacy prepare still completes successfully
- probabilistic capability discovery is accurate when enabled or disabled
- probabilistic re-prepare is explicit, not hidden behind the legacy auto-prepare path
- probabilistic re-prepare persists sidecar artifacts on top of the existing legacy baseline
- status lookups do not confuse legacy readiness with probabilistic readiness
- off-state and invalid-input behavior fail safely
- evidence capture stays precise about Step 2-only scope
- no report, runtime, or chat claim is made beyond the prepare-path artifact layer

## 8. Degraded / Off-State Behavior

The following degraded behaviors are supported by the current implementation and should be treated as required baseline behavior, not edge-case noise.

### Capability discovery unavailable

If capability discovery fails, Step 2 logs the failure and falls back to the legacy prepare path. This is a Step 2 resilience behavior, not evidence of probabilistic readiness. A smoke readout must record that probabilistic discovery was unavailable and that the session fell back to legacy.

### Probabilistic flag disabled

When `PROBABILISTIC_PREPARE_ENABLED=false`:

- the backend still exposes the capability endpoint
- the response reports probabilistic prepare disabled
- Step 2 stays on the legacy single-run path
- direct probabilistic prepare requests are rejected

### Legacy-prepared simulation without sidecars

This is a normal intermediate state in the current design. It means:

- legacy runtime inputs exist
- probabilistic sidecars do not exist yet
- Step 2 may still be used for explicit probabilistic re-prepare
- the simulation must not be described as probabilistic-ready

### Invalid probabilistic values

Unsupported profiles or metrics are validation failures, not partial-success states. The smoke log should record the exact request and the exact rejection message.

### Missing project prerequisites

If the project lacks a graph or `simulation_requirement`, prepare may fail before the Step 2 baseline can be exercised. That is an environment/setup failure, not evidence against the implemented probabilistic contract. It should be logged as a blocked run, not a passed run.

## 9. Evidence Capture Rules

### Required metadata for every smoke run

Every evidence bundle must record:

- date and local time
- repo branch or commit if known
- backend flag state for `PROBABILISTIC_PREPARE_ENABLED`
- project id
- simulation id
- whether the run covered:
  - legacy baseline only
  - legacy baseline plus probabilistic re-prepare

### Required artifacts for a Step 2 baseline evidence bundle

- command transcript or saved output for the automated verification commands
- screenshot or screen recording of Step 2 in the executed scenario
- network evidence for capability discovery and prepare requests
- filesystem evidence for the resulting simulation directory
- written scenario outcome notes with pass, fail, or blocked status

### Evidence interpretation rules

- planned rows in `prepared_artifact_summary` are not sufficient evidence that files were written
- only filesystem presence or summary entries showing real `exists` metadata after completion count as file-write evidence
- `uncertainty_spec.json`, `outcome_spec.json`, and `prepared_snapshot.json` are setup/provenance artifacts only
- the presence of sidecars does not prove seeded runtime execution exists in the shipped flow
- the existence of `backend/app/services/uncertainty_resolver.py` does not upgrade the shipped runtime claim unless it is actually wired into the Step 3 execution path
- do not convert a successful Step 2 probabilistic re-prepare into a claim that Step 4 probabilities or Step 5 probabilistic chat are supported

### Minimum written readout language

Every successful readout should use language equivalent to:

- Step 2 probabilistic prepare is available
- legacy baseline prepare remains intact
- explicit re-prepare can persist probabilistic sidecar artifacts for the same simulation
- downstream runtime/report/interaction support remains partial and not yet fully grounded at this time

## 10. Residual Risks

- there is still no dedicated automated Step 2 smoke harness; the current baseline is command-backed plus manual evidence
- Step 2 auto-starts the legacy prepare path on mount, which increases the chance of mixed-state operator confusion if evidence is captured carelessly
- capability discovery is global, not project-specific
- probabilistic controls currently cover uncertainty profile and outcome metrics, but not run count or ensemble budget
- the current prepared artifact summary is intentionally compact and may be misread as more complete than it is if the readout language is sloppy
- Step 3 through Step 5 remain unchanged, so a large portion of the probabilistic program is still outside the current smoke baseline
- runtime and report expectations can be overstated if reviewers see `prepared_snapshot.json` and assume the rest of the stack already consumes it

## 11. Non-Goals for This Baseline

This baseline does not attempt to prove:

- probabilistic runtime correctness
- seeded ensemble reproducibility in the user-facing flow
- aggregate metric correctness
- scenario clustering
- probabilistic report section generation
- calibrated probability claims
- release readiness for the full stochastic probabilistic roadmap

If any review asks for those conclusions, the correct answer is that they are not established by the current Step 2 smoke/evidence baseline.
