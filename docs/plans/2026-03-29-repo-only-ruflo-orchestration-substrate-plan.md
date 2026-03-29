# Repo-Only Ruflo Orchestration Substrate Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Finish the repo-owned Ruflo substrate so later forecasting phases can start from one truthful Ruflo rule and one fallback rule without patching any external Ruflo install.

**Architecture:** Keep the current repo-owned launcher plus verifier because the audited repo already provides workspace-safe `swarm_init` and `task_create`. Limit this phase to contract hardening: prove state lands inside the workspace, emit one explicit readiness verdict, separate `swarm/task ready` from `memory blocked`, and align docs so later prompts do not infer readiness from global session tools, `system_info.features`, or stray state files. Step 2 through Step 5 product flows stay Ruflo-independent.

**Tech Stack:** Bash launcher, Node.js verifier, npm package scripts, Markdown docs under `docs/` and `README.md`.

---

## Audit Snapshot: 2026-03-29

- `npm run verify:ruflo` currently exits `0` and proves `system_info.cwd`, `swarm_init`, and `task_create`.
- A direct repo-local smoke run showed Ruflo writes to `.claude-flow/swarm`, `.claude-flow/tasks`, `.swarm/memory.db`, and `.swarm/schema.sql` under the workspace, not to `/.claude-flow` or `/.swarm`.
- `memory_store` still fails with `Cannot find package 'sql.js' imported from /Users/danielbloom/Desktop/ruflo/v3/@claude-flow/cli/dist/src/memory/memory-initializer.js`.
- `system_info.features.memory === true` is not a truthful readiness signal, because memory reporting says `true` while `memory_store` still fails.
- The current Step 2 through Step 5 operator docs do not depend on Ruflo orchestration. Keep that boundary intact.

## Phase Decision

The repo is already good enough for `swarm/task-only` Ruflo orchestration.

This phase should not redesign the launcher, patch the external Ruflo install, or make product code depend on Ruflo memory.

This phase should only remove ambiguity by locking one exact repo-only contract:

1. **Ruflo rule:** Run `npm run verify:ruflo` from the repo root. If it exits `0`, later phases may use Ruflo only through the repo-owned launcher and only for `swarm_*` plus `task_*` orchestration.
2. **Fallback rule:** If that verification exits non-zero, or if the work needs memory, AgentDB, claims, or any other state beyond `swarm/task`, use built-in Codex subagents only and ignore Ruflo.

## Exact Repo-Only Orchestration Contract

### Approved entrypoint

- `npm run verify:ruflo` is the only readiness gate.
- `npm run ruflo:mcp` is the only approved launcher for later phases.
- The already-bound session `mcp__ruflo__*` tools are not an approval signal unless they were started by the repo-owned launcher in the current repo root.

### Ready subset

- `swarm_init`
- `task_create`
- other `swarm_*` and `task_*` calls that share the same workspace-local state path assumptions

### Blocked subset

- `memory_store`
- AgentDB and memory-backed helpers
- any workflow that needs truthful Ruflo memory availability rather than swarm/task coordination only

### Non-signals

Do not treat any of these as readiness proof:

- `system_info.features.memory`
- the mere existence of `.swarm/memory.db`
- a globally available Ruflo MCP tool surface in the session
- older plan text that predates this contract

### Required reporting shape

Later phases need one verdict with three facts:

- `ruflo_ready`: `swarm-task-only` or `fallback-required`
- `memory_ready`: `true` or `false`
- `reason`: concise human-readable explanation, including the known `sql.js` blocker when memory is unavailable

## Implementation Tasks

### Task 1: Harden the verifier into a truthful readiness gate

**Files:**
- Modify: `scripts/verify-ruflo-workspace.mjs`
- Modify: `package.json`
- Modify only if needed for clearer failure messaging: `scripts/ruflo-mcp-workspace.sh`

**Steps:**
1. Extend the verifier so it checks not only `system_info.cwd`, `swarm_init`, and `task_create`, but also the actual write locations created during the smoke run.
2. Assert that repo-local `.claude-flow/swarm` and `.claude-flow/tasks` appear during the smoke run.
3. Assert that root-level `/.claude-flow` and `/.swarm` do not appear during the smoke run.
4. Keep the `memory_store` probe, but classify the current `sql.js` failure as `memory blocked by external Ruflo dependency`, not as a generic verifier failure.
5. Add a machine-readable mode, preferably `--json`, that emits the exact contract fields `ruflo_ready`, `memory_ready`, and `reason`.
6. Keep exit code `0` when `swarm/task` is ready and memory is only blocked by the known external dependency.
7. Keep strict memory mode non-zero when `memory_store` does not succeed.
8. If `scripts/ruflo-mcp-workspace.sh` remains unchanged, document its current `RUFLO_BIN` override path clearly instead of relying on the hard-coded default as hidden knowledge.

### Task 2: Align repo docs around one truthful rule and one fallback rule

**Files:**
- Modify: `README.md`
- Modify: `docs/plans/2026-03-29-ruflo-orchestration-foundation-wave.md`
- Do not modify unless the audit finds Ruflo claims there: `docs/local-probabilistic-operator-runbook.md`

**Steps:**
1. Replace inferred wording with audited wording: `swarm/task-only ready`, `memory blocked`, `fallback to built-in subagents`.
2. Document that the repo-owned verifier, not `system_info.features`, is the authoritative readiness signal.
3. Document that passing `npm run verify:ruflo` does not approve memory, AgentDB, or claims-based workflows.
4. Surface the `RUFLO_BIN` override contract so the repo does not depend on an implicit personal install path.
5. Keep the Step 2 through Step 5 operator runbook Ruflo-independent unless a real product dependency appears later.

### Task 3: Make later prompts unambiguous

**Files:**
- Modify: `docs/plans/2026-03-29-ruflo-orchestration-foundation-wave.md`
- Modify: `README.md`

**Steps:**
1. Add a short copy-pastable preflight snippet for future phases that says exactly when Ruflo is allowed and exactly when fallback is required.
2. State explicitly that the preflight check is repo-local and does not authorize patching the external Ruflo install.
3. State explicitly that current memory failure is expected and does not block swarm/task-only later phases.
4. Keep the wording short enough that future prompts can quote it without reinterpretation.

## Repo-Local Hardening Still Needed

- The verifier must prove actual write locations, not just `cwd`.
- The verifier must report a single readiness verdict in machine-readable form.
- Docs must stop treating the hard-coded `RUFLO_BIN` default as hidden context.
- Docs must state that Step 2 through Step 5 product flows are independent of Ruflo orchestration.
- Verification must leave no stray `.claude-flow/` or `.swarm/` directories behind unless they existed before the run.

## Explicitly Out Of Scope

- Patching `/Users/danielbloom/Desktop/ruflo/...`
- Making `memory_store` succeed
- Declaring AgentDB or Ruflo memory ready
- Changing forecasting product code in Step 2 through Step 5 to depend on Ruflo
- Treating the current globally bound Ruflo MCP server as the authoritative launcher

## Acceptance Criteria

- `npm run verify:ruflo` exits `0` and reports `ruflo_ready=swarm-task-only`.
- The verifier proves workspace-local `.claude-flow/*` writes and the absence of `/.claude-flow` and `/.swarm` writes during the smoke run.
- The verifier reports `memory_ready=false` with the known `sql.js` dependency reason until the external Ruflo install is fixed.
- `node ./scripts/verify-ruflo-workspace.mjs --strict-memory` exits non-zero and surfaces the same known blocker explicitly.
- `README.md` and `docs/plans/2026-03-29-ruflo-orchestration-foundation-wave.md` state the same ready rule and fallback rule.
- `docs/local-probabilistic-operator-runbook.md` does not claim Ruflo memory or orchestration as a prerequisite for Step 2 through Step 5 product behavior.
- Running the verifier does not leave transient `.claude-flow/` or `.swarm/` artifacts in the repo when they were absent before the run.

## Exact Verification Commands For This Phase

Run these from `/Users/danielbloom/Desktop/MiroFishES`.

```bash
npm run verify:ruflo
```

Expected:
- exit `0`
- workspace-safe `swarm/task` verdict
- explicit memory-blocked reason

```bash
node ./scripts/verify-ruflo-workspace.mjs --json
```

Expected:
- `ruflo_ready` is `swarm-task-only`
- `memory_ready` is `false`
- `reason` names the known external `sql.js` blocker

```bash
node ./scripts/verify-ruflo-workspace.mjs --strict-memory
```

Expected:
- exit non-zero
- output names the same `sql.js` blocker

```bash
rg -n "swarm-task-only|fallback to built-in subagents|RUFLO_BIN|memory_ready|verify:ruflo" README.md docs/plans/2026-03-29-ruflo-orchestration-foundation-wave.md scripts/verify-ruflo-workspace.mjs scripts/ruflo-mcp-workspace.sh package.json
```

Expected:
- the contract wording and command surface match across docs and scripts

```bash
git status --short --untracked-files=all
```

Expected:
- no transient `.claude-flow/` or `.swarm/` entries created by verification remain in the worktree

## Handoff Note

Phase implementation should stop as soon as the verifier and docs make the two rules unambiguous. No later forecasting wave should be blocked on Ruflo memory readiness.
