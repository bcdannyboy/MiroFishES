# Strategic Product-Direction Memo: Scenario Forecasting In 2026

Date: March 29, 2026

## Executive Summary

For a scenario-forecasting platform in 2026, credibility comes from operational forecasting discipline, not from adding more generative surface area. The strongest external platforms and benchmarks now converge on a small set of non-optional capabilities: explicit forecast questions with rigorous resolution criteria, evidence-backed and inferable grounding, rolling scoring and calibration across question types, and continuously updated forecasts with visible support and freshness status. This repo already has the beginnings of an artifact-first forecasting control plane, but it still treats forecasting as an additive layer around a legacy simulation/report core. That is the main architectural constraint.

The product direction for MiroFishES should therefore be:

1. move from "simulation with probabilistic sidecars" to a forecast-native kernel
2. make evidence and evaluation first-class system primitives
3. keep clusters, compare, and chat as consumers of forecast truth rather than as the center of the product

## Repo-Local Starting Point

The repo truth is internally consistent:

- the legacy graph-build -> simulation -> report core still defines the main flow
- forecast artifacts are additive and bounded
- grounding is durable but limited
- scenario families are empirical
- sensitivity is observational, not interventional
- calibration is binary-only and artifact-gated
- compare is bounded
- live operator proof is incomplete

That means the core strategic question is not "what new forecast UI should exist?" It is "what architectural changes would make this platform believable to a serious user in 2026?"

## What A Materially Stronger Platform Would Prioritize

### Must-Have For Credibility

#### 1. Forecast-native question and resolution contracts

A serious 2026 platform does not begin with a report. It begins with forecast questions, explicit outcome types, resolution criteria, fallback sources, and scoring semantics. Metaculus has doubled down on this operational discipline: its question checklist emphasizes explicit context, absolute dates, third-party resolution, fallback sources, and alignment between headline and resolution criteria, while its live scoring system supports binary, multiple-choice, and continuous questions via proper log-based scoring. Its public March 16, 2026 Respiratory Outlook also shows what the output looks like when the platform is built around resolved or resolvable forecast questions rather than generic scenario prose: named targets, probability estimates, and prediction intervals updated on a schedule. The research side is moving the same way: PROPHET argues that forecasting questions should be screened for inferability because some future questions cannot be supported by valid or sufficient rationales from available evidence.

What this repo would need to change architecturally:

- Make `forecast_brief.json` and `outcome_spec.json` subordinate to a new forecast-question registry, not the other way around.
- Extend [backend/app/models/probabilistic.py](/Users/danielbloom/Desktop/MiroFishES/backend/app/models/probabilistic.py) so the core unit is a typed forecast target with:
  - question id
  - question type: binary, multiple choice, numeric, date/time, interval, pathway trigger
  - resolution criteria
  - primary and fallback resolution sources
  - scoring rule
  - update cadence
  - inferability or support threshold
- Rework [backend/app/services/outcome_extractor.py](/Users/danielbloom/Desktop/MiroFishES/backend/app/services/outcome_extractor.py) from "metric extraction from runs" into "observation and resolution extraction for forecast targets".
- Treat [frontend/src/components/Step4Report.vue](/Users/danielbloom/Desktop/MiroFishES/frontend/src/components/Step4Report.vue) and [frontend/src/components/Step5Interaction.vue](/Users/danielbloom/Desktop/MiroFishES/frontend/src/components/Step5Interaction.vue) as downstream consumers of question-level forecast objects rather than places where forecast semantics are synthesized late.

References:

- Metaculus Question Approval Checklist: https://www.metaculus.com/help/question-checklist/
- Metaculus Scores FAQ: https://www.metaculus.com/help/scores-faq/
- Metaculus Respiratory Outlook Monthly Update, March 16, 2026: https://www.metaculus.com/files/Respiratory-Outlook-Update-March-2026
- PROPHET: https://arxiv.org/abs/2504.01509

#### 2. Evidence grounding must become an evidence graph with inferability gates, not a bundle-status sidecar

The current `grounding_bundle.json` is useful, but in 2026 it is not enough to say that evidence is `ready`, `partial`, or `unavailable`. Stronger systems are moving toward traceable retrieval and support-aware forecasting. AIA Forecaster explicitly combines agentic search over high-quality sources with a supervisor that reconciles competing forecasts, and PROPHET goes further by arguing that the platform should ask whether the question is even inferable from available evidence. In practice, current forecasting organizations also expose reasoning alongside forecasts, not just final numbers: Good Judgment's commercial service emphasizes daily updated forecasts plus qualitative analysis, and Metaculus Pro Forecasters pair calibrated predictions with clear reasoning for clients.

What this repo would need to change architecturally:

- Evolve [backend/app/services/grounding_bundle_builder.py](/Users/danielbloom/Desktop/MiroFishES/backend/app/services/grounding_bundle_builder.py) into an evidence-graph builder that stores:
  - source snapshot metadata
  - freshness timestamps
  - claim-to-source links
  - support coverage by forecast question
  - contradiction or disagreement markers
  - stale or missing-evidence flags
- Replace `grounding_bundle.json` as a thin top-level object with a richer artifact family:
  - `evidence_index.json`
  - `question_support.json`
  - `source_snapshot_manifest.json`
  - `grounding_status.json`
- Make [backend/app/services/probabilistic_report_context.py](/Users/danielbloom/Desktop/MiroFishES/backend/app/services/probabilistic_report_context.py) consume question support and freshness directly, so Step 4 and Step 5 always expose why a forecast is support-rich, weakly supported, or not forecastable yet.
- Add an explicit inferability gate in Step 2: if evidence coverage is below threshold, the system should refuse to emit a strong forecast artifact rather than emit a cosmetically complete but weakly grounded one.

References:

- AIA Forecaster: https://arxiv.org/abs/2511.07678
- PROPHET: https://arxiv.org/abs/2504.01509
- Good Judgment: https://goodjudgment.com/
- Metaculus Services: https://www.metaculus.com/services/

#### 3. Calibration and backtesting must cover the real forecast surface, not one binary lane

This is the largest credibility gap in the repo relative to external practice. Forecasting organizations that expect to be trusted keep score continuously and across many questions. Good Judgment explicitly markets its calibration curves, Brier-based accountability, and longitudinal track record. Metaculus now operates a live AI-forecasting benchmark, FutureEval, with a daily updated leaderboard using a unified log-score-based evaluation; as of March 29, 2026, its published leaderboard still shows the human baselines above leading model entries. ForecastBench reached a similar conclusion in 2025: expert forecasters beat the top-performing LLM on the benchmark. The academic literature has been clear for years that proper scoring rules are foundational, and more recent work emphasizes that multivariate forecasts need multivariate scores rather than collections of univariate scores.

What this repo would need to change architecturally:

- Promote [backend/app/services/backtest_manager.py](/Users/danielbloom/Desktop/MiroFishES/backend/app/services/backtest_manager.py) and [backend/app/services/calibration_manager.py](/Users/danielbloom/Desktop/MiroFishES/backend/app/services/calibration_manager.py) from a narrow confidence lane into a platform evaluation service.
- Expand [backend/app/models/probabilistic.py](/Users/danielbloom/Desktop/MiroFishES/backend/app/models/probabilistic.py) so each forecast target declares its scoring rule and calibration regime.
- Replace `observed_truth_registry.json` with a resolved-case registry that can evaluate:
  - binary events via Brier and log score
  - multiple choice via log score
  - numeric targets via CRPS and interval score
  - pathway or multi-metric bundles via energy score or variogram-style diagnostics where appropriate
- Make [backend/app/services/ensemble_manager.py](/Users/danielbloom/Desktop/MiroFishES/backend/app/services/ensemble_manager.py) emit forecast distributions and dependence metadata, not only aggregate summaries of run outputs.
- Make [frontend/src/components/ProbabilisticReportContext.vue](/Users/danielbloom/Desktop/MiroFishES/frontend/src/components/ProbabilisticReportContext.vue) hide any strong confidence language unless the specific forecast target and scoring family are backtested and in-date.

References:

- Metaculus FutureEval: https://www.metaculus.com/futureeval/
- ForecastBench: https://arxiv.org/abs/2409.19839
- Good Judgment track-record material: https://goodjudgment.com/wp-content/uploads/2022/10/Superforecaster-Accuracy.pdf
- Good Judgment scoring example: https://goodjudgment.com/wp-content/uploads/2022/04/Superforecasters-Covid-Recovery-31-March-2022.pdf
- Gneiting and Raftery, Strictly Proper Scoring Rules: https://stat.uw.edu/research/tech-reports/strictly-proper-scoring-rules-prediction-and-estimation
- Multivariate scoring review and extensions: https://ascmo.copernicus.org/articles/11/23/2025/

#### 4. Forecasts need continuous updates, staleness controls, and end-to-end live proof

Current external practice is plainly operational. Good Judgment sells daily updated forecast monitoring. Metaculus is publishing monthly update products with explicit revisions, current evidence, and changed intervals. In operational weather forecasting, the modern frontier is not just generating forecasts but coupling them with sequential data assimilation so forecasts can be revised as observations arrive. MiroFishES currently has incomplete live proof, which means even truthful artifact contracts do not yet compound into user trust.

What this repo would need to change architecturally:

- Add a versioned forecast-state layer on top of [backend/app/services/simulation_manager.py](/Users/danielbloom/Desktop/MiroFishES/backend/app/services/simulation_manager.py) and [backend/app/services/ensemble_manager.py](/Users/danielbloom/Desktop/MiroFishES/backend/app/services/ensemble_manager.py):
  - `forecast_state.json`
  - `update_manifest.json`
  - `signpost_status.json`
  - `staleness_status.json`
- Introduce scheduled re-grounding and selective reforecasting rather than only one prepare-and-run pattern.
- Add signposts and trigger logic so the platform can say "this forecast is stale", "this assumption broke", or "this scenario threshold was crossed".
- Expand the local operator harness so Step 2 through Step 5 live proof is an explicit release gate, not an aspirational status note.
- Make [frontend/src/components/Step3Simulation.vue](/Users/danielbloom/Desktop/MiroFishES/frontend/src/components/Step3Simulation.vue) and [frontend/src/components/Step4Report.vue](/Users/danielbloom/Desktop/MiroFishES/frontend/src/components/Step4Report.vue) foreground freshness, last update, trigger changes, and invalidation events ahead of visual compare affordances.

References:

- Good Judgment: https://goodjudgment.com/
- Metaculus Respiratory Outlook Monthly Update, March 16, 2026: https://www.metaculus.com/files/Respiratory-Outlook-Update-March-2026
- Ensemble data assimilation for AI weather forecasting: https://gmd.copernicus.org/articles/18/7215/2025/gmd-18-7215-2025.html

### Differentiators Worth Building After Credibility Is Real

#### 5. Replace cluster-first scenario analysis with pathway synthesis, triggers, and option value

The repo's empirical clusters are useful for exploration, but clusters are not a mature answer to "what should we do if conditions evolve this way?" Current strategic foresight practice is more explicit about scenarios as structured pathways tied to assumptions, triggers, and actions. The OECD's 2025 foresight toolkit emphasizes challenging assumptions, building scenarios, stress-testing strategies, and developing actionable plans. The IMF's 2025 work on scenario synthesis argues for reconciling judgmental narratives with statistical forecasts rather than leaving them as disconnected stories. DAPP remains relevant because it treats pathways as sequences of actions with tipping points, signposts, and trigger conditions rather than as static scenario labels.

What this repo would need to change architecturally:

- Relegate [backend/app/services/scenario_clusterer.py](/Users/danielbloom/Desktop/MiroFishES/backend/app/services/scenario_clusterer.py) to exploratory analysis rather than the main scenario abstraction.
- Add a new pathway synthesis service that produces:
  - baseline forecast
  - named scenario deltas
  - pathway trigger conditions
  - action options
  - option-preserving preparatory steps
  - signposts to monitor
- Extend `uncertainty_spec.json` and `outcome_spec.json` so scenarios map to explicit pathway assumptions rather than only perturbation profiles.
- Make Step 4 compare operate on pathway snapshots and trigger differences, not only left/right scope cards.

References:

- OECD Strategic Foresight Toolkit: https://www.oecd.org/en/publications/foresight-toolkit-for-resilient-public-policy_bcdd9304-en.html
- IMF Scenario Synthesis and Macroeconomic Risk: https://www.imf.org/en/publications/wp/issues/2025/05/29/scenario-synthesis-and-macroeconomic-risk-566954
- Dynamic Adaptive Policy Pathways chapter: https://link.springer.com/chapter/10.1007/978-3-030-05252-2_4
- Developing dynamic adaptive policy pathways: https://link.springer.com/article/10.1007/s10584-014-1210-4

#### 6. Add hybrid aggregation: model forecasts, expert judgment, and market or crowd priors

Pure model-only forecasting is no longer the strongest story. External practice increasingly suggests that mixed systems are better. Good Judgment and Metaculus both institutionalize high-performing human forecasting as a real benchmark, not a qualitative garnish. AIA Forecaster is notable because it reports additive value when combined with market consensus, even when market consensus alone remains stronger on a harder benchmark. In other words, a strong platform should support external priors and aggregation rather than pretending one internal model stack is sufficient.

What this repo would need to change architecturally:

- Add a prior-ingestion and forecast-aggregation layer ahead of [backend/app/services/ensemble_manager.py](/Users/danielbloom/Desktop/MiroFishES/backend/app/services/ensemble_manager.py).
- Support provenance-tagged forecast components:
  - repo simulation prior
  - retrieved evidence prior
  - human analyst prior
  - external market or crowd prior
- Persist forecast decomposition and aggregation decisions in the artifact model so report consumers can see where the final probability came from.
- Make Step 5 questions answerable against both the aggregate and the component forecasts.

References:

- Metaculus Services: https://www.metaculus.com/services/
- Good Judgment: https://goodjudgment.com/
- AIA Forecaster: https://arxiv.org/abs/2511.07678

#### 7. Add a real intervention layer only when the platform can separate observational from causal claims

A stronger platform should eventually answer "what if we do X?" but only after it can separate observational associations from intervention claims. The repo is already honest that sensitivity is observational. That honesty should remain. The differentiator is not to relabel observational sensitivity as causal, but to add a separate intervention-grade layer when assumptions, data, and methods justify it. The causal prediction literature is explicit that ordinary predictive models do not answer hypothetical intervention questions correctly, and DAPP-style practice reinforces that actionable scenario systems need triggers and policy-response logic, not just descriptive driver rankings.

What this repo would need to change architecturally:

- Keep [backend/app/services/sensitivity_analyzer.py](/Users/danielbloom/Desktop/MiroFishES/backend/app/services/sensitivity_analyzer.py) for observational analysis, but stop letting it stand in for action guidance.
- Add a separate intervention artifact family:
  - `causal_model.json`
  - `intervention_spec.json`
  - `counterfactual_forecasts.json`
  - `identification_assumptions.json`
- Require explicit assumptions and data provenance for every intervention claim.
- Surface intervention outputs separately in Step 4 and Step 5 with stronger caveats and narrower scope.

References:

- Forecasting Causal Effects of Interventions versus Predicting Future Outcomes: https://pmc.ncbi.nlm.nih.gov/articles/PMC9030387/
- Scoping review of causal methods for hypothetical interventions: https://diagnprognres.biomedcentral.com/articles/10.1186/s41512-021-00092-9
- Dynamic Adaptive Policy Pathways chapter: https://link.springer.com/chapter/10.1007/978-3-030-05252-2_4

### Low-Value Impressiveness

#### 8. Things that will look advanced but will not materially improve trust

The following are lower-value than they appear unless the credibility work above is already done:

- richer report prose and chat polish while question design, evidence support, and scoring remain weak
- more elaborate empirical clustering while pathway structure and action triggers remain absent
- broader compare surfaces while underlying forecasts are still weakly grounded or not backtested
- stronger confidence labels while calibration remains binary-only
- larger simulation ensembles without better measurement, scoring, or freshness handling
- "causal" wording layered onto observational sensitivity

Why this is the right deprioritization:

- ForecastBench and FutureEval both show that forecasting quality is still hard and that evaluation matters more than glossy interaction surfaces.
- Good Judgment and Metaculus both compete on kept-score forecasting, update discipline, and explicit reasoning, not on presentation alone.
- DAPP, OECD, and IMF-style scenario practice emphasize assumptions, triggers, and decision support over decorative scenario richness.

References:

- ForecastBench: https://arxiv.org/abs/2409.19839
- Metaculus FutureEval: https://www.metaculus.com/futureeval/
- Good Judgment: https://goodjudgment.com/
- OECD Strategic Foresight Toolkit: https://www.oecd.org/en/publications/foresight-toolkit-for-resilient-public-policy_bcdd9304-en.html

## Architectural Direction For This Repo

The architecture should evolve in three steps.

### Phase 1: Make forecasting the kernel

- Introduce a forecast-question registry and resolution service.
- Move evidence support and scoring metadata into the core schema.
- Treat Step 4 and Step 5 as renderers of forecast state, not as the place where forecast semantics are invented.

Primary files and services:

- [backend/app/models/probabilistic.py](/Users/danielbloom/Desktop/MiroFishES/backend/app/models/probabilistic.py)
- [backend/app/services/outcome_extractor.py](/Users/danielbloom/Desktop/MiroFishES/backend/app/services/outcome_extractor.py)
- [backend/app/services/probabilistic_report_context.py](/Users/danielbloom/Desktop/MiroFishES/backend/app/services/probabilistic_report_context.py)
- [backend/app/api/simulation.py](/Users/danielbloom/Desktop/MiroFishES/backend/app/api/simulation.py)

### Phase 2: Make evidence and evaluation unavoidable

- Upgrade grounding into an evidence graph with inferability and freshness gates.
- Broaden backtesting and calibration to the real forecast surface.
- Add rolling update, invalidation, and stale-forecast status.

Primary files and services:

- [backend/app/services/grounding_bundle_builder.py](/Users/danielbloom/Desktop/MiroFishES/backend/app/services/grounding_bundle_builder.py)
- [backend/app/services/backtest_manager.py](/Users/danielbloom/Desktop/MiroFishES/backend/app/services/backtest_manager.py)
- [backend/app/services/calibration_manager.py](/Users/danielbloom/Desktop/MiroFishES/backend/app/services/calibration_manager.py)
- [backend/app/services/ensemble_manager.py](/Users/danielbloom/Desktop/MiroFishES/backend/app/services/ensemble_manager.py)

### Phase 3: Add real differentiation

- Build pathway synthesis and signposts.
- Add hybrid aggregation with external priors.
- Add intervention-grade analysis as a separate, more demanding layer.

Primary files and services:

- [backend/app/services/scenario_clusterer.py](/Users/danielbloom/Desktop/MiroFishES/backend/app/services/scenario_clusterer.py)
- [backend/app/services/sensitivity_analyzer.py](/Users/danielbloom/Desktop/MiroFishES/backend/app/services/sensitivity_analyzer.py)
- [backend/app/services/uncertainty_resolver.py](/Users/danielbloom/Desktop/MiroFishES/backend/app/services/uncertainty_resolver.py)
- [backend/app/services/report_agent.py](/Users/danielbloom/Desktop/MiroFishES/backend/app/services/report_agent.py)

## Bottom Line

If MiroFishES wants to be materially stronger in 2026, it should stop treating credibility as something that can be added after scenario generation. The platform needs forecast-native objects, evidence-native grounding, and score-native accountability first. Only after that should it invest heavily in pathway synthesis, hybrid aggregation, and causal intervention support. Clusters, compare, and chat matter, but in 2026 they are not where serious trust is earned.
