# Probabilistic Reporting Surfaces Design

## Goal

Make Step 4 and Step 5 consume probabilistic artifacts as first-class evidence and provenance, instead of showing them as sidecars around a legacy-only report flow.

## North Star

The operator should be able to see, in one place, what scope they are looking at, how much support exists behind each claim, which warnings apply, which representative runs anchor the summary, which assumptions shaped the selected run, and whether any calibration language is actually backed by valid artifacts.

This wave stays additive and truthful:

- empirical remains empirical
- observational remains observational
- calibrated language appears only when valid calibration artifacts exist
- compare stays bounded and evidence-led rather than becoming a broad new workflow

## Current Gaps

1. Step 4 report generation builds `probabilistic_report_context` only after the report body is already generated.
2. Step 5 report-agent chat can use saved probabilistic context from an existing report, but it does not reliably build scoped context on demand for direct probabilistic lanes.
3. Frontend probabilistic cards summarize status, but they do not surface enough provenance and evidence detail to support operator judgment.
4. Compare is still absent as a workflow, even though the backend already has representative runs and scenario-family structure.

## Design

### 1. Report-context-first backend flow

For probabilistic Step 4 requests, the backend should build `probabilistic_report_context` before report generation and pass it into `ReportAgent`.

That context should become part of:

- outline planning input
- section-generation guidance
- saved report metadata
- scoped Step 5 report-agent chat

This changes the probabilistic layer from “saved alongside the report” to “used to shape the report.”

### 2. Stronger report-context contract

`probabilistic_report_context` should normalize evidence-oriented fields so both prompts and UI can consume them directly:

- explicit `scope` blocks for ensemble, cluster, and run records
- `support` blocks with counts/fractions where available
- `warnings`
- `representative_runs`
- selected-run `assumption_ledger` details when persisted
- calibration provenance only when a valid ready calibration summary exists

The artifact should remain conservative and compatible with existing consumers.

### 3. Step 4 operator surface

Step 4 should still keep the existing visual language and report layout, but the probabilistic panel should become more inspectable:

- evidence/provenance summary
- support counts and warnings
- representative run strip
- selected-run assumption ledger details
- calibration provenance strip when valid

The bounded compare surface for this wave should live in Step 4 as a compare card. It will compare:

- selected run vs representative runs
- selected run vs representative scenario families

This is not a general compare workspace. It is a focused operator card that reuses existing report-context artifacts.

### 4. Step 5 scoped probabilistic lane

Step 5 should distinguish the report-agent lane from interviews and survey tools.

For report-agent chat:

- if probabilistic scope is present, load or build scoped report context
- expose clear probabilistic evidence banners and provenance
- add compare-oriented starter prompts tied to the Step 4 compare card

For interviews and surveys:

- preserve legacy semantics unless or until those lanes get explicit probabilistic backing in a later wave

## Truthfulness Rules

- No calibrated language unless valid calibration artifacts exist and pass readiness gating.
- Support counts and warnings must be shown rather than smoothed over.
- Compare copy must describe observed differences, not causal conclusions.
- Selected-run assumption details must come from the stored ledger only.

## Testing Strategy

1. Backend red-green tests for:
   - report generation building context before agent execution
   - Step 5 scoped chat using probabilistic context directly
   - report-context enrichment for evidence/provenance/assumption details
2. Frontend/unit tests for:
   - new report/interaction state derivations
   - compare-card derivation
   - calibration gating copy
3. Targeted smoke verification:
   - backend test slices
   - frontend unit tests
   - frontend build if the changed surface area warrants it

## Out of Scope

- broad compare workspace
- calibrated forecast transformations beyond existing artifacts
- probabilistic grounding for interview-agent or survey lanes
- redesign of the main report layout
