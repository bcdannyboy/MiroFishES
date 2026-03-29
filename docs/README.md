# Documentation Guide

This directory contains three different kinds of documents:

1. front-door docs that explain what MiroFishES is and how to run it
2. current-state contracts that describe what the repo truthfully supports today
3. historical plan and implementation notes that explain how the current system was built

## Start Here

If you are new to the repo, read these first:

- [Root README](../README.md): project front door, fresh-start workflow, and verification ladder
- [What MiroFishES adds](what-mirofishes-adds.md): canonical explanation of how this repo differs from the fork-era MiroFish baseline
- [Forecasting integration hardening wave](plans/2026-03-29-forecasting-integration-hardening-wave.md): authoritative current implementation contract for the forecasting control plane

## By Audience

### Engineers

Read in this order:

1. [Root README](../README.md)
2. [What MiroFishES adds](what-mirofishes-adds.md)
3. [Forecasting integration hardening wave](plans/2026-03-29-forecasting-integration-hardening-wave.md)
### Operators

Read in this order:

1. [Root README](../README.md)
2. [Local probabilistic operator runbook](local-probabilistic-operator-runbook.md)
3. [Forecasting integration hardening wave](plans/2026-03-29-forecasting-integration-hardening-wave.md)

### Reviewers and auditors

Read in this order:

1. [What MiroFishES adds](what-mirofishes-adds.md)
2. [Forecasting integration hardening wave](plans/2026-03-29-forecasting-integration-hardening-wave.md)
3. [North-star forecast upgrades](plans/2026-03-28-mirofish-high-impact-forecasting-upgrades.md)
4. [Local probabilistic operator runbook](local-probabilistic-operator-runbook.md)

## Current-State Docs

Use these when you need the truth about the repo **now**, not the original ambition:

- [Forecasting integration hardening wave](plans/2026-03-29-forecasting-integration-hardening-wave.md)
- [Local probabilistic operator runbook](local-probabilistic-operator-runbook.md)

## Historical Plans

The `docs/plans/` directory contains the design and implementation trail that produced the current forecasting stack. Those files are useful for rationale and audit history, but they are not all current product docs.

When a historical plan conflicts with the current repo, prefer:

1. the code
2. the root README
3. the current-state notes dated `2026-03-29`
