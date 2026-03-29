import { execFileSync, spawnSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { expect, test } from '@playwright/test'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const repoRoot = path.resolve(__dirname, '..', '..')
const fixtureOutputDir = path.join(repoRoot, 'output', 'playwright', 'fixtures')
const fixtureScriptPath = path.join(
  repoRoot,
  'backend',
  'scripts',
  'create_probabilistic_smoke_fixture.py'
)

const buildPythonPath = () => {
  const existing = process.env.PYTHONPATH
  const paths = [path.join(repoRoot, 'backend')]
  if (existing) {
    paths.push(existing)
  }
  return paths.join(path.delimiter)
}

const resolvePythonLauncher = () => {
  const uvProbe = spawnSync('uv', ['--version'], {
    cwd: repoRoot,
    stdio: 'ignore'
  })
  if (uvProbe.status === 0) {
    return {
      command: 'uv',
      baseArgs: ['run', 'python'],
      cwd: path.join(repoRoot, 'backend'),
      scriptPath: path.join('scripts', 'create_probabilistic_smoke_fixture.py'),
      env: { ...process.env }
    }
  }

  const venvPythonPath = path.join(repoRoot, 'backend', '.venv', 'bin', 'python')
  if (fs.existsSync(venvPythonPath)) {
    return {
      command: venvPythonPath,
      baseArgs: [],
      cwd: repoRoot,
      scriptPath: fixtureScriptPath,
      env: {
        ...process.env,
        PYTHONPATH: buildPythonPath()
      }
    }
  }

  return {
    command: 'python3',
    baseArgs: [],
    cwd: repoRoot,
    scriptPath: fixtureScriptPath,
    env: {
      ...process.env,
      PYTHONPATH: buildPythonPath()
    }
  }
}

const seedFixture = ({
  fixtureName,
  seedCompletedReport = false
} = {}) => {
  fs.mkdirSync(fixtureOutputDir, { recursive: true })
  const outputFile = path.join(fixtureOutputDir, `${fixtureName}.json`)
  const launcher = resolvePythonLauncher()
  const args = [
    launcher.scriptPath,
    '--project-name',
    `Playwright ${fixtureName}`,
    '--graph-id',
    '',
    '--run-count',
    '2',
    '--root-seed',
    '101',
    '--output-file',
    outputFile
  ]

  if (seedCompletedReport) {
    args.push('--seed-completed-report', '--report-run-id', '0001')
  }

  execFileSync(launcher.command, [...launcher.baseArgs, ...args], {
    cwd: launcher.cwd,
    env: launcher.env,
    stdio: 'pipe'
  })

  return JSON.parse(fs.readFileSync(outputFile, 'utf-8'))
}

const formatHistorySimulationId = (simulationId) => {
  const prefix = simulationId.replace('sim_', '').slice(0, 6)
  return `SIM_${prefix.toUpperCase()}`
}

test.describe('probabilistic runtime smoke', () => {
  let fixture
  let alternateFixture

  test.beforeAll(() => {
    fixture = seedFixture({
      fixtureName: 'probabilistic-runtime-primary',
      seedCompletedReport: true
    })
    alternateFixture = seedFixture({
      fixtureName: 'probabilistic-runtime-secondary',
      seedCompletedReport: true
    })
  })

  test('Step 2 shows prepared probabilistic artifacts', async ({ page }) => {
    await page.goto(fixture.simulation_route)

    await expect(page.getByTestId('probabilistic-prepared-summary')).toBeVisible()
    await expect(page.getByText('Prepared Artifact Summary')).toBeVisible()
    await expect(
      page.getByTestId('probabilistic-prepared-summary').getByText('Grounding', { exact: true })
    ).toBeVisible()
    await expect(
      page.getByTestId('probabilistic-prepared-summary').getByText('Run-varying')
    ).toBeVisible()
  })

  test('Step 3 surfaces a missing probabilistic handoff honestly', async ({ page }) => {
    await page.goto(`/simulation/${fixture.simulation_id}/start?mode=probabilistic`)

    await expect(
      page.locator('.probabilistic-error').filter({
        hasText:
          'Probabilistic Step 3 requires both ensemble and run identifiers from Step 2. Return to Step 2 and recreate the stored run shell.'
      })
    ).toBeVisible()
  })

  test('Step 3 loads a stored probabilistic run shell and observed analytics', async ({ page }) => {
    await page.goto(
      `/simulation/${fixture.simulation_id}/start?mode=probabilistic&ensembleId=${fixture.ensemble.ensemble_id}&runId=${fixture.report.run_id}&scope=run`
    )

    await expect(page.getByTestId('probabilistic-step3-shell')).toBeVisible()
    await expect(page.getByTestId('probabilistic-analytics-card')).toBeVisible()
    await expect(page.getByTestId('probabilistic-start-button')).toContainText('Retry selected run')
    await expect(page.getByTestId('probabilistic-cleanup-button')).toBeVisible()
    await expect(page.getByTestId('probabilistic-rerun-button')).toBeVisible()
    await expect(page.getByTestId('probabilistic-operator-guidance')).toContainText('Create child rerun')
    await expect(
      page.locator('.probabilistic-status-panel').filter({
        hasText: `Stored run ${fixture.report.run_id}`
      })
    ).toBeVisible()
    await expect(
      page
        .getByTestId('probabilistic-report-scope-panel')
        .locator('.probabilistic-card-meta.mono')
        .filter({ hasText: 'RUN' })
    ).toBeVisible()
  })

  test('Step 4 shows the observed empirical report addendum', async ({ page }) => {
    await page.goto(fixture.report.report_route)

    await expect(page.getByTestId('probabilistic-report-context')).toBeVisible()
    await expect(page.getByText('Observed Forecast Context')).toBeVisible()
    await expect(page.getByText('Empirical report addendum')).toBeVisible()
    await expect(page.getByText('Upstream Grounding')).toBeVisible()
    await expect(page.getByTestId('probabilistic-compare-workspace')).toBeVisible()
    await page.getByTestId('probabilistic-compare-option').first().click()
    await expect(page.getByTestId('probabilistic-compare-handoff')).toBeVisible()
    await expect(page.getByTestId('probabilistic-compare-scope-identity')).toHaveCount(2)
  })

  test('Step 5 shows scoped probabilistic report-agent support explicitly bounded', async ({ page }) => {
    await page.goto(fixture.report.interaction_route)

    await expect(page.getByTestId('probabilistic-step5-banner')).toBeVisible()
    await expect(
      page.getByText('Scoped probabilistic context available')
    ).toBeVisible()
    await expect(page.getByTestId('probabilistic-step5-scope-control')).toBeVisible()
    await expect(
      page.getByTestId('probabilistic-step5-evidence').getByText(/Grounding/i)
    ).toBeVisible()
  })

  test('Step 4 compare handoff opens Step 5 with a selected bounded compare', async ({ page }) => {
    await page.goto(fixture.report.report_route)

    await page.getByTestId('probabilistic-compare-option').first().click()
    await page.getByTestId('probabilistic-compare-handoff').click()

    await expect(page).toHaveURL(/compareId=/)
    await expect(page.getByTestId('probabilistic-step5-compare')).toBeVisible()
  })

  test('history can reopen Step 3 from a saved probabilistic report', async ({ page }) => {
    await page.goto('/')

    const historyToggle = page.getByTestId('history-expand-toggle')
    const historyCard = page.getByTestId(
      `history-card--${fixture.simulation_id}--${fixture.report.report_id}`
    )

    await expect(historyCard).toBeVisible()
    await expect(historyToggle).toBeVisible()

    if ((await historyToggle.getAttribute('aria-expanded')) !== 'true') {
      await historyToggle.click()
    }

    await expect(historyToggle).toHaveAttribute('aria-expanded', 'true')
    await historyCard.click()

    await expect(page.locator('.modal-content')).toBeVisible()
    await page
      .getByTestId(
        `history-action-step3--${fixture.simulation_id}--${fixture.report.report_id}`
      )
      .click()

    await expect(page).toHaveURL(new RegExp(`/simulation/${fixture.simulation_id}/start`))
    await expect(page).toHaveURL(/mode=probabilistic/)
    await expect(page).toHaveURL(new RegExp(`ensembleId=${fixture.ensemble.ensemble_id}`))
    await expect(page).toHaveURL(/scope=run/)
    await expect(page).toHaveURL(new RegExp(`runId=${fixture.report.run_id}`))
    await expect(page.getByTestId('probabilistic-step3-shell')).toBeVisible()
    await expect(
      page.locator('.probabilistic-status-panel').filter({
        hasText: `Stored run ${fixture.report.run_id}`
      })
    ).toBeVisible()
    await expect(
      page
        .getByTestId('probabilistic-report-scope-panel')
        .locator('.probabilistic-card-meta.mono')
        .filter({ hasText: 'RUN' })
    ).toBeVisible()
  })

  test('history can reopen Step 5 from a saved report', async ({ page }) => {
    await page.goto('/')

    const historyToggle = page.getByTestId('history-expand-toggle')
    const historyCard = page.getByTestId(
      `history-card--${fixture.simulation_id}--${fixture.report.report_id}`
    )
    const alternateHistoryCard = page.getByTestId(
      `history-card--${alternateFixture.simulation_id}--${alternateFixture.report.report_id}`
    )

    await expect(alternateHistoryCard).toBeVisible()
    await expect(historyCard).toBeVisible()
    await expect(historyToggle).toBeVisible()

    if ((await historyToggle.getAttribute('aria-expanded')) !== 'true') {
      await historyToggle.click()
    }

    await expect(historyToggle).toHaveAttribute('aria-expanded', 'true')
    await historyCard.click()

    await expect(page.locator('.modal-content')).toBeVisible()
    await page
      .getByTestId(
        `history-action-step5--${fixture.simulation_id}--${fixture.report.report_id}`
      )
      .click()

    await expect(page).toHaveURL(new RegExp(`/interaction/${fixture.report.report_id}$`))
    await expect(page.getByTestId('probabilistic-step5-banner')).toBeVisible()
  })
})
