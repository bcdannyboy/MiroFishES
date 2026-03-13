# Step 3 History And Local Ops Wave Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Let local operators reopen a truthful probabilistic Step 3 shell from History without compare scope, and publish a real local probabilistic operator runbook that names prerequisites, recovery paths, and evidence boundaries.

**Architecture:** Keep the runtime contract additive. Reuse the existing simulation-scoped ensemble APIs and Step 3 route-query contract instead of inventing a new history route. Add a frontend replay-target derivation helper, teach History to resolve and open the latest stored probabilistic shell, and publish a dedicated local operator runbook linked from the README. Then refresh the live March 8/March 10 control docs so H2, H5, and readiness language match the repo.

**Tech Stack:** Vue 3, Vue Router, Vite, Playwright, Node test runner, Markdown docs

---

### Task 1: Define History Replay Target Derivation

**Files:**
- Modify: `frontend/src/utils/probabilisticRuntime.js`
- Test: `frontend/tests/unit/probabilisticRuntime.test.mjs`

**Step 1: Write the failing test**

```javascript
test('deriveHistoryProbabilisticReplayTarget picks the newest replayable ensemble and best run', () => {
  assert.deepEqual(
    deriveHistoryProbabilisticReplayTarget({
      capabilityState: { runtimeEnabled: true },
      ensembles: [
        { ensemble_id: '0001', updated_at: '2026-03-10T09:00:00Z' },
        { ensemble_id: '0002', updated_at: '2026-03-10T10:00:00Z' }
      ],
      runsByEnsembleId: {
        '0002': [
          { run_id: '0004', status: 'completed' },
          { run_id: '0005', status: 'prepared' }
        ]
      }
    }),
    {
      status: 'ready',
      ensembleId: '0002',
      runId: '0005',
      helperText: ''
    }
  )
})
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && node --test tests/unit/probabilisticRuntime.test.mjs`
Expected: FAIL because `deriveHistoryProbabilisticReplayTarget` does not exist yet.

**Step 3: Write minimal implementation**

```javascript
export const deriveHistoryProbabilisticReplayTarget = ({
  capabilityState = {},
  ensembles = [],
  runsByEnsembleId = {}
} = {}) => {
  // Return explicit off-state when runtime shells are disabled.
  // Pick the newest ensemble by updated/created time, then select the best run
  // using the same status priority used by Step 3 selection recovery.
}
```

**Step 4: Run test to verify it passes**

Run: `cd frontend && node --test tests/unit/probabilisticRuntime.test.mjs`
Expected: PASS with the new replay-target coverage plus the existing runtime helper suite.

**Step 5: Commit**

```bash
git add frontend/src/utils/probabilisticRuntime.js frontend/tests/unit/probabilisticRuntime.test.mjs
git commit -m "feat: add probabilistic history replay target helper"
```

### Task 2: Add Step 3 History Re-entry In The History Modal

**Files:**
- Modify: `frontend/src/components/HistoryDatabase.vue`
- Modify: `frontend/src/api/simulation.js`
- Test: `tests/smoke/probabilistic-runtime.spec.mjs`
- Test: `frontend/tests/unit/probabilisticRuntime.test.mjs`

**Step 1: Write the failing test**

```javascript
test('history can reopen Step 3 from a probabilistic stored shell', async ({ page }) => {
  await page.goto('/')
  await page.getByTestId(`history-card--${fixture.simulation_id}--${fixture.report.report_id}`).click()
  await page.getByTestId(`history-action-step3--${fixture.simulation_id}--${fixture.report.report_id}`).click()
  await expect(page.getByTestId('probabilistic-step3-shell')).toBeVisible()
})
```

**Step 2: Run test to verify it fails**

Run: `npm run verify:smoke -- --grep "history can reopen Step 3 from a probabilistic stored shell"`
Expected: FAIL because the History modal does not yet expose Step 3 replay.

**Step 3: Write minimal implementation**

```vue
<!-- HistoryDatabase.vue -->
<!-- When a simulation card is opened, resolve the latest replayable probabilistic shell
     from existing ensemble endpoints. Expose a Step 3 button only when a truthful target exists. -->
```

Implementation notes:
- Reuse existing API helpers to list ensembles and fetch the selected ensemble status.
- Keep legacy Step 3 live-only semantics intact when no probabilistic replay target exists.
- Use explicit helper text for: runtime disabled, no stored ensembles, no stored runs, and fetch failure.
- Route to `/simulation/:simulationId/start?mode=probabilistic&ensembleId=...&runId=...`.

**Step 4: Run tests to verify they pass**

Run: `cd frontend && node --test tests/unit/probabilisticRuntime.test.mjs`
Expected: PASS with replay-target helper coverage.

Run: `npm run verify:smoke -- --grep "history can reopen Step 3 from a probabilistic stored shell"`
Expected: PASS with the new browser-level Step 3 history replay proof.

**Step 5: Commit**

```bash
git add frontend/src/components/HistoryDatabase.vue frontend/src/api/simulation.js frontend/tests/unit/probabilisticRuntime.test.mjs tests/smoke/probabilistic-runtime.spec.mjs
git commit -m "feat: add history-backed Step 3 probabilistic replay"
```

### Task 3: Publish The Local Probabilistic Operator Runbook

**Files:**
- Modify: `README.md`
- Create: `docs/local-probabilistic-operator-runbook.md`

**Step 1: Write the failing doc check**

```text
Search the repo for a user-facing local probabilistic operator runbook.
Expected before change: none exists outside PM/control docs.
```

**Step 2: Run the check to verify the gap**

Run: `rg -n "verify:operator:local|retry|rerun|cleanup|stuck run|Step 3 history" README.md docs -g '!docs/plans/*'`
Expected: the search returns little or no user-facing operator guidance.

**Step 3: Write minimal implementation**

```markdown
# Local Probabilistic Operator Runbook

- prerequisites and flags
- verification ladder (`npm run verify`, `npm run verify:smoke`, `PLAYWRIGHT_LIVE_ALLOW_MUTATION=true npm run verify:operator:local`)
- Step 1 through Step 5 local path
- Step 3 retry vs rerun vs cleanup
- stuck-run recovery
- evidence classes and current known limits
```

Implementation notes:
- README should link to the runbook and state that live Step 2 depends on LLM plus Zep prerequisites.
- The runbook must distinguish fixture-backed, local-only non-fixture, and release-grade evidence.
- Keep probability language empirical/observed/observational only.

**Step 4: Run the doc check to verify the new surface exists**

Run: `rg -n "verify:operator:local|retry|rerun|cleanup|stuck run|Step 3 history" README.md docs/local-probabilistic-operator-runbook.md`
Expected: matches in the README and the new runbook.

**Step 5: Commit**

```bash
git add README.md docs/local-probabilistic-operator-runbook.md
git commit -m "docs: add local probabilistic operator runbook"
```

### Task 4: Refresh PM Truth And Verification Evidence

**Files:**
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-status-audit.md`
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-readiness-dashboard.md`
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-execution-log.md`
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-decision-log.md`
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-gate-evidence-ledger.md`
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-frontend-task-register.md`
- Modify: `docs/plans/2026-03-08-stochastic-probabilistic-integration-task-register.md`
- Modify: `docs/plans/2026-03-10-hybrid-h2-truthful-local-hardening-wave.md`

**Step 1: Write the failing truth checklist**

```text
Checklist:
- Step 3 history/re-entry is still described as absent.
- No user-facing local operator runbook is linked from README.
- H2/H5 truth still lacks this wave's evidence and limits.
```

**Step 2: Verify the checklist is currently true**

Run: `rg -n "Step 3 history|runbook|README|history re-entry|live-only" docs/plans/2026-03-08-stochastic-probabilistic-status-audit.md docs/plans/2026-03-08-stochastic-probabilistic-readiness-dashboard.md docs/plans/2026-03-08-stochastic-probabilistic-frontend-task-register.md docs/plans/2026-03-08-stochastic-probabilistic-integration-task-register.md docs/plans/2026-03-10-hybrid-h2-truthful-local-hardening-wave.md`
Expected: the current docs still describe Step 3 history/re-entry and runbook gaps more narrowly than the post-wave repo will.

**Step 3: Write minimal implementation**

```markdown
- record the new Step 3 history-backed replay boundary
- record the new local operator runbook path
- keep compare out of MVP
- keep 100% local readiness unclaimed until broader gaps close
```

**Step 4: Run verification after docs and code land**

Run: `npm run verify`
Expected: PASS with frontend build + frontend tests + backend tests.

Run: `npm run verify:smoke`
Expected: PASS including the new Step 3 history replay smoke.

Run: `PLAYWRIGHT_LIVE_ALLOW_MUTATION=true npm run verify:operator:local`
Expected: PASS and refresh `output/playwright/live-operator/latest.json` with a new local-only non-fixture operator capture.

**Step 5: Commit**

```bash
git add docs/plans/2026-03-08-stochastic-probabilistic-status-audit.md docs/plans/2026-03-08-stochastic-probabilistic-readiness-dashboard.md docs/plans/2026-03-08-stochastic-probabilistic-execution-log.md docs/plans/2026-03-08-stochastic-probabilistic-decision-log.md docs/plans/2026-03-08-stochastic-probabilistic-gate-evidence-ledger.md docs/plans/2026-03-08-stochastic-probabilistic-frontend-task-register.md docs/plans/2026-03-08-stochastic-probabilistic-integration-task-register.md docs/plans/2026-03-10-hybrid-h2-truthful-local-hardening-wave.md
git commit -m "docs: refresh history replay and local ops truth"
```
