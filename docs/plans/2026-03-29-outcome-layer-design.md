# Outcome Layer Expansion Design

**Date:** 2026-03-29

**Goal:** Expand the probabilistic outcome layer so forecasting and report stages can reason over richer observed outcomes than simple counts and shares, without overstating what the raw run artifacts support.

## Scope

This wave stays inside the existing backend probabilistic stack:

- `backend/app/models/probabilistic.py`
- `backend/app/services/outcome_extractor.py`
- `backend/app/services/ensemble_manager.py`
- backend unit tests for schema, extraction, and aggregate summary behavior

It does not add calibration, causal inference, audience exposure estimation, or parameterized outcome DSLs.

## Design

### Registry Strategy

Keep the metric registry explicit and allowlisted. Add only metrics that can be computed conservatively from current run artifacts:

- action logs in `twitter/actions.jsonl`, `reddit/actions.jsonl`, or legacy `actions.jsonl`
- `simulation_end` markers
- run-state timestamps
- resolved config hot topics and action payload topic hints

New metrics should land as explicit IDs with clear labels, units, aggregation kinds, and value kinds. Unsupported metrics remain out of the registry.

### Extraction Strategy

`OutcomeExtractor` remains the single truth-mapping layer for run-level observed metrics.

Add:

- richer per-run metric computation for binary occurrence, threshold crossing, time-to-event, severity bands, diffusion/reach, persistence/volatility, cross-platform lag/transfer, and concentration/tail-risk where current logs make that possible
- explicit warning propagation when a requested metric cannot be computed from the available artifacts
- one topic-normalization path so `topic`, `topics`, and downstream legacy `top_topics` payload shapes resolve into one consistent internal representation

Undefined metrics must be preserved as `value: null` with warnings, not silently coerced to `0`, `false`, or `"none"` when the raw evidence is insufficient.

### Aggregate Summary Strategy

`EnsembleManager` keeps the current binary/categorical/continuous aggregation model, but it must preserve richer metric metadata and warnings across the pipeline.

Add:

- normalization for legacy metric entry shapes
- normalization for `top_topics` item shapes such as `{topic, count}` versus `{topic, mentions}`
- aggregated warning visibility for metrics that had missing or degraded run-level evidence

The summary layer should remain empirical and observational only.

## Deferred

This wave intentionally defers:

- external audience reach or impression estimation
- calibrated probabilities
- sentiment or polarization claims not directly stored in the logs
- intervention uptake metrics that require explicit intervention artifacts
- generic threshold or severity-band DSLs
