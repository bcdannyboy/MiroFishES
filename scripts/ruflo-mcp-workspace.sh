#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
WORKSPACE_ROOT="${RUFLO_WORKSPACE_ROOT:-${REPO_ROOT}}"
RUFLO_BIN="${RUFLO_BIN:-/Users/danielbloom/Desktop/ruflo/v3/@claude-flow/cli/bin/cli.js}"

if [[ ! -f "${RUFLO_BIN}" ]]; then
  echo "Missing Ruflo CLI at ${RUFLO_BIN}. Set RUFLO_BIN to a repo-local or installed Ruflo CLI path before running this launcher." >&2
  exit 1
fi

cd "${WORKSPACE_ROOT}"

export npm_config_update_notifier="${npm_config_update_notifier:-false}"
export CLAUDE_FLOW_MODE="${CLAUDE_FLOW_MODE:-v3}"
export CLAUDE_FLOW_HOOKS_ENABLED="${CLAUDE_FLOW_HOOKS_ENABLED:-true}"

exec node "${RUFLO_BIN}" mcp start
