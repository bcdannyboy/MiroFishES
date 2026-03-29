# Probabilistic Reporting Surfaces Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make Step 4 and Step 5 use probabilistic evidence, provenance, support, and calibration artifacts directly instead of treating them as sidecars.

**Architecture:** Build probabilistic report context before Step 4 generation, pass it into report-agent planning and section generation, enrich the context contract for UI consumption, and upgrade Step 4/Step 5/operator utilities to surface support, warnings, assumptions, and bounded compare views without overstating semantics.

**Tech Stack:** Python 3.11+, Flask, pytest, Vue 3, Vite, Node test runner, JSON artifact contracts under `backend/uploads/simulations/`.

---

### Task 1: Add failing backend tests for report-context-first generation

**Files:**
- Modify: `backend/tests/unit/test_probabilistic_report_api.py`
- Modify: `backend/tests/unit/test_probabilistic_report_context.py`
- Modify: `backend/tests/unit/test_probabilistic_report_context.py`

**Step 1: Write the failing tests**

- Assert scoped Step 4 generation builds probabilistic context before report-agent generation and passes it into the agent.
- Assert scoped Step 5 report-agent chat can use probabilistic scope directly without requiring a pre-saved report context.
- Assert report-context payloads expose support/warnings/representative runs/assumption ledger/calibration provenance cleanly.

**Step 2: Run tests to verify they fail**

Run: `pytest backend/tests/unit/test_probabilistic_report_api.py backend/tests/unit/test_probabilistic_report_context.py -q`

**Step 3: Write minimal backend implementation**

- Update `backend/app/api/report.py`
- Update `backend/app/services/report_agent.py`
- Update `backend/app/services/probabilistic_report_context.py`

**Step 4: Re-run backend tests**

Run: `pytest backend/tests/unit/test_probabilistic_report_api.py backend/tests/unit/test_probabilistic_report_context.py -q`

### Task 2: Upgrade report-agent probabilistic prompt plumbing

**Files:**
- Modify: `backend/app/services/report_agent.py`
- Modify: `backend/app/api/report.py`

**Step 1: Write the failing tests**

- Assert planning and section-generation prompts include probabilistic evidence/provenance blocks when present.
- Assert chat prompt formatting stays concise and scoped.

**Step 2: Run red**

Run: `pytest backend/tests/unit/test_probabilistic_report_api.py -q`

**Step 3: Implement the minimal prompt/context changes**

- Add deterministic probabilistic context formatting helpers.
- Pass probabilistic context into `ReportAgent` before generation begins.
- Keep calibrated wording gated.

**Step 4: Re-run**

Run: `pytest backend/tests/unit/test_probabilistic_report_api.py -q`

### Task 3: Add failing frontend tests for Step 4/Step 5 provenance and compare state

**Files:**
- Modify: `frontend/tests/unit/probabilisticRuntime.test.mjs`
- Modify: `frontend/src/utils/probabilisticRuntime.js`

**Step 1: Write the failing tests**

- Assert Step 4 runtime helpers derive richer provenance/evidence cards.
- Assert Step 5 state shows probabilistic report-agent grounding honestly.
- Assert compare-card derivation returns bounded compare payloads from report context.

**Step 2: Run red**

Run: `node --test frontend/tests/unit/probabilisticRuntime.test.mjs`

**Step 3: Implement minimal runtime utility changes**

- Add compare/evidence derivation helpers.
- Update Step 4/Step 5 helper text and calibration gating copy.

**Step 4: Re-run**

Run: `node --test frontend/tests/unit/probabilisticRuntime.test.mjs`

### Task 4: Wire the operator surfaces

**Files:**
- Modify: `frontend/src/components/ProbabilisticReportContext.vue`
- Modify: `frontend/src/components/Step3Simulation.vue`
- Modify: `frontend/src/components/Step4Report.vue`
- Modify: `frontend/src/components/Step5Interaction.vue`

**Step 1: Implement the smallest UI changes that satisfy the tested state**

- Stronger provenance/evidence rendering in `ProbabilisticReportContext.vue`
- Step 4 compare card using existing representative runs and scenario families
- Step 5 report-agent scope banner and compare-oriented starter affordance
- Small Step 3 copy adjustments only if needed for handoff honesty

**Step 2: Verify frontend behavior**

Run: `node --test frontend/tests/unit/probabilisticRuntime.test.mjs`

**Step 3: Build if justified**

Run: `npm --prefix frontend run build`

### Task 5: Final targeted verification

**Files:**
- Verify changed backend/frontend surfaces only

**Step 1: Run targeted backend suite**

Run: `pytest backend/tests/unit/test_probabilistic_report_api.py backend/tests/unit/test_probabilistic_report_context.py -q`

**Step 2: Run targeted frontend suite**

Run: `node --test frontend/tests/unit/probabilisticRuntime.test.mjs`

**Step 3: Run frontend build smoke**

Run: `npm --prefix frontend run build`

**Step 4: Summarize operator-visible changes**

- What Step 4 can now ground directly
- What Step 5 report-agent can now do
- What compare surface exists
- What still remains legacy-only
