# Local Probabilistic Operator Runbook

This runbook is the local operating guide for the bounded probabilistic path in MiroFishES.

It is intentionally practical. It focuses on what the current code, tests, and verification commands support, not on the larger aspiration around forecasting.

## What This Runbook Covers

Supported now:

- Step 1 graph build through the normal project flow
- Step 2 forecast prepare and Step 2 handoff into stored Step 3 shells
- Step 3 launch, stop, retry, cleanup, child rerun, and history re-entry for stored shells
- Step 4 scoped probabilistic report context and one bounded compare workspace
- Step 5 scoped Report Agent context, one bounded compare handoff, and history re-entry through saved report state

Still out of scope:

- broad calibrated forecasting claims
- scope-aware interviews or surveys
- cross-report or cross-simulation compare
- release-grade operator proof

## Verification Ladder

Run these from the repo root.

### Broad repo verify

```bash
npm run verify
```

Use this for code and build health in the current worktree. It runs frontend tests, the frontend build, and backend pytest. It does not inspect persisted forecast artifacts or browser routing.

### Confidence verify

```bash
npm run verify:confidence
```

Use this when the change touches confidence, backtests, calibration, provenance, report context, or the Step 2 through Step 5 copy that depends on those states.

### Targeted non-binary verify

```bash
npm run verify:nonbinary
```

Use this when the change touches the active typed forecast path for `binary`, `categorical`, or `numeric` questions and you want the tightest backend plus runtime signal before running the broader wrappers.

### Forecasting verify

```bash
npm run verify:forecasting
```

This is the main non-mutating forecasting wrapper. It runs broad repo verify, targeted non-binary verify, confidence verify, the active artifact scan, and the fixture-backed smoke suite.

The active artifact scan is intentionally narrow. A green result here only means the active simulation set is clean enough for the default scan.

### Historical artifact verify

```bash
npm run verify:forecasting:artifacts:all
```

Use this when you need the full historical backlog audited. It includes archived simulations that are excluded from the default active scan.

Use `npm run forecasting:migrate:historical` when archived simulations need to be migrated into the current artifact contract.

After migration, this command passes only when archived simulations are either:

- remediated into the current contract, or
- explicitly marked in `forecast_archive.json` as `historical_conformance.status=quarantined_non_ready` for the currently allowed residual issue code `grounding_bundle_not_ready`

Archive markers alone are not remediation. `npm run forecasting:archive:historical` only records pending-remediation archive metadata and still refuses to mark active simulations archived unless `--allow-active` is passed directly to the backend script.

### Fixture-backed smoke verify

```bash
npm run verify:smoke
```

This suite uses deterministic fixture data and Playwright-owned local env overrides from [playwright.config.mjs](../playwright.config.mjs). It checks the bounded browser path through Step 2, Step 3, Step 4, Step 5, and history replay.

It proves routing and surfaced state. It does not prove live LLM or Zep access, live Step 2 prepare, or live Report Agent chat responses.

### Live mutating operator verify

```bash
PLAYWRIGHT_LIVE_ALLOW_MUTATION=true npm run verify:operator:local
```

This suite mutates a real local simulation family and is intentionally gated.

Use it only when:

- mutation is acceptable
- the local environment is configured for live use
- you want fresh evidence for one real Step 2 through Step 5 path

It covers Step 2 handoff, Step 3 recovery actions, Step 4 report generation, Step 4 compare handoff, and one real Step 5 Report Agent message against a saved live report context.

If `PLAYWRIGHT_LIVE_SIMULATION_ID` is unset, the Step 2/3 portion of the harness uses the newest non-archived prepared-and-grounded simulation, while the live Step 4/5 portion prefers the newest prepared-and-grounded simulation family that already has completed ready run-scoped evidence. Smoke fixtures and archived simulations are skipped automatically.

## Workflow And Evidence Terms

Use these terms literally.

- `artifact completeness`: the required Step 2 probabilistic artifacts exist.
- `grounding attachment status`: `grounding_bundle.json` exists and its `status` is `ready` only when upstream grounding was actually attached.
- `workflow handoff status`: the Step 2 stored-run handoff gate. It combines artifact completeness and grounding attachment status.
- `confidence gate status`: the Step 4 and Step 5 calibration gate. It passes only when the supported binary, categorical, or numeric answer lane has valid type-correct calibration and backtest artifacts plus matching provenance.
- `active forecasting evidence`: simulations that count for the normal artifact scan and default history views.
- `archived historical evidence`: saved simulations marked with `forecast_archive.json`. They remain readable but stop counting as active readiness evidence by default.
- `historical conformance status`: the archive-side artifact contract for archived simulations. `pending_remediation` means the backlog still needs repair, `remediated` means the archived artifact set meets the current contract, and `quarantined_non_ready` means the simulation remains read-only historical evidence with explicitly listed non-ready issue codes.
- `active artifact scan`: the default scan path. It evaluates only active simulations.
- `historical artifact scan`: the all-history scan path. It includes archived simulations so backlog problems stay visible and currently only accepts explicit quarantine for archived `grounding_bundle_not_ready`.

## Local Prerequisites

### Tooling

- `node >= 18`
- `python >= 3.11`
- `uv`
- `npm run setup:all`
- `npx playwright install chromium`

### Live environment

For real local Step 2 through Step 5 use, the repo expects a root `.env` with real keys and the probabilistic flags enabled:

```env
LLM_API_KEY=...
ZEP_API_KEY=...

PROBABILISTIC_PREPARE_ENABLED=true
PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED=true
PROBABILISTIC_REPORT_ENABLED=true
PROBABILISTIC_INTERACTION_ENABLED=true

CALIBRATED_PROBABILITY_ENABLED=false
```

`CALIBRATED_PROBABILITY_ENABLED` is only a surface flag. It does not make any metric pass the confidence gate by itself.

### Capability check

Before debugging UI behavior, check the backend surface directly:

```bash
curl http://localhost:5001/api/simulation/prepare/capabilities
```

For the bounded probabilistic path, expect:

- `probabilistic_prepare_enabled=true`
- `probabilistic_ensemble_storage_enabled=true`
- `probabilistic_report_enabled=true`
- `probabilistic_interaction_enabled=true`

## Operator Flow

### Step 1

Upload source material and complete the normal graph build. You need a real `simulation_id` before any probabilistic path matters.

### Step 2

Stay in `Forecast` mode when probabilistic prepare is available.

What Step 2 does:

- writes or refreshes the forecast-oriented artifact set
- computes readiness summaries
- prepares the later Step 3 shell contract

What Step 2 does not do:

- it does not launch a run
- it does not make the report calibrated
- it does not make Step 4 or Step 5 stronger than the saved artifacts support

The important distinction is this:

- forecast prepare writes artifacts
- Step 2 handoff creates or reopens the stored Step 3 shell
- Step 3 launch starts execution later, when the operator chooses to do it

Grounding status in `grounding_bundle.json` should be read plainly:

- `ready`: the required upstream source and graph-build evidence is attached
- `partial`: some durable evidence exists, but the handoff gate should still block
- `unavailable`: there is no usable upstream grounding evidence for the forecast path

If Step 2 helper text says handoff is blocked, treat that as the real backend gate, not as a cosmetic warning.

### Step 3

Step 3 is the stored-shell operator view.

A prepared shell stays passive until `Launch selected run`. That point matters because Step 3 is about execution control and observed runtime state, not about stronger forecast certainty than the prepared artifacts support.

Current operator actions:

- `Launch selected run`
- `Stop selected run`
- `Retry selected run`
- `Clean selected run`
- `Create child rerun`

Their current semantics are narrow:

- retry restarts the same `run_id`
- child rerun creates a new `run_id` with lineage back to the source run
- cleanup clears transient runtime traces while preserving the stored shell inputs
- cleanup is a recovery action, not a delete action

### Step 4

Step 4 is still the legacy report-generation surface plus an additive probabilistic context layer.

Treat that probabilistic layer as descriptive:

- ensemble and family summaries are empirical
- selected runs are observed
- sensitivity is descriptive or designed-comparison evidence, not causal proof

Step 4 can surface:

- grounding status and citations
- explicit `ensemble`, `cluster`, or `run` scope
- support counts and warnings
- representative runs and selected family evidence
- selected-run assumption ledger details when present
- `answer_confidence_status`
- calibration provenance only when the confidence gate is truly ready
- one bounded compare workspace

Do not call the report body calibrated just because calibration artifacts exist somewhere nearby.

### Step 5

Only the Report Agent lane is probabilistic-context-aware.

It can use:

- saved report scope
- explicit route scope
- one manual in-session scope switch
- one bounded compare handoff from the current saved report context

Interviews and surveys remain legacy-scoped.

## History and Archives

History can currently:

- reopen Step 3 when probabilistic runtime scope is available
- reopen Step 4 from the latest saved report
- reopen Step 5 from the latest saved report

Archive behavior is deliberate:

- active history excludes archived simulations by default
- `/api/simulation/history?include_archived=true` includes them again
- archived simulations carry `forecast_archive` metadata
- archived simulations can additionally carry `historical_conformance` metadata that records whether they were remediated or explicitly quarantined as non-ready historical evidence
- archived simulations remain readable, but they stop counting as active forecasting evidence
- `npm run verify:forecasting:artifacts` is active-only
- `npm run verify:forecasting:artifacts:all` audits active plus archived history
- `npm run verify:forecasting:artifacts:all` only passes when archived backlog gaps are either remediated or explicitly quarantined as non-ready historical evidence
- a green all-history scan is still not a claim that archived simulations are forecast-ready; quarantined archived simulations remain non-ready by design
- a green active scan is not a claim about historical backlog health

## Recovery Paths

### Step 2 handoff is blocked

Check the helper text first. The usual causes are:

- missing required Step 2 artifacts
- `grounding_bundle.json` present but not `ready`
- probabilistic runtime shells disabled by backend capability flags

### A run is active and you want to retry or branch it

Stop it first. Cleanup and child rerun are meant for inactive shells.

### Cleanup is refused

That usually means the shell still has active runtime state. Wait for the run to become inactive, then clean it up.

### You need a new branch of execution

Use `Create child rerun`. That preserves the existing stored run as evidence and creates a new `run_id` with lineage.

## Evidence Locations

- fixture-backed smoke artifacts: `output/playwright/fixtures/`
- live local operator evidence: `output/playwright/live-operator/`
- active artifact scan contract: `backend/scripts/scan_forecasting_artifacts.py`
- historical archive marker logic: `backend/scripts/archive_nonconforming_forecasting_artifacts.py`
- current browser contracts: `tests/smoke/probabilistic-runtime.spec.mjs` and `tests/live/probabilistic-operator-local.spec.mjs`

## Known Limits

- Live Step 2 prepare still depends on real LLM and Zep configuration.
- The smoke suite is good routing evidence, but it is not proof that live prepare or live chat works in a fresh environment.
- Confidence language must stay bounded to supported ready binary, categorical, or numeric answer lanes with valid provenance.
- The repo has local bounded operator evidence, not release-grade rollout evidence.
