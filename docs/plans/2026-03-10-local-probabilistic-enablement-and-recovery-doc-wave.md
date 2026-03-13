# Local Probabilistic Enablement And Recovery Doc Wave

**Date:** 2026-03-10

## Goal

Make the bounded local probabilistic Step 2 through Step 5 path discoverable and operable from zero context by surfacing:

- the exact opt-in rollout flags
- the exact startup and capability-check path
- the exact Playwright/browser prerequisites
- the exact live-operator simulation override
- the exact artifact inspection paths and cleanup behavior
- the truthful H5 boundary between a bounded local runbook and a full release-ops package

## Why this wave is next

The runtime and browser slices are ahead of the operator docs:

- `backend/app/config.py` keeps the probabilistic flags off by default
- `.env.example` previously did not surface those flags
- `tests/live/probabilistic-operator-local.spec.mjs` falls back to one repo-local simulation family unless `PLAYWRIGHT_LIVE_SIMULATION_ID` is set
- cleanup preserves `run_manifest.json` and `resolved_config.json` but may remove runtime logs, so artifact inspection needed to be explained explicitly

Without those truths in the user path, a fresh developer can follow the old docs correctly and still fail to unlock or verify the bounded local probabilistic path.

## Planned edits

- update `.env.example` with the probabilistic rollout flags and calibration-off default
- update `README.md` with exact local enablement notes, capability checks, Playwright install guidance, simulation override guidance, and artifact-path guidance
- extend `docs/local-probabilistic-operator-runbook.md` with startup steps, capability checks, simulation override guidance, and artifact inspection behavior
- refresh PM/control docs so H2/G5 describe the bounded local runbook truthfully instead of acting as if runbook support is still entirely absent

## Truth boundary after this wave

- the repo will have a bounded local operator runbook package
- the repo will still not have a full H5 release-ops package
- no document should claim release-grade readiness, controlled-beta supportability, or 100% local readiness yet
