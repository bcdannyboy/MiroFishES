# Local Probabilistic Operator Runbook

This runbook is the local operations guide for the bounded stochastic probabilistic rollout in MiroFishES.

It is intentionally narrower than the repo front door or the fork-delta explanation:

- it tells a local developer or operator how to run and recover the supported Step 1 through Step 5 path
- it names what is fixture-backed, what is local-only non-fixture, and what is still unsupported
- it does not claim 100% local readiness
- it does not try to restate the whole "what makes MiroFishES different from fork-era MiroFish" story

Read these first if you need project framing rather than operator procedure:

- [Root README](../README.md)
- [Documentation guide](README.md)
- [What MiroFishES adds](what-mirofishes-adds.md)
- [Forecasting integration hardening wave](plans/2026-03-29-forecasting-integration-hardening-wave.md)

## 1. Supported local scope

Supported now:

1. Step 1 graph build through the normal project flow
2. Step 2 forecast-first prepare when probabilistic prepare is available, including one durable upstream `grounding_bundle.json`
3. Step 3 probabilistic stored-run launch, stop, retry on the same `run_id`, cleanup, child rerun, reload, saved-record re-entry, and Step 4 scope selection across ensemble, scenario-family, and run
4. Step 4 legacy report generation plus additive observed probabilistic report context with separate upstream grounding, explicit `ensemble|cluster|run` scope, support, warnings, representative runs, assumption-ledger details, explicit `confidence_status`, calibration provenance only when a named metric is ready, and one bounded compare workspace
5. Step 5 report-agent chat grounded on explicit `ensemble|cluster|run` scope from the current route, a saved report context, or a manual in-session scope switch, with one optional bounded compare handoff and bounded upstream citations when available

Not supported yet:

1. calibrated forecast language beyond named binary metrics with ready backtest artifacts
2. scope-aware interviews or surveys
3. cross-report or cross-simulation compare
4. claiming release-grade or 100% local readiness

## 2. Evidence classes

Use these labels consistently in notes, QA readouts, and support handoffs.

| Evidence class | What to use | What it proves | What it does not prove |
| --- | --- | --- | --- |
| `unit/contract` | frontend node tests, backend pytest | code-level contract behavior | browser/runtime usability on a real project |
| `fixture-backed browser` | `npm run verify:smoke` | the bounded probabilistic shell still renders and routes correctly | live LLM/Zep prepare viability |
| `local-only non-fixture` | `PLAYWRIGHT_LIVE_ALLOW_MUTATION=true npm run verify:operator:local` | one real local operator path can work and writes durable evidence | release-grade readiness |
| `release-grade` | none today | nothing today | do not claim it |

## 3. Prerequisites

### Repository prerequisites

- `node >= 18`
- `python >= 3.11`
- `uv`
- root dependencies installed with `npm run setup`
- backend dependencies installed with `npm run setup:backend` or `uv sync` in `backend/`

### Environment prerequisites

- `.env` exists at repo root
- `LLM_API_KEY` is set
- `ZEP_API_KEY` is set
- the four probabilistic rollout flags are enabled together when you want the bounded probabilistic path:

```env
PROBABILISTIC_PREPARE_ENABLED=true
PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED=true
PROBABILISTIC_REPORT_ENABLED=true
PROBABILISTIC_INTERACTION_ENABLED=true
CALIBRATED_PROBABILITY_ENABLED=false
```

Live Step 2 probabilistic prepare is not self-contained without those keys.
Those four rollout flags default to `false` in `backend/app/config.py`, so a fresh operator must opt in explicitly.
`CALIBRATED_PROBABILITY_ENABLED` is only an artifact-reading rollout flag. It does not by itself prove any forecast metric is calibrated.

### Default local endpoints

- frontend: `http://localhost:5173`
- backend: `http://localhost:5001`

### Startup checklist

1. copy `.env.example` to `.env`
2. set `LLM_API_KEY` and `ZEP_API_KEY`
3. enable the four probabilistic rollout flags above
4. install dependencies with `npm run setup:all`
5. install Playwright browsers with `npx playwright install chromium` if they are not already present locally
6. start the stack with `npm run dev`

### Capability check

Before debugging the UI, confirm the backend capability surface:

```bash
curl http://localhost:5001/api/simulation/prepare/capabilities
```

For the bounded probabilistic path, expect these booleans to be `true`:

- `probabilistic_prepare_enabled`
- `probabilistic_ensemble_storage_enabled`
- `probabilistic_report_enabled`
- `probabilistic_interaction_enabled`

## 4. Verification ladder

Run these from the repository root.

### 4.1 Broad repo verification

```bash
npm run verify
```

Use this before trusting code changes. It should run:

- frontend unit/runtime tests
- frontend production build
- backend pytest

### 4.2 Fixture-backed browser verification

```bash
npm run verify:smoke
```

Use this to prove the bounded probabilistic browser path still works against deterministic fixtures, including:

- Step 2 prepared probabilistic state
- Step 3 missing-handoff off-state
- Step 3 stored-run shell
- Step 4 observed probabilistic addendum plus bounded compare workspace and upstream-grounding status
- Step 5 probabilistic banner truth, manual report-agent scope switching, and bounded compare handoff state
- Step 3 history replay from a saved probabilistic record
- Step 5 history replay from a saved report

### 4.3 Live local operator verification

```bash
PLAYWRIGHT_LIVE_ALLOW_MUTATION=true npm run verify:operator:local
```

Use this only when you intentionally allow mutation of a real local simulation family.

If you are not using the repo's current default local evidence family, pass the simulation explicitly:

```bash
PLAYWRIGHT_LIVE_ALLOW_MUTATION=true \
PLAYWRIGHT_LIVE_SIMULATION_ID=<simulation_id> \
npm run verify:operator:local
```

Notes:

- the test currently falls back to `sim_7a6661c37719` when `PLAYWRIGHT_LIVE_SIMULATION_ID` is unset
- that fallback is local evidence scaffolding, not a guarantee that a fresh workspace contains the same simulation family
- the target simulation must already satisfy the Step 2 forecast handoff gate; if the button stays disabled, the suite now fails fast with the visible helper-text blocker and records that blocker in `output/playwright/live-operator/latest.json`

Evidence written:

- `output/playwright/live-operator/latest.json`
- `output/playwright/live-operator/operator-pass-<timestamp>.json`

Current proven operator actions in that live path:

- Fresh live verification in the current workspace is blocked before mutation because the default local family `sim_7a6661c37719` is missing `grounding_bundle.json`, so Step 2 never reaches the forecast handoff gate.
- Historical local-only evidence still exists for Step 2 handoff plus Step 3 stop, retry, cleanup, and child rerun, but that proof is not fresh until a forecast-ready local family is supplied and the suite is rerun.
- Step 4 compare and Step 5 scope behavior are currently smoke-backed and targeted-test-backed, not freshly live-operator-backed in this workspace.

### 4.4 Focused confidence verification

```bash
npm run verify:confidence
```

Use this when confidence, backtest, calibration, or report-context code changes. It proves:

- observed-truth schema and provenance round-trips
- binary backtest artifacts persist explicit counts, scores, and skips
- calibration readiness stays bounded to binary metrics with real support
- report context surfaces `absent | not_ready | ready` confidence truthfully
- frontend runtime helpers keep Step 2 through Step 5 copy artifact-gated instead of calling the stack calibrated from config alone

## 5. Recommended local operator flow

### Step 1: Graph build

1. Upload or select source material.
2. Complete the normal graph build flow.
3. Confirm the project reaches the simulation setup view with a valid `simulation_id`.

### Step 2: Environment setup

1. If forecast prepare is available, leave Step 2 in `Forecast` mode and start that path directly.
2. Use `Legacy` only when forecast prepare is disabled or when you intentionally need the single-run path.
3. Reopening an already-prepared forecast simulation should keep Step 2 in `Forecast` mode automatically.
4. Do not treat Step 2 as report-ready or calibration-ready. It only prepares artifacts and settings.
5. Step 2 capability copy is artifact-gated. It means the repo can read confidence artifacts later, not that any named metric is already calibrated.

Step 2 grounding truth:

- `grounding_bundle.json` is the only forecast-facing upstream grounding artifact later phases should rely on.
- `ready` means uploaded-source plus graph-build artifacts were attached.
- `partial` means some durable upstream evidence exists but the bundle is incomplete.
- `unavailable` means no durable upstream evidence was attached; do not improvise live-research claims from that state.

If Step 2 says probabilistic runtime shells are disabled, do not keep clicking into Step 3. That is a real backend capability off-state.

### Step 3: Stored-run operator workflow

Current supported actions:

- `Launch selected run`: start a prepared stored shell
- `Retry selected run`: restart the same stored `run_id`
- `Stop selected run`: stop active runtime state
- `Cleanup selected run`: clear volatile runtime artifacts after the run is inactive
- `Create child rerun`: clone the current run into a new child `run_id`

Rules:

1. Retry keeps the same `run_id`.
2. Child rerun creates a new `run_id` and preserves lineage.
3. Cleanup is a recovery action, not a delete action.
4. Cleanup must not be used on an active run.

### Step 3 saved-record re-entry

History can now reopen Step 3 when a saved probabilistic record exists:

- if a saved probabilistic report already points to `ensemble_id` plus `run_id`, History reopens that exact Step 3 shell
- if no report exists but storage history can resolve a latest probabilistic run, the replay target can still come from storage metadata

What remains out of scope:

- richer ensemble-history browsing beyond the existing history record model
- cross-report or cross-simulation compare

### Step 4

Step 4 remains the legacy report-generation surface plus additive observed probabilistic context. Treat the probabilistic addendum as empirical or observational only.

Current Step 4 probabilistic-native evidence includes:

- upstream grounding status, boundary note, and stable citations when available
- scope at the ensemble, scenario-family, or run level
- support counts and surfaced warnings
- representative runs, selected scenario-family evidence, and selected-run assumption-ledger details where present
- `confidence_status` always: `absent`, `not_ready`, or `ready`
- calibration provenance only when ready calibration artifacts exist
- one dedicated bounded compare workspace with inspectable left/right scope snapshots and one Step 5 handoff

Do not describe the report body itself as calibrated. At most, cite explicit backtested calibration provenance for the supported metric named in the artifact, and only when `confidence_status.status == ready`.

### Step 5

Only the report-agent chat lane is probabilistic-context-aware. It can use explicit `ensemble|cluster|run` route scope, saved report context, or one manual in-session scope switch. Interviews and surveys remain legacy-scoped.

Current Step 5 operator expectations:

- the probabilistic banner can reflect live scoped context, not just saved-report reopen state
- report-agent chat can ground answers on explicit scope, support, warnings, representative runs, assumption-ledger details, and calibration provenance when valid
- operators can switch the report-agent lane across bounded `ensemble`, `cluster`, and `run` scopes without changing report identity
- compare support can arrive either from Step 4 handoff or bounded starter prompts, but it remains one saved-context compare at a time

## 6. Recovery paths

### Step 2 handoff blocked

Cause:

- runtime shells disabled by capability state
- probabilistic prepare still in flight
- missing required probabilistic sidecar artifacts

Action:

1. wait for prepare to finish
2. confirm the Step 2 helper text
3. if capabilities disable runtime shells, stay on legacy or re-enable the backend flags

### Run is active and you want a clean retry

Action:

1. click `Stop selected run`
2. wait until the run becomes inactive
3. click `Retry selected run`

### Cleanup is refused

Cause:

- cleanup was attempted while the run still had active runtime state

Action:

1. stop the run first
2. refresh or wait for the Step 3 shell to show an inactive status
3. run cleanup again

### You need a fresh branch of execution

Action:

1. keep the source run intact
2. click `Create child rerun`
3. confirm Step 3 switches to the new child `run_id`

### Stuck-run first response

Use this conservative sequence:

1. inspect the Step 3 status, timeline, and actions
2. inspect `run_manifest.json` and any surviving runtime logs under the current run directory
3. attempt `Stop selected run`
4. if the run becomes inactive, use `Cleanup selected run`
5. relaunch with `Retry selected run` if you want the same shell, or `Create child rerun` if you want a fresh child run
6. if the shell stays unavailable, reopen Step 3 from History or return to Step 2 and create a new stored shell

This is a local operator recovery path, not release-grade incident handling.

## 7. History behavior

History currently supports:

- Step 3 replay when probabilistic runtime scope can be resolved
- Step 4 reopen from the latest saved report
- Step 5 reopen from the latest saved report

History still does not support:

- compare
- deep ensemble-history browsing as a first-class route

## 8. Known limitations

1. Live Step 2 probabilistic prepare still depends on LLM plus Zep prerequisites.
2. The deterministic smoke fixture is separate QA evidence, not proof that live prepare is self-contained.
3. Probability language must stay empirical, observed, or observational unless a valid backtested calibration artifact exists for the cited metric, and even then that does not imply globally calibrated forecasting.
4. Step 5 beyond the report-agent lane is still legacy-scoped.
5. The repo has local-only non-fixture operator evidence, not release-grade rollout evidence.

## 9. Artifact inspection paths

Use this generic path pattern for one stored run:

`backend/uploads/simulations/<simulation_id>/ensemble/ensemble_<ensemble_id>/runs/run_<run_id>/`

Files to inspect:

- `run_manifest.json`: durable lifecycle, lineage, and artifact pointers
- `resolved_config.json`: durable resolved inputs for the stored run
- `simulation.log`: runtime log if the run has been launched and not cleaned
- `twitter/actions.jsonl`: platform action log if present and not cleaned
- `reddit/actions.jsonl`: platform action log if present and not cleaned

Cleanup behavior to remember:

- cleanup preserves `run_manifest.json` and `resolved_config.json`
- cleanup may remove `simulation.log`, `twitter/actions.jsonl`, and `reddit/actions.jsonl`

## 10. Current evidence locations

- live local operator capture: `output/playwright/live-operator/latest.json`
- fixture-backed smoke suite: `tests/smoke/probabilistic-runtime.spec.mjs`
- local-only operator suite: `tests/live/probabilistic-operator-local.spec.mjs`
- PM/control packet: `docs/plans/2026-03-08-stochastic-probabilistic-*.md`

## 11. Escalation boundary

Escalate beyond this runbook when:

1. Step 2 cannot complete a live prepare even though credentials and flags are correct
2. Step 3 status, stop, cleanup, or rerun behavior diverges from the current tests and evidence files
3. a report or interaction surface implies calibrated support or unsupported probabilistic scope
4. someone wants to claim 100% local readiness or release-grade evidence
