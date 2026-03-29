# MiroFishES Docs Reset Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reframe the repo documentation so it clearly explains how MiroFishES has diverged from the original fork-era MiroFish baseline, while keeping all runtime and verification claims truthful.

**Architecture:** Make the root README the front door for mixed audiences, add one canonical differentiation document plus a docs index, and align the operator runbook and current-status snapshot so they reinforce the same story instead of restating it differently.

**Tech Stack:** Markdown documentation, repo-local verification commands, existing plan and runbook artifacts

---

### Task 1: Create the docs information architecture

**Files:**
- Create: `docs/README.md`
- Create: `docs/what-mirofishes-adds.md`

**Step 1: Add a docs index**

Document the main reading paths for engineers, operators, and reviewers.

**Step 2: Add the canonical differentiation document**

Describe the fork-era baseline, what this repo now adds, and what remains bounded or unsupported.

### Task 2: Rewrite the repo front door

**Files:**
- Modify: `README.md`

**Step 1: Replace the current status-heavy intro**

Lead with what MiroFishES is, how it differs from the original fork-era baseline, and what claims are still bounded.

**Step 2: Add a clearer getting-started and verification narrative**

Keep the quick-start and probabilistic operator instructions, but reorganize them so a fresh reader can understand how to start from scratch and what each verification layer proves.

### Task 3: Align the supporting docs

**Files:**
- Modify: `docs/local-probabilistic-operator-runbook.md`
- Modify: `docs/plans/2026-03-29-forecasting-integration-hardening-wave.md`

**Step 1: Tighten each document's purpose**

Make the runbook an operations guide, and make the hardening-wave note a status/contract snapshot instead of a project overview.

**Step 2: Cross-link to the new canonical docs**

Point both docs back to `docs/README.md` and `docs/what-mirofishes-adds.md`.

### Task 4: Run focused verification

**Files:**
- Verify only; no code changes

**Step 1: Check markdown link targets and patch formatting**

Run a repo-local markdown link and formatting sanity pass.

**Step 2: Summarize the new documentation contract**

Explain what now serves as the front door, what serves as the fork-delta explanation, and what remains the authoritative runtime/status reference.
