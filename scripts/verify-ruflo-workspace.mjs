#!/usr/bin/env node

import { existsSync } from "node:fs";
import { readdir, rm } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { setTimeout as delay } from "node:timers/promises";
import { spawn } from "node:child_process";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..");
const launcherPath = path.join(repoRoot, "scripts", "ruflo-mcp-workspace.sh");

const args = new Set(process.argv.slice(2));
const strictMemory = args.has("--strict-memory");
const jsonOutput = args.has("--json");

const repoStateDirs = [
  path.join(repoRoot, ".claude-flow"),
  path.join(repoRoot, ".swarm"),
];
const rootClaudeFlowDir = "/.claude-flow";
const rootSwarmDir = "/.swarm";
const existingRepoState = new Map(repoStateDirs.map((dir) => [dir, existsSync(dir)]));

function parseToolText(result) {
  const text = result?.content?.[0]?.text;
  if (!text) {
    throw new Error("Missing tool text payload");
  }
  return JSON.parse(text);
}

function createCheck(ok, label, details = {}) {
  return { ok, label, ...details };
}

async function cleanupTransientState() {
  for (const dir of repoStateDirs) {
    if (existingRepoState.get(dir)) {
      continue;
    }
    await rm(dir, { force: true, recursive: true });
  }
}

async function pathExists(targetPath) {
  return existsSync(targetPath);
}

async function listDirectory(targetPath) {
  if (!existsSync(targetPath)) {
    return [];
  }
  const entries = await readdir(targetPath);
  return entries.sort();
}

async function terminateChild(child, exitPromise) {
  child.stdin.end();

  const killProcess = (signal) => {
    if (child.killed) {
      return;
    }
    try {
      if (process.platform !== "win32") {
        process.kill(-child.pid, signal);
      } else {
        child.kill(signal);
      }
    } catch {
      // Ignore ESRCH or already-exited children.
    }
  };

  killProcess("SIGTERM");
  const exitResult = await Promise.race([
    exitPromise,
    delay(2000).then(() => null),
  ]);

  if (exitResult) {
    return exitResult;
  }

  killProcess("SIGKILL");
  return Promise.race([
    exitPromise,
    delay(2000).then(() => ({ code: null, signal: "SIGKILL-timeout" })),
  ]);
}

function printSummary(summary) {
  if (jsonOutput) {
    console.log(JSON.stringify(summary, null, 2));
    return;
  }

  const orderedChecks = [
    "system_info_cwd",
    "swarm_init",
    "swarm_id",
    "task_create",
    "workspace_claude_flow",
    "workspace_swarm",
    "root_claude_flow_absent",
    "root_swarm_absent",
  ];

  for (const key of orderedChecks) {
    const check = summary.checks[key];
    if (!check) {
      continue;
    }
    console.log(`${check.ok ? "PASS" : "FAIL"} ${check.label}`);
  }

  const memoryCheck = summary.checks.memory_store;
  if (memoryCheck) {
    if (memoryCheck.ok) {
      console.log("PASS memory_store succeeded");
    } else if (memoryCheck.expected_blocker) {
      console.log(`WARN memory_store blocked by external Ruflo dependency: ${memoryCheck.error}`);
    } else {
      console.log(`FAIL memory_store failed unexpectedly: ${memoryCheck.error ?? "unknown error"}`);
    }
  }

  console.log(
    `${summary.exit_ok ? "PASS" : "FAIL"} readiness ${summary.ruflo_ready}; memory_ready=${summary.memory_ready}; ${summary.reason}`,
  );
}

function buildFailureSummary(message) {
  return {
    repo_root: repoRoot,
    ruflo_ready: "fallback-required",
    memory_ready: false,
    exit_ok: false,
    reason: message,
    checks: {},
  };
}

async function main() {
  if (!existsSync(launcherPath)) {
    throw new Error(`Missing Ruflo workspace launcher: ${launcherPath}`);
  }

  const child = spawn(launcherPath, {
    cwd: repoRoot,
    detached: process.platform !== "win32",
    stdio: ["pipe", "pipe", "pipe"],
  });

  const pending = new Map();
  let nextId = 1;
  let stdoutBuffer = "";
  let stderrBuffer = "";
  let childExited = false;

  child.stdout.setEncoding("utf8");
  child.stderr.setEncoding("utf8");

  child.stdout.on("data", (chunk) => {
    stdoutBuffer += chunk;
    const lines = stdoutBuffer.split("\n");
    stdoutBuffer = lines.pop() ?? "";

    for (const rawLine of lines) {
      const line = rawLine.trim();
      if (!line) {
        continue;
      }

      try {
        const message = JSON.parse(line);
        if (message.id && pending.has(message.id)) {
          const { resolve, reject, timer } = pending.get(message.id);
          clearTimeout(timer);
          pending.delete(message.id);
          if (message.error) {
            reject(new Error(message.error.message));
          } else {
            resolve(message.result);
          }
        }
      } catch {
        // Ignore non-JSON lines; stderr carries logs.
      }
    }
  });

  child.stderr.on("data", (chunk) => {
    stderrBuffer += chunk;
  });

  function describeChildExit(context, code, signal) {
    const trimmedStderr = stderrBuffer.trim();
    if (trimmedStderr) {
      return trimmedStderr;
    }
    const codePart = code === null || code === undefined ? "unknown" : String(code);
    const signalPart = signal ? `, signal ${signal}` : "";
    return `Ruflo launcher exited before ${context} (code ${codePart}${signalPart})`;
  }

  function rejectPendingOnExit(message) {
    for (const [id, entry] of pending.entries()) {
      clearTimeout(entry.timer);
      pending.delete(id);
      entry.reject(new Error(message));
    }
  }

  const exitPromise = new Promise((resolve) => {
    child.on("exit", (code, signal) => {
      childExited = true;
      rejectPendingOnExit(describeChildExit("response handling", code, signal));
      resolve({ code, signal });
    });
  });

  child.on("error", (error) => {
    childExited = true;
    rejectPendingOnExit(`Failed to start Ruflo launcher: ${error.message}`);
  });

  function send(method, params = {}) {
    if (childExited) {
      return Promise.reject(new Error(describeChildExit(method, null, null)));
    }

    const id = nextId++;
    const payload = JSON.stringify({
      jsonrpc: "2.0",
      id,
      method,
      params,
    });

    child.stdin.write(`${payload}\n`);

    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        if (!pending.has(id)) {
          return;
        }
        pending.delete(id);
        reject(new Error(`Timed out waiting for ${method}`));
      }, 15000);

      pending.set(id, { resolve, reject, timer });
    });
  }

  try {
    await send("initialize", {});

    const systemInfo = parseToolText(await send("tools/call", {
      name: "system_info",
      arguments: {},
    }));
    const swarmInit = parseToolText(await send("tools/call", {
      name: "swarm_init",
      arguments: {
        topology: "hierarchical",
        maxAgents: 3,
        strategy: "balanced",
      },
    }));
    const taskCreate = parseToolText(await send("tools/call", {
      name: "task_create",
      arguments: {
        type: "research",
        description: "workspace smoke",
        priority: "low",
        tags: ["smoke"],
      },
    }));
    const memoryStore = parseToolText(await send("tools/call", {
      name: "memory_store",
      arguments: {
        key: "mirofish-ruflo-smoke",
        namespace: "default",
        value: JSON.stringify({ repo: "MiroFishES", ts: "2026-03-29" }),
        upsert: true,
      },
    }));

    const workspaceClaudeFlowEntries = await listDirectory(path.join(repoRoot, ".claude-flow"));
    const workspaceSwarmEntries = await listDirectory(path.join(repoRoot, ".swarm"));

    const checks = {
      system_info_cwd: createCheck(
        systemInfo.cwd === repoRoot,
        `system_info.cwd == ${repoRoot}`,
        { expected: repoRoot, actual: systemInfo.cwd ?? null },
      ),
      swarm_init: createCheck(
        swarmInit.success === true,
        "swarm_init succeeded",
        { actual: swarmInit.success ?? null },
      ),
      swarm_id: createCheck(
        Boolean(swarmInit.swarmId),
        "swarm_init returned swarmId",
        { actual: swarmInit.swarmId ?? null },
      ),
      task_create: createCheck(
        Boolean(taskCreate.taskId),
        "task_create returned taskId",
        { actual: taskCreate.taskId ?? null },
      ),
      workspace_claude_flow: createCheck(
        workspaceClaudeFlowEntries.includes("swarm") && workspaceClaudeFlowEntries.includes("tasks"),
        "workspace .claude-flow contains swarm and tasks state",
        { entries: workspaceClaudeFlowEntries },
      ),
      workspace_swarm: createCheck(
        workspaceSwarmEntries.includes("memory.db") && workspaceSwarmEntries.includes("schema.sql"),
        "workspace .swarm contains memory state files",
        { entries: workspaceSwarmEntries },
      ),
      root_claude_flow_absent: createCheck(
        !(await pathExists(rootClaudeFlowDir)),
        "root /.claude-flow was not created",
      ),
      root_swarm_absent: createCheck(
        !(await pathExists(rootSwarmDir)),
        "root /.swarm was not created",
      ),
    };

    const memoryReady = memoryStore.success === true;
    const knownMemoryBlocker =
      typeof memoryStore.error === "string" &&
      memoryStore.error.includes("Cannot find package 'sql.js'");

    checks.memory_store = createCheck(
      memoryReady,
      "memory_store succeeded",
      {
        expected_blocker: knownMemoryBlocker,
        error: memoryStore.error ?? null,
      },
    );

    const coreReady = Object.entries(checks)
      .filter(([key]) => key !== "memory_store")
      .every(([, check]) => check.ok);

    const unexpectedMemoryFailure = !memoryReady && !knownMemoryBlocker;
    const rufloReady = coreReady ? "swarm-task-only" : "fallback-required";

    let reason;
    if (!coreReady) {
      const failedLabels = Object.entries(checks)
        .filter(([key, check]) => key !== "memory_store" && !check.ok)
        .map(([, check]) => check.label);
      reason = `Repo-owned Ruflo swarm/task verification failed: ${failedLabels.join("; ")}`;
    } else if (memoryReady) {
      reason = "Repo-owned Ruflo launcher is workspace-safe and memory is ready.";
    } else if (knownMemoryBlocker) {
      reason = "Repo-owned Ruflo launcher is workspace-safe for swarm/task orchestration. Memory remains blocked by the external Ruflo sql.js dependency.";
    } else {
      reason = `Repo-owned Ruflo launcher is workspace-safe for swarm/task orchestration, but memory failed unexpectedly: ${memoryStore.error ?? "unknown error"}`;
    }

    const exitOk = coreReady && !unexpectedMemoryFailure && (!strictMemory || memoryReady);
    const summary = {
      repo_root: repoRoot,
      ruflo_ready: rufloReady,
      memory_ready: memoryReady,
      exit_ok: exitOk,
      reason,
      checks,
    };

    printSummary(summary);

    if (!exitOk) {
      process.exitCode = 1;
    }
  } finally {
    for (const entry of pending.values()) {
      clearTimeout(entry.timer);
    }
    pending.clear();
    await terminateChild(child, exitPromise);
    await cleanupTransientState();
  }
}

main().catch((error) => {
  const summary = buildFailureSummary(error.message);
  printSummary(summary);
  process.exit(1);
});
