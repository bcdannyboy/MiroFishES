#!/usr/bin/env bash

set -uo pipefail

declare -a STEP_RESULTS=()
FAILURES=0
ARTIFACT_SCAN_FAILED=0
SMOKE_FAILED=0

print_step_header() {
  local label="$1"
  printf '\n== %s ==\n' "$label"
}

record_pass() {
  local label="$1"
  STEP_RESULTS+=("PASS|${label}")
}

record_fail() {
  local label="$1"
  local exit_code="$2"
  STEP_RESULTS+=("FAIL|${label}|${exit_code}")
  FAILURES=$((FAILURES + 1))

  if [[ "$label" == "Forecast artifact conformance scan" ]]; then
    ARTIFACT_SCAN_FAILED=1
  fi

  if [[ "$label" == "Fixture-backed forecasting smoke verification" ]]; then
    SMOKE_FAILED=1
  fi
}

run_step() {
  local label="$1"
  shift

  print_step_header "$label"
  if "$@"; then
    record_pass "$label"
  else
    local exit_code=$?
    printf 'Step failed: %s (exit %s)\n' "$label" "$exit_code"
    record_fail "$label" "$exit_code"
  fi
}

printf 'Forecasting verification runs five evidence surfaces:\n'
printf '1. broad repo verify\n'
printf '2. targeted non-binary verify\n'
printf '3. confidence/report-context verify\n'
printf '4. active persisted artifact conformance scan\n'
printf '5. non-mutating smoke verify\n'

run_step "Broad repo verification" npm run verify
run_step "Targeted non-binary verification" npm run verify:nonbinary
run_step "Confidence verification" npm run verify:confidence
run_step "Forecast artifact conformance scan" npm run verify:forecasting:artifacts

printf '\nSmoke note: this step is non-mutating, but it still depends on Playwright being installed and on local ports 50141 and 41731 being available.\n'
run_step "Fixture-backed forecasting smoke verification" npm run verify:smoke

printf '\nVerification summary:\n'
for result in "${STEP_RESULTS[@]}"; do
  IFS='|' read -r status label exit_code <<<"$result"
  if [[ "$status" == "PASS" ]]; then
    printf '[PASS] %s\n' "$label"
  else
    printf '[FAIL] %s (exit %s)\n' "$label" "$exit_code"
  fi
done

if (( FAILURES > 0 )); then
  printf '\nverify:forecasting failed because one or more forecasting evidence surfaces failed.\n'
  if (( ARTIFACT_SCAN_FAILED > 0 )); then
    printf 'Artifact conformance failed: active non-archived simulations under backend/uploads/simulations still contain nonconforming forecasting artifacts.\n'
    printf 'For a full historical backlog audit, run npm run verify:forecasting:artifacts:all.\n'
    printf 'Archived historical simulations only pass the all-history scan when they are either remediated or explicitly quarantined as non-ready through forecast_archive historical_conformance metadata.\n'
  fi
  if (( SMOKE_FAILED > 0 )); then
    printf 'Smoke failed: common non-code blockers are missing Playwright browsers or occupied local ports 50141/41731, but product regressions are also possible and require reading the failing test output.\n'
  fi
  exit 1
fi

printf '\nverify:forecasting passed.\n'
printf 'Note: this wrapper gates the active artifact scan only. Archived historical backlog still requires npm run verify:forecasting:artifacts:all. Whole-history pass now requires either remediated artifacts or explicit historical_conformance quarantine for archived non-ready simulations, and those archived simulations remain read-only and non-ready.\n'
