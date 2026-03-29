import test from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";

const repoRoot = "/Users/danielbloom/Desktop/MiroFishES";
const verifierPath = path.join(repoRoot, "scripts", "verify-ruflo-workspace.mjs");

function runVerifier(args = [], envOverrides = {}) {
  return spawnSync(process.execPath, [verifierPath, ...args], {
    cwd: repoRoot,
    encoding: "utf8",
    timeout: 20000,
    env: {
      ...process.env,
      ...envOverrides,
    },
  });
}

test("verify-ruflo-workspace reports machine-readable swarm/task readiness", () => {
  const result = runVerifier(["--json"]);

  assert.equal(result.status, 0, `expected exit 0, got ${result.status}\n${result.stderr}`);

  const payload = JSON.parse(result.stdout);

  assert.equal(payload.ruflo_ready, "swarm-task-only");
  assert.equal(payload.memory_ready, false);
  assert.match(payload.reason, /sql\.js/i);
  assert.equal(payload.checks.system_info_cwd.ok, true);
  assert.equal(payload.checks.workspace_claude_flow.ok, true);
  assert.equal(payload.checks.workspace_swarm.ok, true);
  assert.equal(payload.checks.root_claude_flow_absent.ok, true);
  assert.equal(payload.checks.root_swarm_absent.ok, true);
});

test("verify-ruflo-workspace strict-memory mode fails with the same blocker", () => {
  const result = runVerifier(["--strict-memory", "--json"]);

  assert.notEqual(result.status, 0, "strict-memory mode should fail while sql.js is unresolved");

  const payload = JSON.parse(result.stdout);

  assert.equal(payload.ruflo_ready, "swarm-task-only");
  assert.equal(payload.memory_ready, false);
  assert.match(payload.reason, /sql\.js/i);
});

test("verify-ruflo-workspace does not leave transient repo state behind", () => {
  const hadClaudeFlow = existsSync(path.join(repoRoot, ".claude-flow"));
  const hadSwarm = existsSync(path.join(repoRoot, ".swarm"));

  const result = runVerifier(["--json"]);

  assert.equal(result.status, 0, `expected exit 0, got ${result.status}\n${result.stderr}`);

  if (!hadClaudeFlow) {
    assert.equal(existsSync(path.join(repoRoot, ".claude-flow")), false);
  }

  if (!hadSwarm) {
    assert.equal(existsSync(path.join(repoRoot, ".swarm")), false);
  }
});

test("verify-ruflo-workspace surfaces launcher startup failures in json mode", () => {
  const result = runVerifier(["--json"], {
    RUFLO_BIN: "/definitely/missing/cli.js",
  });

  assert.notEqual(result.status, 0, "missing launcher should fail");

  const payload = JSON.parse(result.stdout);

  assert.equal(payload.ruflo_ready, "fallback-required");
  assert.equal(payload.memory_ready, false);
  assert.match(payload.reason, /Missing Ruflo CLI/i);
  assert.doesNotMatch(payload.reason, /Timed out waiting for initialize/i);
});

test("verify-ruflo-workspace text mode reports startup failures without crashing", () => {
  const result = runVerifier([], {
    RUFLO_BIN: "/definitely/missing/cli.js",
  });

  assert.notEqual(result.status, 0, "missing launcher should fail");
  assert.match(result.stdout, /FAIL readiness fallback-required/i);
  assert.match(result.stdout, /Missing Ruflo CLI/i);
  assert.doesNotMatch(result.stderr, /TypeError/i);
});
