# Ruflo Orchestration Foundation Wave

**Goal:** Make Ruflo's orchestration state workspace-safe in MiroFishES when possible, and document the exact fallback when it is not.

## North-star alignment

The March 28 forecasting plan assumes later waves can rely on a repeatable research and execution substrate. This wave does not implement forecasting features. It only hardens the orchestration foundation enough that later prompts can decide, truthfully, when Ruflo is usable and when built-in subagents should stay the default.

## Root cause reproduced

In this Codex desktop session, the bound Ruflo MCP server reports:

- `system_info.cwd == "/"`

That launch context causes stateful Ruflo MCP tools to derive storage paths from the filesystem root:

- `swarm_init` tries to create `/.claude-flow/swarm`
- `task_create` tries to create `/.claude-flow/tasks`
- memory initialization derives `/.swarm/memory.db` from `process.cwd()`

This is not a MiroFish product bug. It is a Ruflo MCP launch-context bug in the current session.

## Repo changes in this wave

1. Added `scripts/ruflo-mcp-workspace.sh`
   - forces Ruflo MCP startup from the repository root
   - keeps state inside the workspace instead of `/.claude-flow` or `/.swarm`
   - supports `RUFLO_BIN` so the repo does not depend on one hidden personal install path

2. Added `scripts/verify-ruflo-workspace.mjs`
   - starts the repo-owned launcher
   - verifies `system_info.cwd`
   - verifies `swarm_init`
   - verifies `task_create`
   - verifies repo-local `.claude-flow/` and `.swarm/` writes
   - verifies `/.claude-flow` and `/.swarm` were not created
   - exposes a machine-readable `--json` readiness verdict
   - reports the current memory blocker explicitly

3. Added npm scripts
   - `npm run verify:ruflo:contract`
   - `npm run ruflo:mcp`
   - `npm run verify:ruflo`

4. Ignored repo-local Ruflo state
   - `.claude-flow/`
   - `.swarm/`

## What is actually fixed

Verified with the repo-owned launcher:

- Ruflo can run with `cwd=/Users/danielbloom/Desktop/MiroFishES`
- `swarm_init` succeeds
- `task_create` succeeds
- those operations persist in workspace-local state instead of the filesystem root
- the verifier now proves the actual write locations instead of inferring them from `cwd` alone

## What remains unsupported

`memory_store` still fails even with the workspace launcher because the external Ruflo install cannot resolve `sql.js` from:

- `/Users/danielbloom/Desktop/ruflo/v3/@claude-flow/cli/dist/src/memory/memory-initializer.js`

Current observed error:

- `Cannot find package 'sql.js' imported from /Users/danielbloom/Desktop/ruflo/v3/@claude-flow/cli/dist/src/memory/memory-initializer.js`

That is a second, separate Ruflo installation problem. It is not caused by MiroFish or by workspace-root pathing.

## Session guidance

Authoritative readiness signal:

- `npm run verify:ruflo`

Do **not** treat any of these as readiness proof:

- the already-bound `mcp__ruflo__*` tools in the current Codex session
- `system_info.features.memory`
- the mere existence of `.swarm/memory.db`

Exact later-phase rule:

1. Run `npm run verify:ruflo` from the repo root.
2. If it exits `0`, later phases may use Ruflo only through `npm run ruflo:mcp` and only for `swarm_*` plus `task_*` orchestration.
3. If that verification fails, or if the work needs memory, AgentDB, claims, or any other memory-backed Ruflo state, use built-in Codex subagents instead.

Machine-readable status:

- `node ./scripts/verify-ruflo-workspace.mjs --json`

Current expected verdict:

- `ruflo_ready = swarm-task-only`
- `memory_ready = false`
- reason names the external `sql.js` dependency blocker

## Follow-on prompt assumptions

Later waves may safely assume:

1. There is a repo-owned way to launch Ruflo without writing to `/.claude-flow/...`.
2. Workspace-safe Ruflo swarm/task orchestration is reproducibly testable with `npm run verify:ruflo`.
3. Ruflo memory / AgentDB is still not approved for later phases until the external `sql.js` packaging issue is fixed.
4. Built-in Codex subagents are the fallback whenever the verifier fails or the task needs memory-backed Ruflo features.
