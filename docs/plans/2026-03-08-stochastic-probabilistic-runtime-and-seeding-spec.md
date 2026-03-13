# Stochastic Probabilistic Simulation Runtime and Seeding Spec

**Date:** 2026-03-08

## 1. Purpose

Define how runs are launched, isolated, seeded, and cleaned up in probabilistic mode.

## 2. Run lifecycle

1. prepare simulation
2. create ensemble
3. resolve one run config
4. write run manifest and resolved config
5. launch runtime with run-specific directory and seed
6. stream logs and state
7. extract metrics
8. mark run complete
9. aggregate ensemble outputs

## 3. Current implemented seed flow

Implemented today:

- `root_seed` may be provided at ensemble-creation time
- `run_manifest.json` persists `root_seed` and `seed_metadata.resolution_seed`
- `SimulationRunner.start_simulation(...)` reads the stored run manifest for one ensemble member and passes one explicit `--seed` argument to the runtime script
- `run_parallel_simulation.py`, `run_twitter_simulation.py`, and `run_reddit_simulation.py` all accept `--seed`
- the single-platform scripts build an explicit `random.Random` instance for their scheduling helpers
- the parallel script derives separate Twitter and Reddit RNG streams from the root runtime seed for its scheduling helpers

Still planned, not yet implemented:

- `config_seed`
- `event_seed`
- `twitter_seed` as a persisted artifact field rather than a runtime-derived internal stream
- `reddit_seed` as a persisted artifact field rather than a runtime-derived internal stream
- `analysis_seed`

## 4. Seeding rules

- identical inputs and identical seeds must resolve identical `resolved_config.json`
- runtime scheduling helpers should use explicit RNG objects instead of hidden module-global randomness
- dual-platform runs should not share one uncontrolled RNG stream
- seeded guarantees must be documented as "best effort" where external LLM behavior cannot be fully controlled

## 5. Runtime isolation rules

- every member run writes to its own run directory
- `SimulationRunner` tracks process state by a run-scoped identity instead of `simulation_id` alone
- runtime scripts now accept explicit `--run-dir` and use it as the working root instead of inferring one shared root from `simulation_id`
- stop and cleanup actions target one run unless explicitly asked to target the full ensemble

## 6. Reproducibility limits

The system must explicitly document:

- which stages are seed-controlled
- which stages remain LLM-dependent and may vary
- which outputs are guaranteed repeatable
- which outputs are only approximately repeatable

Current repo-grounded limit:

- prepare-time resolution is seed-controlled and tested
- runtime launch now preserves the chosen seed explicitly at the process boundary
- scheduling helpers inside the scripts now use explicit RNG objects, but the scripts still call `apply_runtime_seed(...)` at startup and downstream OASIS/LLM behavior may vary
- runtime reproducibility must therefore remain documented as best-effort rather than deterministic
