# Stochastic Probabilistic Simulation Extension Design

**Date:** 2026-03-08

**Scope:** Extend the existing MiroFishES graph-plus-agent simulation product with explicit stochastic and probabilistic forecasting capabilities without replacing the current pipeline.

**Audience:** Engineers, product owners, and researchers working on the MiroFishES backend and frontend.

## 1. Repo-grounded current state

This design is based on the current codebase, not on an imagined platform.

The current system already has a coherent end-to-end workflow:

1. Documents are uploaded and analyzed to generate an ontology through `/api/graph/ontology/generate` in `backend/app/api/graph.py`.
2. A Zep graph is built and persisted by `/api/graph/build` plus `GraphBuilderService` in `backend/app/services/graph_builder.py`.
3. A simulation wrapper is created by `/api/simulation/create` in `backend/app/api/simulation.py`.
4. `/api/simulation/prepare` reads filtered entities, generates OASIS profiles, generates `simulation_config.json`, and writes simulation artifacts under `uploads/simulations/<simulation_id>/`.
5. `/api/simulation/start` launches a single run via `backend/scripts/run_parallel_simulation.py` or its single-platform siblings.
6. The live run is monitored by `SimulationRunner`, which tails `twitter/actions.jsonl` and `reddit/actions.jsonl`.
7. `/api/report/generate` produces one report per simulation through `ReportAgent`, and the frontend renders that report across Step 4 and Step 5.

Important observed properties of the current implementation:

- The system is already graph-backed and stateful.
- The system already serializes profiles, config, actions, run status, and report artifacts.
- The system currently assumes one prepared simulation maps to one run and one report.
- The current runtime already contains hidden randomness:
  - LLM-driven config generation.
  - LLM-driven profile generation.
  - `random.uniform`, `random.random`, and `random.sample` in the runtime scripts.
  - OASIS agent action generation through `LLMAction()`.
- That randomness is not explicit, versioned, or reproducible.

This means MiroFishES is already stochastic in practice, but not probabilistic in architecture.

## 2. Problem statement

MiroFishES currently produces a single generated simulation configuration, runs one trajectory, and then writes one report. That is suitable for narrative exploration, but it does not support decision-grade probabilistic forecasting because it lacks:

- explicit uncertainty objects,
- repeatable seeded execution,
- multi-run orchestration,
- run lineage,
- scenario aggregation,
- sensitivity analysis,
- calibration,
- and clear semantics for what any reported probability is over.

The core design problem is therefore:

How do we convert MiroFishES from a single-trajectory simulator into a probabilistic ensemble simulator while preserving its existing strengths in graph-derived worldbuilding, agent simulation, natural-language interaction, and report generation?

## 3. Non-negotiable design principles

### 3.1 Preserve the current product shape

The extension must fit the current product:

- uploaded documents,
- ontology generation,
- graph build,
- entity extraction,
- profile generation,
- simulation configuration,
- OASIS execution,
- report generation,
- interactive report interrogation.

This should remain the backbone.

### 3.2 Make uncertainty explicit, not implicit

A future probability must be derived from one of the following:

- empirical frequency over a run family,
- a fitted calibration transform,
- or a defined probabilistic submodel.

The system must not fabricate probability language in prose when there is no explicit basis.

### 3.3 Keep the world-construction layer mostly deterministic

For a fixed project snapshot, the following should be treated as deterministic by default:

- uploaded source files,
- extracted text,
- the approved ontology snapshot,
- the graph snapshot used for a simulation family,
- the chosen entity set,
- the prepared profile set,
- the baseline simulation config,
- the outcome metric definitions,
- and the aggregation rules.

This is necessary for provenance, reproducibility, and user trust.

### 3.4 Introduce stochasticity only at named entry points

Stochasticity should enter through explicit mechanisms:

- parameter sampling,
- runtime agent activation sampling,
- exogenous event sampling,
- branch assumption sampling,
- and optional targeted latent-state sampling.

### 3.5 Separate exploration from decision-grade forecasting

The product should support two modes:

- exploratory mode: broad narrative ideation, rich scenario spread, lighter controls;
- forecasting mode: narrower, versioned, seeded, metrics-first, with calibrated or clearly marked uncalibrated probabilities.

### 3.6 Version everything that affects results

Every probabilistic artifact must be tied to:

- project snapshot,
- graph snapshot or graph fetch time,
- prepared profile version,
- base config version,
- uncertainty spec version,
- outcome metric version,
- runtime version,
- and seed policy.

## 4. What should be deterministic, stochastic, and learned

### 4.1 Deterministic

- Project creation and file persistence.
- Extracted text for a given project version.
- Approved ontology definition.
- Graph snapshot selected for a run family.
- Entity filtering rules.
- Outcome metric definitions and thresholds.
- Aggregation rules.
- Report templates and rendering logic.
- Seed derivation policy.
- Scenario clustering algorithm choice and parameters.

### 4.2 Stochastic

- Which uncertain parameter values are sampled for a run.
- Which agents activate in a round.
- How many agents activate in a round.
- Whether uncertain exogenous events occur.
- Exact timing of uncertain events.
- Optional narrative variant choice.
- Optional uncertain poster selection when multiple agents fit an initial event.
- Agent-level action generation variance during runtime.

### 4.3 Learned or inferred

- Distribution parameters derived from historical data.
- Confidence values inferred from document extraction quality.
- Calibration transforms fitted against historical forecast outcomes.
- Targeted world-level latent regime models, if added later.
- Event hazard priors learned from prior simulations or observed cases.

## 5. Candidate architectures compared

| Architecture | What it means in MiroFishES | Strengths | Weaknesses | Fit |
| --- | --- | --- | --- | --- |
| Pure Monte Carlo over current simulator | Sample config fields, run many seeded OASIS runs, aggregate outcomes | Cheapest to ship, preserves current engine, easy to explain | Limited structure for world-level dependencies, uncalibrated until later | High |
| Monolithic Bayesian network rewrite | Replace major parts of graph-plus-agent execution with one probabilistic graphical model | Strong formal semantics | Poor fit for rich open-ended agent behavior, large rewrite | Low |
| Hybrid deterministic world build + stochastic execution + aggregation + calibration | Keep current pipeline, add explicit uncertainty layer, seeded ensembles, metrics, clustering, calibration | Best balance of fit, rigor, interpretability, incremental rollout | Requires new orchestration and artifact model | Very high |
| Scenario trees as primary engine | Encode futures as manually or LLM-generated branches instead of sampled runs | Interpretable branching | Hard to scale, brittle, poor coverage of continuous uncertainty | Medium |
| Calibration-only overlay | Keep single-run simulator and calibrate report answers afterward | Cheap surface improvement | Does not solve missing ensemble semantics or run variance | Low |
| System dynamics or diffusion models as replacement | Replace agent runtime with aggregate math models | Faster for some domains | Loses current strength in agentic interaction and world exploration | Low |
| Targeted Bayesian world-state module layered on top of ensembles | Add small world-level latent models for a few variables only | Good later-stage upgrade | Research-heavy, needs disciplined scope | Medium now, high later |

## 6. Recommended target architecture

The recommended architecture for MiroFishES is:

**Deterministic world construction + explicit uncertainty specification + seeded ensemble execution + structured aggregation and calibration.**

This architecture has six layers.

### Layer 1: Project and graph snapshot

Purpose:

- lock the provenance anchor for the simulation family.

Input:

- uploaded files,
- extracted text,
- ontology,
- graph_id,
- filtered entities.

Output:

- a stable prepared snapshot that all probabilistic runs reference.

### Layer 2: Prepared simulation baseline

Purpose:

- preserve the current profile-generation and config-generation workflow while capturing a canonical baseline.

Output artifacts:

- `prepared_snapshot.json`
- `reddit_profiles.json`
- `twitter_profiles.csv`
- `simulation_config.base.json`

The baseline config remains scalar and concrete.

### Layer 3: Uncertainty model

Purpose:

- represent what is uncertain, why it is uncertain, and how it should be sampled.

Output artifacts:

- `uncertainty_spec.json`
- `outcome_spec.json`
- `ensemble_spec.json`

This layer is the new heart of the probabilistic extension.

### Layer 4: Run resolver

Purpose:

- turn one baseline config plus one uncertainty spec into one resolved run config.

Output per run:

- `resolved_config.json`
- `run_manifest.json`

This is where probabilities become actual sampled values.

### Layer 5: Stochastic execution

Purpose:

- run the existing OASIS-based runtime with deterministic resolved config plus a per-run seed manifest.

Output per run:

- `run_state.json`
- `simulation.log`
- `twitter/actions.jsonl`
- `reddit/actions.jsonl`
- per-platform SQLite databases
- `metrics.json`

### Layer 6: Aggregation, calibration, and reporting

Purpose:

- convert many runs into empirical probabilities, scenario clusters, driver rankings, and explainable outputs.

Output per ensemble:

- `aggregate_summary.json`
- `scenario_clusters.json`
- `sensitivity.json`
- `calibration.json`
- `probabilistic_report_context.json`

This is what makes the extension useful rather than merely stochastic.

## 7. Recommended implementation stance for the current codebase

### 7.1 Do not replace the current single-run path first

The lowest-risk path is to add a parallel probabilistic path while preserving the current flow:

- existing `simulation_id` single-run behavior continues to work,
- new ensemble APIs and artifacts are introduced beside it,
- the frontend opts into the ensemble path only when probabilistic mode is enabled.

### 7.2 Treat the current single run as the baseline primitive

MiroFishES already knows how to:

- prepare one simulation,
- launch one runtime,
- read one action stream,
- generate one report.

The probabilistic extension should reuse that primitive by adding:

- run family orchestration,
- resolved per-run config generation,
- per-run storage,
- and cross-run aggregation.

### 7.3 Fix hidden randomness before claiming forecast rigor

The first technical cleanup step is not Bayesian modeling. It is:

- adding explicit seeds,
- separating scalar config from sampled config,
- and making randomness discoverable in artifacts.

## 8. Exact new abstractions

The following abstractions should be added explicitly.

### 8.1 `RandomVariableSpec`

Represents one uncertain scalar or categorical field.

Suggested shape:

```json
{
  "id": "agent_12.activity_level",
  "distribution": "beta",
  "parameters": { "alpha": 5.0, "beta": 3.0 },
  "support": { "min": 0.0, "max": 1.0 },
  "source": "llm_prior",
  "confidence": 0.55,
  "description": "Probability that agent 12 is active in an eligible round",
  "frozen": false
}
```

### 8.2 `UncertaintySpec`

Represents the full uncertainty model for one prepared simulation.

Suggested fields:

- `spec_version`
- `probabilistic_mode`
- `random_variables`
- `event_hazards`
- `world_variables`
- `agent_variables`
- `runtime_variance_controls`
- `sampling_defaults`
- `provenance`

### 8.3 `EnsembleSpec`

Represents how many runs to execute and how to structure them.

Suggested fields:

- `ensemble_id`
- `run_count`
- `mode`: `replicate | full_resample | perturbation | counterfactual | branch`
- `root_seed`
- `seed_policy`
- `max_parallel_runs`
- `branch_dimensions`
- `perturbation_dimensions`
- `paired_counterfactuals`

### 8.4 `RunManifest`

Represents one concrete run instance.

Suggested fields:

- `run_id`
- `simulation_id`
- `ensemble_id`
- `parent_run_id`
- `run_type`
- `root_seed`
- `platform_seeds`
- `sampled_variables`
- `resolved_config_path`
- `started_at`
- `completed_at`
- `runtime_version`
- `status`

### 8.5 `OutcomeMetricDefinition`

Represents one metric or event whose probability will be reported.

Examples:

- probability of narrative A dominating by final round,
- probability of cascade size exceeding threshold,
- time to first official response,
- total action volume by end of horizon,
- polarization index at final state.

Suggested fields:

- `metric_id`
- `display_name`
- `description`
- `type`: `binary | categorical | continuous | count`
- `extractor`
- `thresholds`
- `aggregation`
- `probability_queries`

### 8.6 `ScenarioCluster`

Represents one scenario family found after aggregation.

Suggested fields:

- `cluster_id`
- `probability_mass`
- `prototype_run_id`
- `member_run_ids`
- `summary`
- `distinguishing_metrics`
- `dominant_agents`
- `leading_indicators`

### 8.7 `CalibrationArtifact`

Represents fitted calibration outputs for recurring targets.

Suggested fields:

- `target_id`
- `training_window`
- `method`
- `pre_calibration_score`
- `post_calibration_score`
- `model_path`
- `calibration_curve_points`

## 9. Distribution types to implement first

The system should not expose an unbounded zoo of distributions immediately. The initial supported set should be purpose-built.

### 9.1 Phase 1 distributions

- `fixed`
  - Use for deterministic fields.
- `categorical`
  - Use for stance, event type, narrative variant, platform regime.
- `beta`
  - Use for bounded probabilities in `[0, 1]`, such as `activity_level`, `echo_chamber_strength`, and resharing likelihoods.
- `truncated_normal`
  - Use for bounded continuous variables such as `sentiment_bias` and bounded delay multipliers.
- `lognormal`
  - Use for heavy-tailed positive variables such as `influence_weight`.
- `poisson`
  - Use for count-like rate variables such as initial event arrivals and optional posts-per-hour variants.
- `uniform`
  - Use as a simple fallback when only ranges are known.

### 9.2 Phase 2 distributions

- `empirical`
  - Use when enough historical fit data exist.
- `negative_binomial`
  - Use for overdispersed count processes.
- `bernoulli_hazard`
  - Use for event occurrence within a time window.
- `mixture`
  - Use for multimodal world-state variables.

## 10. Where uncertainty should live in the existing pipeline

### 10.1 First extension point: simulation preparation and config generation

This is the best initial insertion point because the config schema already contains the knobs that should become uncertain:

- `time_config`
- `agent_configs`
- `event_config`
- `twitter_config`
- `reddit_config`

The current data model lives in `backend/app/services/simulation_config_generator.py`.

This file should be extended so a prepared simulation can emit:

- a baseline scalar config,
- and optionally a probabilistic extension spec beside it.

This solves the immediate problem that uncertainty has nowhere formal to live.

### 10.2 Second extension point: runtime orchestration

`SimulationRunner` and the runtime scripts currently key everything by `simulation_id`.

That must change for ensembles because:

- one prepared simulation must be able to launch many member runs,
- many member runs must coexist without log collisions,
- and each run must keep its own seed and sampled values.

### 10.3 Third extension point: post-run metrics extraction

`SimulationRunner` already exposes:

- action history,
- timeline,
- agent stats,
- per-round action counts.

That telemetry should be standardized into reusable per-run metrics.

This solves the problem that current reports are narrative-first and lack structured outcome distributions.

### 10.4 Fourth extension point: report generation

`ReportAgent` should not infer probabilities from one run.

It should instead consume:

- aggregate metrics,
- scenario clusters,
- sensitivity summaries,
- and calibration artifacts.

This solves the problem of pseudo-quantified prose.

### 10.5 Later extension point: graph confidence metadata

The graph path can later carry uncertainty metadata on nodes and edges, but it should not be the first step.

Why:

- graph uncertainty is valuable,
- but if the runtime and report layers cannot represent or aggregate uncertainty yet, graph confidence will not materially improve end-user forecasts.

## 11. Detailed pipeline changes

### 11.1 Ontology generation

Current state:

- Ontology is generated by LLM and stored as plain entity and edge type definitions.

Recommended change:

- Keep ontology deterministic for Phase 1.
- Add optional type-level uncertainty metadata only in Phase 2.

New optional ontology fields for later:

- `confidence_interpretation`
- `default_uncertainty_profile`
- `allowed_distribution_types`
- `evidence_requirements`

Why not first:

- ontology uncertainty is upstream and abstract;
- runtime uncertainty controls are more immediately useful and easier to validate.

### 11.2 Graph construction and graph read path

Current state:

- Zep stores nodes and edges with attributes and temporal metadata.
- Read helpers inconsistently preserve all relationship attributes.

Recommended changes:

- Preserve uncertainty-related edge and node attributes end-to-end.
- Add a post-build enrichment stage that can write:
  - `extraction_confidence`
  - `belief_strength`
  - `evidence_count`
  - `contradiction_score`
  - `confidence_source`

Problem solved:

- later probabilistic modules can distinguish confident graph facts from weak inferred relationships.

### 11.3 Profile generation

Current state:

- Profile generation contains hidden randomness and rule-based random fallbacks.

Recommended changes:

- Split profiles into:
  - deterministic baseline profile fields,
  - optional uncertain agent trait fields.
- Add seed plumbing to profile generation if reproducible preparation is required.
- Add optional trait distributions for:
  - `baseline_activity_level`
  - `influence_weight`
  - `response_delay`
  - `sentiment_bias`
  - `stance_transition`

Important constraint:

- The visible persona text should not be re-randomized per run.
- Narrative persona remains the stable baseline identity.
- Behavior parameters are what vary per run.

Problem solved:

- preserves agent identity while allowing behavior uncertainty.

### 11.4 Simulation config generation

Current state:

- config generation is scalar and LLM-driven.

Recommended changes:

- Generate two artifacts:
  - `simulation_config.base.json`
  - `uncertainty_spec.json`

Initial uncertain fields to support:

- `time_config.agents_per_hour_min`
- `time_config.agents_per_hour_max`
- `time_config.peak_activity_multiplier`
- `agent_configs[*].activity_level`
- `agent_configs[*].posts_per_hour`
- `agent_configs[*].comments_per_hour`
- `agent_configs[*].response_delay_min`
- `agent_configs[*].response_delay_max`
- `agent_configs[*].sentiment_bias`
- `agent_configs[*].influence_weight`
- `event_config.initial_posts[*].poster_agent_id`
- `event_config.scheduled_events`
- `twitter_config.viral_threshold`
- `reddit_config.viral_threshold`
- `twitter_config.echo_chamber_strength`
- `reddit_config.echo_chamber_strength`

Problem solved:

- uncertainty is represented where the current system already makes consequential assumptions.

### 11.5 Runtime loop

Current state:

- runtime samples agent activation using module-global `random`.

Recommended changes:

- add `--run-id`
- add `--seed`
- add `--run-dir`
- use seeded RNG objects instead of module-global random state
- separate platform RNG streams in parallel mode
- write per-run metrics at end of execution

Optional Phase 2 additions:

- exogenous event injector
- scheduled event hazard execution
- optional mid-run forced interventions

Problem solved:

- run variance becomes explicit and reproducible.

### 11.6 Post-simulation analysis

Current state:

- only single-run telemetry is available.

Recommended changes:

- create a new analysis layer that extracts standardized outcome metrics from every run.

Example metrics:

- `final_total_actions`
- `time_to_first_official_post`
- `platform_action_share_delta`
- `max_round_action_spike`
- `dominant_topic_by_final_round`
- `top_3_agents_by_action_count`
- `narrative_polarization_index`
- `cross_platform_divergence_score`

Problem solved:

- reports can talk about distributions over metrics instead of narrativizing one trace.

### 11.7 Reporting and interaction

Current state:

- one report per simulation, section-based, driven by `ReportAgent`.

Recommended changes:

- add a probabilistic report context artifact and new report sections:
  - outcome distribution,
  - scenario families,
  - key drivers,
  - tail risks,
  - early indicators,
  - calibration status.

Important rule:

- any exemplar narrative quoted in a probabilistic report must be tied to a named run or cluster prototype.

Problem solved:

- avoids contradiction between one agent narrative and a cross-run forecast summary.

## 12. Internal schema changes

### 12.1 Prepared simulation root

Suggested directory layout:

```text
uploads/simulations/<simulation_id>/
  state.json
  prepared_snapshot.json
  simulation_config.base.json
  uncertainty_spec.json
  outcome_spec.json
  ensemble/
    ensemble_<ensemble_id>/
      ensemble_state.json
      ensemble_spec.json
      aggregate_summary.json
      scenario_clusters.json
      sensitivity.json
      calibration.json
      runs/
        run_<run_id>/
          run_manifest.json
          resolved_config.json
          run_state.json
          simulation.log
          metrics.json
          twitter/actions.jsonl
          reddit/actions.jsonl
```

### 12.2 `prepared_snapshot.json`

Suggested contents:

- `project_id`
- `simulation_id`
- `graph_id`
- `prepared_at`
- `project_snapshot`
- `entity_summary`
- `profile_summary`
- `base_config_hash`
- `graph_fetch_timestamp`

### 12.3 `uncertainty_spec.json`

Suggested contents:

- `spec_version`
- `mode`
- `random_variables`
- `event_hazards`
- `seed_policy`
- `sampling_policy`
- `notes`

### 12.4 `resolved_config.json`

This should look like today's `simulation_config.json`, but entirely concrete.

Additional metadata:

- `run_id`
- `ensemble_id`
- `root_seed`
- `sample_seed`
- `sampled_values`
- `resolved_at`

### 12.5 `metrics.json`

Suggested contents:

- `run_id`
- `simulation_id`
- `ensemble_id`
- `metric_values`
- `event_flags`
- `timeline_summaries`
- `top_agents`
- `top_topics`
- `quality_checks`

## 13. Multiple run types

### 13.1 Replicate runs

Definition:

- same resolved parameter values,
- different runtime seeds.

Use:

- measure intrinsic process variance.

Probability is over:

- runtime stochasticity conditional on one resolved world.

### 13.2 Full-resample runs

Definition:

- resample uncertain parameters and runtime noise.

Use:

- default forecast ensemble.

Probability is over:

- the uncertainty model plus runtime noise.

### 13.3 Perturbation runs

Definition:

- vary one or a small set of parameters systematically.

Use:

- sensitivity analysis and driver ranking.

Probability is over:

- a controlled alternate assumption set, not the baseline forecast distribution.

### 13.4 Counterfactual runs

Definition:

- hold the baseline family fixed, then deterministically impose an intervention.

Examples:

- remove one high-influence agent,
- inject a correction event at hour 6,
- increase viral threshold by 20 percent.

### 13.5 Branch runs

Phase 1 definition:

- pre-run branch from the same prepared simulation with one changed assumption set.

Phase 3 definition:

- true mid-run branch from a serialized checkpoint, if OASIS state serialization proves feasible.

## 14. Runtime orchestration design

### 14.1 New service responsibilities

Introduce the following services:

- `EnsembleManager`
  - creates ensembles, run manifests, directories, and high-level status.
- `UncertaintyResolver`
  - samples or freezes uncertain fields into a concrete run config.
- `OutcomeExtractor`
  - computes per-run metrics from action logs and timelines.
- `ScenarioClusterer`
  - groups runs into scenario families.
- `SensitivityAnalyzer`
  - ranks drivers and perturbation effects.
- `CalibrationManager`
  - stores and applies fitted calibration artifacts for recurring targets.

### 14.2 Seed policy

Use a hierarchical seed structure:

- `root_seed`
- `config_seed`
- `event_seed`
- `twitter_seed`
- `reddit_seed`
- `analysis_seed`

The platform runtime should never use Python's module-global random state directly in probabilistic mode.

### 14.3 Run status model

Current issue:

- `SimulationRunner` is keyed only by `simulation_id`.

Required change:

- key run state, processes, monitor threads, and cleanup by `run_id`.

This is mandatory for concurrent ensemble execution.

### 14.4 Backward compatibility

Legacy mode:

- `POST /api/simulation/start` continues to launch one run for one `simulation_id`.

Probabilistic mode:

- new ensemble endpoints operate beside the old path.

This avoids destabilizing the current product while the extension is being proven.

## 15. UI and report design

### 15.1 Step 2: environment setup

Extend `Step2EnvSetup.vue` with a new section:

- probabilistic mode toggle,
- uncertainty profile preview,
- ensemble defaults,
- outcome metric selection.

Show:

- which fields are deterministic,
- which are uncertain,
- which are learned,
- and the provenance of each uncertainty object.

### 15.2 Step 3: live run monitor

In probabilistic mode, Step 3 should show ensemble progress rather than one timeline only.

Add:

- completed runs count,
- running runs count,
- failed runs count,
- convergence panel for key metrics,
- early cluster emergence,
- and a way to inspect one selected member run.

### 15.3 Step 4: probabilistic report

Add new first-class report cards or sections:

- top outcomes with empirical probabilities,
- probability distributions with quantiles,
- scenario families with probability mass,
- key drivers and sensitivities,
- most likely vs tail-risk futures,
- early indicators to monitor in the real world,
- calibration status,
- evidence quality and thin-evidence warnings.

### 15.4 Step 5: interaction

The report agent should be able to answer:

- top outcome probability questions,
- scenario cluster questions,
- driver questions,
- seed stability questions,
- intervention effect questions.

When answering narrative questions, it should say whether it is referring to:

- the ensemble as a whole,
- a specific cluster,
- or a specific representative run.

## 16. Evaluation and calibration framework

### 16.1 What can be evaluated immediately

- run stability across seeds,
- robustness across perturbations,
- internal consistency checks,
- clustering stability,
- evidence coverage,
- extraction quality,
- runtime failure rate.

### 16.2 What requires historical data

- calibration of event probabilities,
- Brier score and log loss for binary or categorical forecast targets,
- calibration curves and reliability diagrams,
- CRPS for continuous forecasts,
- post-hoc calibrated probability layers.

### 16.3 What should be calibrated against what

Calibration should be done only for recurring forecast targets with observed real outcomes.

Examples:

- predicted probability that official response occurs within 24 hours,
- predicted probability that narrative X dominates by day 3,
- predicted probability that action count exceeds threshold,
- predicted probability that one intervention reduces cascade size by at least N percent.

Each such target needs:

- a historical corpus of prior projects or benchmark scenarios,
- observed realized outcomes,
- uncalibrated predicted probabilities,
- and fitted calibration transforms.

### 16.4 Report language rules

- If a target is uncalibrated, the report must say it is an uncalibrated ensemble estimate.
- If a target is calibrated, the report must cite the calibration version.
- If a target comes from a small sample ensemble, the report must show the run count.

## 17. Risks, anti-patterns, and failure modes

### 17.1 Pseudo-quantification

Risk:

- polished numbers without a formal basis.

Mitigation:

- probabilities must come from empirical frequencies, explicit submodels, or calibration artifacts only.

### 17.2 False precision

Risk:

- reporting 63.2 percent when the system has weak evidence.

Mitigation:

- round display values,
- expose run counts,
- show uncertainty bands and evidence quality.

### 17.3 Compounding uncertainty

Risk:

- uncertain ontology, uncertain graph, uncertain profiles, uncertain config, uncertain runtime, uncertain report all piling together with no control.

Mitigation:

- phase the system,
- only turn on a few uncertainty sources at first,
- and measure contribution of each source separately.

### 17.4 Runtime explosion

Risk:

- too many runs, too many agents, too many LLM calls.

Mitigation:

- cap run counts,
- add max concurrency,
- cache prepared artifacts,
- define cheap screening ensembles and expensive high-fidelity ensembles.

### 17.5 Narrative-probability contradiction

Risk:

- one vivid run dominates the report even if it is low-probability.

Mitigation:

- cluster runs,
- use prototype runs,
- clearly label exemplars as representatives, not dominant outcomes.

### 17.6 Hidden stochasticity

Risk:

- a claimed seeded run is still affected by uncontrolled randomness in profile generation or LLM behavior.

Mitigation:

- version and disclose which parts are seed-controlled and which are not.

## 18. Phased roadmap

### 18.1 Minimum viable probabilistic extension

Goal:

- turn one prepared simulation into a seeded run family with empirical outcome distributions.

Ship:

- baseline config plus uncertainty spec,
- ensemble and run manifests,
- per-run directories,
- seeded runtime selection,
- metrics extraction,
- aggregate summary,
- scenario clustering,
- basic probabilistic report cards.

Do not ship yet:

- graph confidence enrichment,
- calibration claims,
- targeted Bayesian world-state models,
- mid-run checkpoint branching.

### 18.2 Medium-complexity extension

Goal:

- add uncertainty-aware controls and driver analysis suitable for serious scenario work.

Ship:

- graph/node/edge confidence propagation,
- probabilistic scheduled events,
- parameter perturbation campaigns,
- sensitivity analysis,
- richer Step 3 and Step 4 ensemble UIs,
- report agent support for probabilistic artifacts.

### 18.3 Full-vision extension

Goal:

- make MiroFishES a trustworthy probabilistic simulation and forecasting system.

Ship:

- recurring target calibration,
- versioned calibration artifacts,
- targeted world-state latent models,
- sequential updating from observed real-world signals,
- optional checkpoint branching if technically feasible,
- cross-project benchmark and backtest workflows.

## 19. Single best path forward

The best architecture for MiroFishES specifically is:

**Keep graph building and world preparation stable, make execution explicitly stochastic, and make reporting empirical and calibration-aware.**

That means:

- do not replace the graph or OASIS stack,
- do not rewrite the system as one giant Bayesian network,
- do not start with ontology-level uncertainty,
- do not report probabilities from single runs,
- and do not delay on research-heavy submodels before fixing seeds, run manifests, and aggregation.

Instead:

1. Add a probabilistic schema beside the current config.
2. Add seeded run-family orchestration and per-run storage.
3. Extract standardized per-run metrics.
4. Aggregate into scenario clusters and outcome distributions.
5. Extend the report and interaction layers to consume those artifacts.
6. Add calibration only when recurring targets and benchmark data exist.

## 20. Top 5 highest-leverage changes

1. Add `uncertainty_spec.json`, `ensemble_spec.json`, `resolved_config.json`, and `run_manifest.json`.
2. Make runtime randomness seedable and run-scoped instead of `simulation_id`-scoped.
3. Add a standardized per-run outcome extraction layer.
4. Add aggregate scenario clustering and sensitivity summaries before changing the report language.
5. Add probabilistic report artifacts and UI cards that clearly distinguish empirical ensemble probabilities from narrative examples.

## 21. Minimum viable probabilistic extension

The minimum viable probabilistic extension is:

- one prepared simulation,
- one baseline scalar config,
- one uncertainty spec covering a small set of high-leverage fields,
- N seeded member runs,
- per-run resolved configs and manifests,
- cross-run metrics aggregation,
- top outcome probabilities,
- scenario family summaries,
- and explicit disclosure that the outputs are empirical ensemble estimates.

## 22. Most dangerous design mistakes to avoid

- Treating current hidden randomness as if it were already a probabilistic model.
- Reporting probabilities from one run or from LLM prose.
- Making ontology, graph, profiles, config, and runtime all uncertain on day one.
- Keeping run storage keyed only by `simulation_id`.
- Allowing one vivid exemplar run to masquerade as the most likely future.
- Claiming calibration before benchmark targets and observed outcomes exist.
- Adding a monolithic probabilistic graphical model before the system has good run manifests, metrics, and evaluation discipline.
