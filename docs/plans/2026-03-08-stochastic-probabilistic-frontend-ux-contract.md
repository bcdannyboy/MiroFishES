# Stochastic Probabilistic Frontend UX and State-Ownership Contract

**Date:** 2026-03-09

## 1. Purpose

This document closes the ready planning gap for `F0.1` and `F0.2`.

It defines:

- the user-visible vocabulary for probabilistic features
- the provenance and forbidden-language rules that keep the UI aligned with the program probability contract
- the ownership and placement rules for `mode`, `ensemble_id`, `run_id`, and `cluster_id` across Step 2, Step 3, Step 4, Step 5, history, and routing

This is a frontend UX and state contract. It is not approval to ship UI that the backend does not yet support.

## 2. Current Product Truth

As of 2026-03-08, the live product truth is:

- Step 2 and a bounded Step 3 shell are the live probabilistic slices.
- Step 2 supports capability discovery, a legacy-vs-probabilistic prepare choice, probabilistic draft controls, and a prepared-artifact summary.
- Step 3 has a truthful probabilistic ensemble browser keyed by `simulation_id` plus query-state `mode`, `ensembleId`, and `runId`, and it now renders stored-run browsing, selected-run recovery, and read-only observed ensemble analytics cards from persisted summary/cluster/sensitivity artifacts.
- Step 4 remains a legacy report experience keyed by `report_id`.
- Step 5 remains keyed by `report_id` and `simulation_id`, but the report-agent lane can now recover saved probabilistic report context for the exact saved report while interviews and surveys remain legacy-scoped.
- history remains simulation/report centric; Step 4 and Step 5 can reopen from a saved report, but Step 3 still cannot replay and there are still no ensemble-history rows
- backend storage APIs now create and inspect ensembles and runs, and the current Step 2 -> Step 3 browser already routes one `ensemble_id` plus one initial `run_id`
- routing owns `simulationId` and `reportId` today, plus Step 3 query-state `mode`, `ensembleId`, and `runId`; `cluster_id` remains absent

Program implication:

- no Step 4 or Step 5 surface should imply more probabilistic grounding than the repo actually supports
- no frontend surface should imply ensemble runtime, scenario clustering, tail-risk analysis, or calibration support before the corresponding backend artifacts exist

## 3. MVP Boundary

### In MVP / current ready scope

- Step 2 terminology and copy discipline
- Step 2 ownership of the editable probabilistic prepare state
- Step 2 creation of one stored ensemble plus one initial selected run for Step 3 under explicit backend capabilities
- Step 3 ownership of one probabilistic ensemble browser and its strict-handoff/off-state behavior
- Step 4 additive observed report-context cards under the existing `report_id` route
- bounded Step 5 report-agent chat grounding plus saved-report Step 5 re-entry under the existing `report_id` route
- explicit unsupported-state and legacy-fallback wording
- documentation decisions for later Step 4 through Step 5 placement
- history staying on the existing legacy route model
- compare remaining out of scope

### Deferred or post-MVP

- deeper Step 4 scenario family, representative-run, and tail-risk views
- Step 5 ensemble-vs-cluster-vs-run chat scope
- ensemble-aware history rows
- history-driven Step 3 re-entry beyond the current query-state handoff
- compare route
- calibrated probability UI

## 4. User-Visible Vocabulary Contract

The terms below are the approved meanings for user-facing copy, labels, helper text, report cards, and chat scope labels.

| Term | Approved user-visible meaning | Release posture | Required guardrail |
| --- | --- | --- | --- |
| `ensemble` | A defined family of simulation runs launched from the same prepared baseline with explicit uncertainty settings. | Live only as backend-backed identifier and Step 3 shell metadata; broader UX is still deferred. | Must refer to an explicit run family, not a vague "set of possibilities." |
| `run` | One concrete execution inside an ensemble. | Live in the current Step 3 browser. | Must never be presented as a probability distribution by itself. |
| `scenario family` | A grouped pattern of similar runs that describe one recurring future shape. | Deferred until clustering artifacts exist. | Must identify that it is a grouped family, not a single run. |
| `tail risk` | A rare but important outcome pattern observed in a run family. | Deferred until aggregate evidence exists. | Must be grounded in explicit run-family evidence, never in one anecdote or one run. |
| `empirical probability` | An observed frequency over an explicit run family. Plain-language alternative: `empirical estimate`. | Deferred until aggregate artifacts exist. | Must carry run-count context such as `observed in X of Y runs` or an equivalent run-family denominator. |
| `calibrated probability` | A probability that has been adjusted using a validated calibration artifact. | Post-MVP only. Not supported in the current product. | Must cite the calibration artifact or version. If none exists, this term is forbidden. |
| `representative run` | One example run chosen to illustrate a scenario family or important outcome pattern. | Deferred until report/runtime context supports it. | Must be framed as an example, never as automatically the most likely future. |
| `thin evidence` | Evidence exists, but support is weak because the run family is small, degraded, incomplete, or otherwise unstable. | Deferred until backend/report context can justify it. | Must be presented as a caution state, not as a numeric probability. |
| `unsupported` or `unavailable` | The current release or current artifact set cannot support the requested probabilistic claim or scope. | Live now as an off-state policy. | Must be used instead of inventing a value, placeholder percentage, or fake probabilistic shell. |

## 5. Terminology Rollout Rules By Surface

### Step 2

Allowed now:

- `Legacy`
- `Probabilistic`
- `Uncertainty profile`
- `Empirical outcome metrics`
- `Prepared artifact summary`
- `legacy single-run path`
- `prepared artifacts`

Not allowed yet in Step 2 primary UX:

- `ensemble`
- `run family`
- `scenario family`
- `tail risk`
- `calibrated probability`
- any probability percentage or percentile language

Reason:

- Step 2 currently prepares contracts and provenance only. It does not launch an ensemble or compute aggregate probabilities.

### Step 3

Allowed now:

- `stored run`
- `ensemble`
- `run`
- `stored run list`
- `selected run`
- `ensemble status`
- `observed analytics`
- `raw runtime status`
- `raw action history`

Deferred until runtime contracts land:

- `representative run`
- report-ready probabilistic language
- calibrated probability language

### Step 4

Allowed now:

- existing legacy report language

Deferred until report context exists:

- `empirical estimate`
- `scenario family`
- `representative run`
- `tail risk`
- `thin evidence`

### Step 5

Allowed now:

- existing legacy interaction language

Deferred until chat grounding exists:

- `ensemble scope`
- `scenario family scope`
- `representative run scope`
- probabilistic provenance labels in answers

### History

Allowed now:

- existing simulation/report history language

Deferred:

- ensemble row types
- probabilistic mode badges beyond simple future metadata display
- compare flows

## 6. Provenance Copy Rules

These rules are mandatory across Step 2 through Step 5, history, tooltips, banners, empty states, and chat answers.

### Rule 1: Scope comes before interpretation

Every probabilistic statement must make its scope clear:

- ensemble-level
- scenario-family-level
- representative-run-level

A run narrative without scope labeling is not acceptable if surrounding UI also shows probability information.

### Rule 2: Empirical and calibrated language are different products

Use `empirical estimate` or equivalent ensemble-frequency wording when the value comes from observed run counts.

Use `calibrated probability` only when a named calibration artifact exists.

Never silently upgrade empirical language into calibrated language.

### Rule 3: Step 2 is provenance, not probability

Step 2 may say that the product prepared:

- uncertainty artifacts
- outcome metric definitions
- versioned sidecar files
- a prepared artifact summary

Step 2 may not imply that it produced:

- runtime sampling results
- scenario families
- tail-risk findings
- calibrated outputs
- empirical probability values

### Rule 4: Every probability needs an evidence label

Approved patterns:

- `Empirical estimate`
- `Observed in X of Y runs`
- `Calibrated probability (calibration version: ...)`

Unlabeled numeric probability language is forbidden.

### Rule 5: Every representative narrative needs provenance

If the UI shows a representative run, it must say what it represents:

- a scenario family
- a cluster prototype
- a specific run selected as an example

The wording must not imply dominance or inevitability.

### Rule 6: Tail-risk language requires explicit rare-event evidence

`Tail risk` may only appear when aggregate artifacts explicitly support:

- low frequency
- high consequence
- run-family grounding

If those conditions are absent, the UI must fall back to plain descriptive language or an unsupported state.

### Rule 7: Thin evidence is weaker than unsupported, but both are non-promotional

Use `thin evidence` when some evidence exists but it is weak.

Use `unsupported` or `unavailable` when the evidence or capability is absent.

Do not swap between them for tone reasons. They mean different things.

### Rule 8: History and replay text must match actual replay support

History may only claim that a surface is reopenable if routing and backend support it.

Today that means:

- Step 2 can be revisited by `simulation_id`
- Step 4 can be revisited by `report_id`
- Step 5 can be revisited by `report_id`
- Step 3 replay from history is not supported

### Rule 9: Chat and report must share the same probability contract

If a term is forbidden in Step 4 report cards, it is also forbidden in Step 5 chat answers.

If a probability requires provenance in a report card, it also requires provenance in chat.

## 7. Forbidden Language

The following language is forbidden unless a later backend contract explicitly enables it.

- any percentage or probability value without run-count context or calibration provenance
- `calibrated`, `confidence-adjusted`, or equivalent wording when no calibration artifact exists
- `most likely future` when referring to a representative run
- `tail risk` for a single run anecdote
- `probability`, `chance`, or `risk` language for Step 2 prepared artifacts
- `guaranteed`, `expected`, `will happen`, or other certainty framing for empirical outputs
- language that implies Step 3 through Step 5 are already ensemble-aware today

Preferred replacements:

| Forbidden phrasing | Approved replacement |
| --- | --- |
| `82% chance of ...` | `Empirical estimate: observed in 82 of 100 runs.` |
| `Most likely scenario` | `Representative run from a larger scenario family.` |
| `Calibrated probability` without calibration support | `Empirical estimate. Calibration unavailable.` |
| `Tail risk` without aggregate support | `Potential high-impact outcome; probabilistic support unavailable.` |
| `Probabilistic result` in Step 2 | `Prepared probabilistic artifact set` or `prepared artifact summary` |

## 8. State-Ownership Principles

The following principles govern state placement:

1. Only real backend identities may become durable frontend identities.
2. Route-owned state is reserved for identifiers needed for refresh, direct re-entry, or safe history navigation.
3. Component-owned state is preferred for local selection state inside a screen.
4. The frontend must not synthesize placeholder `ensemble_id`, `run_id`, or `cluster_id` values.
5. The product must not promote future IDs into the URL before the backend can resolve them.

## 9. Field-Level Ownership Contract

| Field | Creation point | Current owner | Future durable owner | URL/history decision | MVP status |
| --- | --- | --- | --- | --- | --- |
| `mode` | User chooses in Step 2; backend echoes through prepared-artifact summary. | Step 2 component state while editing; Step 2 prepared summary for readback; Step 3 query-state for runtime handoff. | Read-only downstream metadata once later surfaces exist. | Route-owned only on Step 3 query-state. Not a history key. | Live now in Step 2 and the Step 3 shell. |
| `ensemble_id` | Backend storage create/list/detail APIs return it; Step 2 shell creation now forwards it. | Step 2 handoff state plus Step 3 query-state/readback for one stored ensemble browser. | Route-level owner for Step 3 resume/reload; history row metadata for future ensemble records. | Present only on Step 3 query-state today. Not in history. | Live now for the Step 3 probabilistic browser. |
| `run_id` | Backend storage run-list and run-detail APIs return it; Step 2 shell creation now forwards it. | Step 2 handoff state plus Step 3 selected-run/query-state for one stored ensemble browser. | Step 3 selected-run state; optional Step 4/5 context selection state. | Present only on Step 3 query-state today and updated when the user changes selected runs. Not a history primary key in MVP. | Live now for the Step 3 probabilistic browser. |
| `cluster_id` | Future clustering artifact. | No current frontend owner. | Step 4 selected scenario-family state and Step 5 chat-scope state. | Not URL-owned in MVP. Not a history primary key in MVP. | Deferred. |

## 10. Surface Placement Matrix

### Step 2: Environment Setup

Decision:

- Step 2 is the only screen that owns editable `mode`.
- Step 2 owns the probabilistic draft controls.
- Step 2 owns the prepared-artifact summary readback.

Field placement:

| Field | Ownership decision |
| --- | --- |
| `mode` | Editable and Step 2-local. The toggle belongs in Step 2 only. |
| `ensemble_id` | Step 2 may create and forward one backend-owned stored ensemble identifier when the user explicitly launches probabilistic Step 3, but it is not an editable Step 2 control. |
| `run_id` | Step 2 may forward one backend-owned initial selected-run identifier for Step 3, but it is not an editable Step 2 control. |
| `cluster_id` | Must not exist in Step 2. |

PM note:

- Step 2 is allowed to prepare the user for later probabilistic runtime work and to create one stored ensemble plus one initial selected run for Step 3, but it is not allowed to pretend that broader report or calibration support already exists.

### Step 3: Run Simulation

Current truth:

- Step 3 now has a truthful probabilistic ensemble browser keyed by `simulation_id` plus query-state `mode`, `ensembleId`, and `runId`.

MVP decision:

- preserve the current strict-handoff browser and its deterministic selected-run semantics
- do not silently guess another stored run when `ensemble_id` or `run_id` is missing
- once the handoff exists, allow deterministic selected-run fallback when the chosen run disappears
- do not imply Step 4 support

Current ownership:

| Field | Ownership decision |
| --- | --- |
| `mode` | Read-only route/query metadata. Never editable here. |
| `ensemble_id` | Route-owned identity for the current probabilistic browser reload path. |
| `run_id` | Route-owned and component-updated selection state for the current probabilistic browser. |
| `cluster_id` | Out of Step 3 MVP scope. Do not place here. |

### Step 4: Report Generation

Current truth:

- Step 4 is still keyed by `report_id` and keeps the legacy report-log/section-streaming flow, but it can now recover `mode`, `ensemble_id`, and `run_id` from saved report metadata and render an additive observed report-context card beside the legacy report body.

MVP decision:

- preserve the current `report_id`-rooted route
- Step 3 may show read-only observed analytics cards backed directly by persisted ensemble artifacts, and Step 4 may now show additive observed report-context cards backed by saved report metadata, but those cards must stay clearly separate from the generated markdown report body until the report renderer itself becomes ensemble-aware

Deferred target ownership:

| Field | Ownership decision |
| --- | --- |
| `mode` | Read-only provenance badge or header metadata after probabilistic report context exists. |
| `ensemble_id` | Resolved from report metadata or report context; not user-editable. `report_id` remains the canonical route identity. |
| `run_id` | Optional in-view selection for a representative run card or drilldown. Not route-owned in MVP. |
| `cluster_id` | Optional in-view selection for scenario family browsing. Not route-owned in MVP. |

Reason:

- Step 4 already has a durable report identity. Duplicating that with route-owned run or cluster state would add URL churn before the report context stabilizes.

### Step 5: Deep Interaction

Current truth:

- Step 5 remains report/simulation scoped and has no grounded run or cluster semantics today, but it now preserves the probabilistic handoff metadata, lets the report-agent lane use the exact saved report plus saved probabilistic context, and still keeps interviews and surveys explicitly legacy-scoped.

MVP decision:

- keep Step 5 on the existing `report_id` route
- allow the report-agent lane to reuse saved report context, because `report_id` is now the durable probabilistic scope carrier for Step 4 and Step 5
- do not add fake scope chips for ensemble, family, or representative run before run/cluster chat grounding exists

Deferred target ownership:

| Field | Ownership decision |
| --- | --- |
| `mode` | Read-only provenance metadata from report context. |
| `ensemble_id` | Resolved from report context, not edited here. |
| `run_id` | Component-owned chat scope selection when representative-run grounding exists. |
| `cluster_id` | Component-owned chat scope selection when scenario-family grounding exists. |

### History

Current truth:

- history is simulation/report centric
- Step 4 and Step 5 can reopen from a saved report today
- Step 3 still cannot be replayed from history today

MVP decision:

- keep history on the current simulation/report record model
- do not add compare mode
- do not introduce probabilistic history entries until backend ensemble summaries exist

Deferred target ownership:

| Field | Ownership decision |
| --- | --- |
| `mode` | Optional record badge only. Not a history key. |
| `ensemble_id` | Future history row metadata for probabilistic records. |
| `run_id` | Not a history row identity in MVP. Possible later drilldown metadata only if product value is proven. |
| `cluster_id` | Not a history row identity in MVP. |

### Routing

Current truth:

- current routes are `/simulation/:simulationId`, `/simulation/:simulationId/start`, `/report/:reportId`, and `/interaction/:reportId`

MVP routing decision:

- keep the existing route table unchanged
- do not add query-param ownership for `mode`, `ensemble_id`, `run_id`, or `cluster_id`
- do not add a compare route

Deferred routing contract:

- the first real Step 3 probabilistic route must give `ensemble_id` first-class route ownership because Step 3 needs reload-safe monitor identity
- Step 4 and Step 5 should remain canonically rooted in `report_id`, with `ensemble_id` resolved through report metadata/context
- `run_id` and `cluster_id` remain off-URL in MVP and early rollout; they are view selections, not routing primitives

## 11. Unsupported and Thin-Evidence States

The frontend needs two distinct caution states.

### Unsupported or unavailable

Meaning:

- the release does not support the capability, or the required artifact is absent

Approved patterns:

- `Probabilistic reporting is not available in this release yet.`
- `Calibration unavailable. Showing no calibrated probability.`
- `This answer is not supported by the current evidence.`
- `This view remains on the legacy single-run path.`

Behavior:

- hide or disable the unsupported probabilistic surface
- show an explicit reason when possible
- never substitute a placeholder percentage, placeholder badge, or empty shell that implies the capability is almost there

### Thin evidence

Meaning:

- the product has some evidence, but it is not strong enough for confident interpretation

Approved patterns once supported:

- `Thin evidence: treat this as directional rather than stable.`
- `Thin evidence: the estimate is based on limited or degraded run-family support.`

Behavior:

- keep the value visible if the backend says the evidence is real but weak
- pair the value with a caution label
- never convert a thin-evidence state into unsupported if a valid, weak estimate actually exists

## 12. Explicit Non-Goals

This contract does not approve the following in the current release:

- probabilistic Step 3 widgets without ensemble runtime
- probabilistic Step 4 cards without report context artifacts
- probabilistic Step 5 scope selectors without chat grounding
- history replay for Step 3 or Step 5
- calibrated probability copy before calibration artifacts exist
- compare routing in MVP

## 13. Assumptions

- the H0 baseline, H1 prepare-path contract, status audit, and frontend task register dated 2026-03-08 are the current source of truth
- Step 2 capability discovery remains the only live probabilistic backend surface consumed by the frontend
- backend storage endpoints now return `ensemble_id` and `run_id`, but the frontend does not consume them yet
- `report_id` remains the canonical durable identity for Step 4 and Step 5 until a future contract explicitly changes that

## 14. Evidence Base

This contract is grounded in:

- `docs/plans/2026-03-08-stochastic-probabilistic-domain-and-probability-contract.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-status-audit.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-h0-contract-baseline.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-h1-prepare-path-contract.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-frontend-task-register.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-frontend-workstreams.md`
- `docs/plans/2026-03-08-stochastic-probabilistic-api-contracts.md`
- `frontend/src/components/Step2EnvSetup.vue`
- `frontend/src/components/Step3Simulation.vue`
- `frontend/src/components/Step4Report.vue`
- `frontend/src/components/Step5Interaction.vue`
- `frontend/src/components/HistoryDatabase.vue`
- `frontend/src/views/SimulationView.vue`
- `frontend/src/views/SimulationRunView.vue`
- `frontend/src/views/ReportView.vue`
- `frontend/src/views/InteractionView.vue`
- `frontend/src/router/index.js`
