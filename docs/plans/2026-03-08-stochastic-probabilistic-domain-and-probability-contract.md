# Stochastic Probabilistic Simulation Domain and Probability Contract

**Date:** 2026-03-08

## 1. Purpose

Define what probability means inside MiroFishES so implementation and reporting do not drift into pseudo-quantification.

## 2. Deterministic boundary

For a fixed prepared simulation, the following are deterministic by contract:

- source files
- extracted text
- approved ontology
- selected graph snapshot
- selected entity set
- prepared profile set
- baseline scalar config
- outcome metric definitions
- aggregation rules

## 3. Stochastic boundary

The following are stochastic by contract:

- sampled uncertainty fields
- runtime activation choices
- uncertain exogenous event occurrence and timing
- runtime action-generation variance
- perturbation and counterfactual run choices when explicitly requested

## 4. Probability modes

### Mode A: Empirical ensemble probability

Meaning:

- frequency over an explicitly defined run family.

Allowed language:

- "empirical ensemble estimate"
- "observed in X of Y runs"

### Mode B: Calibrated probability

Meaning:

- ensemble or model output that has been adjusted through a validated calibration artifact.

Allowed language:

- "calibrated probability"

Precondition:

- benchmark target exists
- calibration artifact version exists

### Mode C: Representative narrative

Meaning:

- description of one prototype run or cluster exemplar.

Allowed language:

- "representative run"
- "prototype scenario"

Forbidden language:

- any implication that the representative run is automatically the most likely future

## 5. Forbidden probability behaviors

- inventing probability values in prose without aggregate artifacts
- presenting one run as a probability distribution
- calling a value calibrated when no calibration artifact exists
- mixing run-level and ensemble-level statements without labeling which is which

## 6. Report-language rules

- every probability must cite run count or calibration version
- every exemplar narrative must cite its run or cluster origin
- every tail-risk statement must be grounded in explicit run-family evidence
- when evidence is thin, the UI must say so
