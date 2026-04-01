# Documentation Guide

Most people only need four files:

- [Root README](../README.md): front door, setup, readiness terms, and verification ladder
- [Local probabilistic operator runbook](local-probabilistic-operator-runbook.md): local Step 1 through Step 5 operating guide
- [What MiroFishES adds](what-mirofishes-adds.md): plain-language fork delta and current boundaries
- [Forecast readiness chain ledger](plans/2026-03-31-forecast-readiness-chain.md): current implementation contract, phase handoffs, and final readiness evidence
- [Forecast readiness status](plans/2026-03-31-forecast-readiness-status.json): machine-readable phase status and verification record

Everything else under `docs/plans/` is historical planning unless one of the files above points to it as current context.

If documents disagree, trust the code, tests, scripts, and fresh command output. In practice that means:

1. code paths and current tests first
2. package scripts and verification wrappers next
3. front-door docs after that
4. older plans only for rationale

## Suggested Reading Paths

For a new engineer:

1. [Root README](../README.md)
2. [What MiroFishES adds](what-mirofishes-adds.md)
3. [Local probabilistic operator runbook](local-probabilistic-operator-runbook.md)

For someone auditing the forecasting slice:

1. [Root README](../README.md)
2. [Forecast readiness chain ledger](plans/2026-03-31-forecast-readiness-chain.md)
3. [Forecast readiness status](plans/2026-03-31-forecast-readiness-status.json)
4. [Local probabilistic operator runbook](local-probabilistic-operator-runbook.md)

For higher-level ambition rather than the current contract:

- [North-star forecast upgrades](plans/2026-03-28-mirofish-high-impact-forecasting-upgrades.md)
- [Hybrid forecasting utility design](plans/2026-03-30-hybrid-forecasting-utility-design.md)
- [Hybrid forecasting utility execution ledger](plans/2026-03-30-hybrid-forecasting-utility-execution.md)
