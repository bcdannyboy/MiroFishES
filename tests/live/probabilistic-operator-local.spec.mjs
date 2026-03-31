import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { expect, test } from '@playwright/test'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const repoRoot = path.resolve(__dirname, '..', '..')
const liveEvidenceDir = path.join(repoRoot, 'output', 'playwright', 'live-operator')
const simulationsRoot = path.join(repoRoot, 'backend', 'uploads', 'simulations')
const reportsRoot = path.join(repoRoot, 'backend', 'uploads', 'reports')
const smokeFixtureMarkerFilename = 'probabilistic_smoke_fixture.json'
const actionTimeout = 30_000
const readinessTimeout = 5_000
const reportTimeout = 300_000
const liveStep45Timeout = 600_000
const liveBackendPort = process.env.PLAYWRIGHT_BACKEND_PORT || '50141'
const liveBackendBaseURL = process.env.PLAYWRIGHT_BACKEND_BASE_URL || `http://127.0.0.1:${liveBackendPort}`

const safeReadJson = (filePath) => {
  try {
    return JSON.parse(fs.readFileSync(filePath, 'utf-8'))
  } catch {
    return null
  }
}

const isProbabilisticPrepared = (snapshot) => {
  if (!snapshot || typeof snapshot !== 'object') {
    return false
  }
  if (snapshot.probabilistic_mode === true) {
    return true
  }
  if (typeof snapshot.mode === 'string' && snapshot.mode.trim() === 'probabilistic') {
    return true
  }
  const preparedSummary = snapshot.prepared_artifact_summary
  if (!preparedSummary || typeof preparedSummary !== 'object') {
    return false
  }
  return (
    preparedSummary.probabilistic_mode === true
    || (typeof preparedSummary.mode === 'string' && preparedSummary.mode.trim() === 'probabilistic')
  )
}

const readLiveSimulationRecord = (simulationId) => {
  if (!simulationId) {
    return null
  }

  const simulationDir = path.join(simulationsRoot, simulationId)
  if (!fs.existsSync(simulationDir) || !fs.statSync(simulationDir).isDirectory()) {
    return null
  }
  if (fs.existsSync(path.join(simulationDir, smokeFixtureMarkerFilename))) {
    return null
  }
  if (fs.existsSync(path.join(simulationDir, 'forecast_archive.json'))) {
    return null
  }

  const preparedSnapshot = safeReadJson(path.join(simulationDir, 'prepared_snapshot.json'))
  const groundingBundle = safeReadJson(path.join(simulationDir, 'grounding_bundle.json'))
  const state = safeReadJson(path.join(simulationDir, 'state.json'))
  const configReasoning = typeof state?.config_reasoning === 'string'
    ? state.config_reasoning
    : ''
  const sourceRequirement = groundingBundle?.source_summary?.simulation_requirement

  return {
    simulationId,
    createdAt: state?.created_at || state?.updated_at || null,
    preparedGrounded: (
      isProbabilisticPrepared(preparedSnapshot)
      && groundingBundle?.status === 'ready'
      && !configReasoning.includes('Synthetic smoke-fixture configuration')
      && !(
        typeof sourceRequirement === 'string'
        && sourceRequirement.includes('Smoke-test the probabilistic Step 2 to Step 3 handoff')
      )
    )
  }
}

const listLiveSimulationCandidates = () => {
  if (!fs.existsSync(simulationsRoot)) {
    return []
  }

  const candidates = []
  for (const entry of fs.readdirSync(simulationsRoot)) {
    if (!entry || entry.startsWith('.')) {
      continue
    }

    const record = readLiveSimulationRecord(entry)
    if (!record?.preparedGrounded) {
      continue
    }
    candidates.push(record)
  }

  candidates.sort((left, right) => {
    const leftKey = left.createdAt || ''
    const rightKey = right.createdAt || ''
    return rightKey.localeCompare(leftKey) || right.simulationId.localeCompare(left.simulationId)
  })

  return candidates
}

const resolveLiveSimulationSelection = () => {
  if (process.env.PLAYWRIGHT_LIVE_SIMULATION_ID) {
    return {
      simulationId: process.env.PLAYWRIGHT_LIVE_SIMULATION_ID,
      source: 'env'
    }
  }

  const candidates = listLiveSimulationCandidates()
  if (candidates.length === 0) {
    return {
      simulationId: null,
      source: 'auto',
      reason: fs.existsSync(simulationsRoot)
        ? 'No active prepared-and-grounded simulation was found under backend/uploads/simulations.'
        : `No simulation storage root found at ${simulationsRoot}`
    }
  }

  return {
    simulationId: candidates[0].simulationId,
    source: 'auto'
  }
}

const resolvedSimulationSelection = resolveLiveSimulationSelection()
const defaultSimulationId = resolvedSimulationSelection.simulationId

const hasSavedReportInferenceEvidence = (probabilisticContext) => {
  if (!probabilisticContext || typeof probabilisticContext !== 'object') {
    return false
  }

  const selectedRun = probabilisticContext.selected_run
  const simulationMarket = (
    selectedRun
    && typeof selectedRun === 'object'
    && selectedRun.simulation_market
    && typeof selectedRun.simulation_market === 'object'
  )
    ? selectedRun.simulation_market
    : null
  const answerPayload = (
    probabilisticContext.forecast_workspace
    && typeof probabilisticContext.forecast_workspace === 'object'
    && probabilisticContext.forecast_workspace.forecast_answer
    && typeof probabilisticContext.forecast_workspace.forecast_answer === 'object'
    && probabilisticContext.forecast_workspace.forecast_answer.answer_payload
    && typeof probabilisticContext.forecast_workspace.forecast_answer.answer_payload === 'object'
  )
    ? probabilisticContext.forecast_workspace.forecast_answer.answer_payload
    : null

  return Boolean(
    probabilisticContext.simulation_market_summary
    && probabilisticContext.signal_provenance_summary
    && simulationMarket?.market_snapshot
    && answerPayload?.best_estimate
  )
}

const listCompletedProbabilisticReportScopes = ({ simulationId = null } = {}) => {
  if (!fs.existsSync(reportsRoot)) {
    return []
  }

  const reportScopes = []
  for (const entry of fs.readdirSync(reportsRoot)) {
    if (!entry || entry.startsWith('.') || entry.startsWith('smoke-')) {
      continue
    }

    const reportDir = path.join(reportsRoot, entry)
    if (!fs.statSync(reportDir).isDirectory()) {
      continue
    }

    const meta = safeReadJson(path.join(reportDir, 'meta.json'))
    if (!meta || meta.status !== 'completed') {
      continue
    }
    if (simulationId && meta.simulation_id !== simulationId) {
      continue
    }

    const simulationRecord = readLiveSimulationRecord(meta.simulation_id)
    if (!simulationRecord) {
      continue
    }

    const probabilisticContext = (
      meta.probabilistic_context
      && typeof meta.probabilistic_context === 'object'
    )
      ? meta.probabilistic_context
      : null
    if (!probabilisticContext) {
      continue
    }
    if (!hasSavedReportInferenceEvidence(probabilisticContext)) {
      continue
    }
    const ensembleId = meta.ensemble_id || probabilisticContext?.ensemble_id || null
    if (!ensembleId) {
      continue
    }

    reportScopes.push({
      source: 'saved-report',
      simulationId: meta.simulation_id,
      reportId: entry,
      ensembleId,
      clusterId: meta.cluster_id || probabilisticContext?.cluster_id || null,
      runId: meta.run_id || probabilisticContext?.run_id || null,
      createdAt: meta.completed_at || meta.created_at || null
    })
  }

  reportScopes.sort((left, right) => {
    const leftRunScoped = left.runId ? 1 : 0
    const rightRunScoped = right.runId ? 1 : 0
    if (rightRunScoped !== leftRunScoped) {
      return rightRunScoped - leftRunScoped
    }
    const leftKey = left.createdAt || ''
    const rightKey = right.createdAt || ''
    return rightKey.localeCompare(leftKey) || right.reportId.localeCompare(left.reportId)
  })

  return reportScopes
}

const listCompletedRunScopeCandidates = (simulationId) => {
  if (!simulationId) {
    return []
  }

  const simulationDir = path.join(simulationsRoot, simulationId)
  const ensembleRoot = path.join(simulationDir, 'ensemble')
  if (!fs.existsSync(ensembleRoot)) {
    return []
  }

  const runScopes = []
  for (const ensembleEntry of fs.readdirSync(ensembleRoot)) {
    if (!ensembleEntry.startsWith('ensemble_')) {
      continue
    }

    const ensembleDir = path.join(ensembleRoot, ensembleEntry)
    if (!fs.statSync(ensembleDir).isDirectory()) {
      continue
    }

    const ensembleId = ensembleEntry.replace(/^ensemble_/, '')
    const runsDir = path.join(ensembleDir, 'runs')
    if (!fs.existsSync(runsDir)) {
      continue
    }

    for (const runEntry of fs.readdirSync(runsDir)) {
      if (!runEntry.startsWith('run_')) {
        continue
      }

      const runDir = path.join(runsDir, runEntry)
      if (!fs.statSync(runDir).isDirectory()) {
        continue
      }

      const runState = safeReadJson(path.join(runDir, 'run_state.json'))
      const runManifest = safeReadJson(path.join(runDir, 'run_manifest.json'))
      if (runState?.runner_status !== 'completed' || runManifest?.status !== 'completed') {
        continue
      }
      const marketManifest = safeReadJson(path.join(runDir, 'simulation_market_manifest.json'))
      if (
        !marketManifest
        || marketManifest.extraction_status !== 'ready'
        || marketManifest.forecast_workspace_linked !== true
        || marketManifest.scope_linked_to_run !== true
      ) {
        continue
      }

      const graphId = (
        runManifest?.base_graph_id
        || runManifest?.graph_id
        || runState?.base_graph_id
        || runState?.graph_id
      )
      if (!graphId) {
        continue
      }

      const hasRunMetrics = fs.existsSync(path.join(runDir, 'metrics.json'))
      const hasEnsembleAnalytics = (
        fs.existsSync(path.join(ensembleDir, 'aggregate_summary.json'))
        || fs.existsSync(path.join(ensembleDir, 'scenario_clusters.json'))
      )
      if (!hasRunMetrics && !hasEnsembleAnalytics) {
        continue
      }

      runScopes.push({
        source: 'completed-run',
        simulationId,
        reportId: null,
        ensembleId,
        clusterId: null,
        runId: runEntry.replace(/^run_/, ''),
        scopeLinkedToRun: marketManifest.scope_linked_to_run === true,
        createdAt: (
          runState?.completed_at
          || runManifest?.completed_at
          || runManifest?.updated_at
          || runManifest?.generated_at
          || null
        )
      })
    }
  }

  runScopes.sort((left, right) => {
    const leftRunLinked = left.scopeLinkedToRun ? 1 : 0
    const rightRunLinked = right.scopeLinkedToRun ? 1 : 0
    if (rightRunLinked !== leftRunLinked) {
      return rightRunLinked - leftRunLinked
    }
    const leftKey = left.createdAt || ''
    const rightKey = right.createdAt || ''
    return rightKey.localeCompare(leftKey) || right.runId.localeCompare(left.runId)
  })

  return runScopes
}

const resolveLiveProbabilisticReportScope = (simulationId) => {
  if (!simulationId) {
    return {
      source: 'auto',
      reportId: null,
      reason: 'No live simulation was selected for report verification.'
    }
  }

  const savedReportScopes = listCompletedProbabilisticReportScopes({ simulationId })
  if (savedReportScopes.length > 0) {
    return savedReportScopes[0]
  }

  const completedRunScopes = listCompletedRunScopeCandidates(simulationId)
  if (completedRunScopes.length > 0) {
    return completedRunScopes[0]
  }

  return {
    source: 'auto',
    reportId: null,
    reason: (
      `No completed live probabilistic report scope or report-generatable completed `
      + `run scope was found for ${simulationId}.`
    )
  }
}

const resolveLiveStep45Selection = () => {
  const preferFreshGeneration = process.env.PLAYWRIGHT_LIVE_ALLOW_MUTATION === 'true'

  if (process.env.PLAYWRIGHT_LIVE_SIMULATION_ID) {
    const envSimulationId = process.env.PLAYWRIGHT_LIVE_SIMULATION_ID
    const reportScopeSelection = resolveLiveProbabilisticReportScope(envSimulationId)
    return {
      simulationId: reportScopeSelection.simulationId || envSimulationId,
      simulationSelection: {
        simulationId: envSimulationId,
        source: 'env'
      },
      reportScopeSelection
    }
  }

  if (resolvedSimulationSelection.simulationId) {
    const preferredSelection = resolveLiveProbabilisticReportScope(
      resolvedSimulationSelection.simulationId
    )
    if (preferredSelection.ensembleId) {
      return {
        simulationId: preferredSelection.simulationId || resolvedSimulationSelection.simulationId,
        simulationSelection: resolvedSimulationSelection,
        reportScopeSelection: preferredSelection
      }
    }
  }

  const simulationCandidates = listLiveSimulationCandidates()
  if (!preferFreshGeneration) {
    const savedReportScopes = listCompletedProbabilisticReportScopes()
    if (savedReportScopes.length > 0) {
      return {
        simulationId: savedReportScopes[0].simulationId,
        simulationSelection: {
          simulationId: savedReportScopes[0].simulationId,
          source: 'saved-report-catalog'
        },
        reportScopeSelection: savedReportScopes[0]
      }
    }
  }

  if (simulationCandidates.length === 0) {
    return {
      simulationId: null,
      simulationSelection: resolvedSimulationSelection,
      reportScopeSelection: {
        source: 'auto',
        reportId: null,
        reason: resolvedSimulationSelection.reason
          || 'No active prepared-and-grounded simulation was available for Step 4/5 verification.'
      }
    }
  }

  const reasons = []
  for (const candidate of simulationCandidates) {
    if (candidate.simulationId === resolvedSimulationSelection.simulationId) {
      continue
    }
    const reportScopeSelection = resolveLiveProbabilisticReportScope(candidate.simulationId)
    if (reportScopeSelection.ensembleId) {
      return {
        simulationId: candidate.simulationId,
        simulationSelection: candidate,
        reportScopeSelection
      }
    }
    reasons.push(`${candidate.simulationId}: ${reportScopeSelection.reason}`)
  }

  return {
    simulationId: resolvedSimulationSelection.simulationId || simulationCandidates[0].simulationId,
    simulationSelection: resolvedSimulationSelection.simulationId
      ? resolvedSimulationSelection
      : simulationCandidates[0],
    reportScopeSelection: {
      source: 'auto',
      reportId: null,
      reason: reasons.join(' | ')
    }
  }
}

const delay = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds))

const readLiveRunScopeEvidence = ({ simulationId, ensembleId, runId }) => {
  if (!simulationId || !ensembleId || !runId) {
    return null
  }

  const runDir = path.join(
    simulationsRoot,
    simulationId,
    'ensemble',
    `ensemble_${ensembleId}`,
    'runs',
    `run_${runId}`
  )
  if (!fs.existsSync(runDir) || !fs.statSync(runDir).isDirectory()) {
    return null
  }

  const runState = safeReadJson(path.join(runDir, 'run_state.json'))
  const runManifest = safeReadJson(path.join(runDir, 'run_manifest.json'))
  const marketManifest = safeReadJson(path.join(runDir, 'simulation_market_manifest.json'))
  const marketSnapshot = safeReadJson(path.join(runDir, 'market_snapshot.json'))
  const metrics = safeReadJson(path.join(runDir, 'metrics.json'))
  const actionLogPaths = ['twitter', 'reddit']
    .map((platform) => ({
      platform,
      relativePath: `${platform}/actions.jsonl`,
      absolutePath: path.join(runDir, platform, 'actions.jsonl')
    }))
    .filter((entry) => fs.existsSync(entry.absolutePath) && fs.statSync(entry.absolutePath).size > 0)
    .map((entry) => entry.relativePath)
  const signalCounts = marketManifest?.signal_counts || {}
  const hasExtractedSignals = (
    (signalCounts.agent_beliefs || 0) > 0
    || (signalCounts.belief_updates || 0) > 0
  )

  return {
    simulationId,
    ensembleId,
    runId,
    runDir,
    runState,
    runManifest,
    marketManifest,
    marketSnapshot,
    metrics,
    actionLogPaths,
    ready: Boolean(
      runState?.runner_status === 'completed'
      && runManifest?.status === 'completed'
      && marketManifest?.extraction_status === 'ready'
      && marketManifest?.forecast_workspace_linked === true
      && marketManifest?.scope_linked_to_run === true
      && actionLogPaths.length > 0
      && hasExtractedSignals
      && marketSnapshot
      && metrics
    )
  }
}

const waitForLiveRunScopeEvidence = async (
  { simulationId, ensembleId, runId },
  {
    timeoutMs = liveStep45Timeout,
    pollIntervalMs = 2_000
  } = {}
) => {
  const deadline = Date.now() + timeoutMs
  let lastEvidence = readLiveRunScopeEvidence({ simulationId, ensembleId, runId })

  while (Date.now() < deadline) {
    lastEvidence = readLiveRunScopeEvidence({ simulationId, ensembleId, runId }) || lastEvidence
    if (lastEvidence?.ready) {
      return lastEvidence
    }
    await delay(pollIntervalMs)
  }

  const timeoutSummary = lastEvidence
    ? {
      runnerStatus: lastEvidence.runState?.runner_status || null,
      runStatus: lastEvidence.runManifest?.status || null,
      extractionStatus: lastEvidence.marketManifest?.extraction_status || null,
      forecastWorkspaceLinked: lastEvidence.marketManifest?.forecast_workspace_linked === true,
      scopeLinkedToRun: lastEvidence.marketManifest?.scope_linked_to_run === true,
      actionLogs: lastEvidence.actionLogPaths,
      signalCounts: lastEvidence.marketManifest?.signal_counts || null,
      hasMarketSnapshot: Boolean(lastEvidence.marketSnapshot),
      hasMetrics: Boolean(lastEvidence.metrics)
    }
    : null

  throw new Error(
    `Timed out waiting for live run-scoped report evidence ${simulationId}/${ensembleId}/${runId}: ${
      JSON.stringify(timeoutSummary)
    }`
  )
}

const buildEvidencePath = (basename = 'operator-pass', latestName = 'latest.json') => {
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-')
  return {
    latestPath: path.join(liveEvidenceDir, latestName),
    timestampedPath: path.join(liveEvidenceDir, `${basename}-${timestamp}.json`)
  }
}

const writeEvidence = (
  payload,
  {
    basename = 'operator-pass',
    latestName = 'latest.json'
  } = {}
) => {
  const normalizedPayload = {
    ...payload,
    completedAt: new Date().toISOString()
  }
  const { latestPath, timestampedPath } = buildEvidencePath(basename, latestName)
  fs.mkdirSync(liveEvidenceDir, { recursive: true })
  const serialized = JSON.stringify(normalizedPayload, null, 2)
  fs.writeFileSync(latestPath, serialized, 'utf-8')
  fs.writeFileSync(timestampedPath, serialized, 'utf-8')
}

const extractRouteIds = (urlString) => {
  const url = new URL(urlString)
  return {
    ensembleId: url.searchParams.get('ensembleId'),
    runId: url.searchParams.get('runId')
  }
}

const buildLiveBackendApiUrl = (pathname) => {
  const normalizedPath = pathname.startsWith('/') ? pathname : `/${pathname}`
  return new URL(normalizedPath, `${liveBackendBaseURL}/`).toString()
}

const isRelevantOperatorResponse = (response, simulationId) => {
  const url = response.url()
  return (
    url.includes(`/api/simulation/${simulationId}/ensembles`)
    || url.includes(`/api/simulation/${simulationId}/reports`)
  )
}

test.describe('local-only probabilistic operator pass', () => {
  test.skip(
    process.env.PLAYWRIGHT_LIVE_ALLOW_MUTATION !== 'true',
    'Set PLAYWRIGHT_LIVE_ALLOW_MUTATION=true to run the live mutating operator pass.'
  )

  test('Step 2 handoff and Step 3 recovery actions work on a live local simulation family', async ({ page }) => {
    const evidence = {
      evidenceClass: 'local-only non-fixture',
      mutationAllowed: process.env.PLAYWRIGHT_LIVE_ALLOW_MUTATION === 'true',
      simulationId: defaultSimulationId,
      simulationSelection: resolvedSimulationSelection,
      startedAt: new Date().toISOString(),
      operatorActions: [],
      network: [],
      console: [],
      pageErrors: []
    }

    page.on('console', (message) => {
      evidence.console.push({
        type: message.type(),
        text: message.text()
      })
    })

    page.on('pageerror', (error) => {
      evidence.pageErrors.push(String(error))
    })

    page.on('response', (response) => {
      if (!isRelevantOperatorResponse(response, defaultSimulationId)) {
        return
      }

      evidence.network.push({
        method: response.request().method(),
        status: response.status(),
        url: response.url()
      })
    })

    try {
      if (!defaultSimulationId) {
        throw new Error(
          `Live operator run could not select a prepared-and-grounded simulation: ${resolvedSimulationSelection.reason}`
        )
      }

      await page.goto(`/simulation/${defaultSimulationId}`)

      const handoffButton = page.getByRole('button', {
        name: /Create Step 3 stored run shell/i
      })
      const handoffHelper = page.locator('.action-group.dual .action-note').first()

      await expect(handoffButton).toBeVisible({ timeout: actionTimeout })

      try {
        await expect(handoffButton).toBeEnabled({ timeout: readinessTimeout })
      } catch (error) {
        const helperText = (await handoffHelper.allTextContents())
          .map((value) => value.trim())
          .find(Boolean) || ''
        let prepareStatus = null

        try {
          const prepareStatusResponse = await page.request.post('/api/simulation/prepare/status', {
            data: {
              simulation_id: defaultSimulationId
            }
          })
          prepareStatus = await prepareStatusResponse.json()
        } catch (statusError) {
          prepareStatus = {
            success: false,
            error: String(statusError)
          }
        }

        const prepareData = prepareStatus?.data && typeof prepareStatus.data === 'object'
          ? prepareStatus.data
          : {}
        const prepareInfo = prepareData.prepare_info && typeof prepareData.prepare_info === 'object'
          ? prepareData.prepare_info
          : {}
        const preparedArtifactSummary = (
          prepareInfo.prepared_artifact_summary
          && typeof prepareInfo.prepared_artifact_summary === 'object'
        )
          ? prepareInfo.prepared_artifact_summary
          : {}
        const forecastReadiness = (
          preparedArtifactSummary.forecast_readiness
          && typeof preparedArtifactSummary.forecast_readiness === 'object'
        )
          ? preparedArtifactSummary.forecast_readiness
          : {}
        const artifactCompleteness = (
          preparedArtifactSummary.artifact_completeness
          && typeof preparedArtifactSummary.artifact_completeness === 'object'
        )
          ? preparedArtifactSummary.artifact_completeness
          : {}
        const missingProbabilisticArtifacts = Array.isArray(
          preparedArtifactSummary.missing_probabilistic_artifacts
        )
          ? preparedArtifactSummary.missing_probabilistic_artifacts
          : []
        const derivedBlocker = (
          helperText
          || (typeof forecastReadiness.reason === 'string' ? forecastReadiness.reason.trim() : '')
          || (typeof artifactCompleteness.reason === 'string' ? artifactCompleteness.reason.trim() : '')
          || (missingProbabilisticArtifacts.length > 0
            ? `Missing probabilistic prepare artifacts: ${missingProbabilisticArtifacts.join(', ')}`
            : '')
          || (typeof prepareInfo.reason === 'string' ? prepareInfo.reason.trim() : '')
          || (typeof prepareData.message === 'string' ? prepareData.message.trim() : '')
          || 'Step 2 handoff stayed disabled without a visible blocker'
        )

        evidence.step2Readiness = {
          enabled: false,
          helperText: derivedBlocker,
          uiHelperText: helperText || null,
          prepareStatus: {
            status: prepareData.status || null,
            alreadyPrepared: prepareData.already_prepared === true,
            message: prepareData.message || null,
            reason: prepareInfo.reason || null,
            probabilisticMode: preparedArtifactSummary.probabilistic_mode === true,
            forecastReady: forecastReadiness.ready === true,
            missingProbabilisticArtifacts
          }
        }
        evidence.operatorActions.push({
          action: 'step2-handoff',
          result: 'blocked before mutation',
          helperText: derivedBlocker
        })
        throw new Error(
          `Live operator simulation ${defaultSimulationId} is not Step 3 ready: ${derivedBlocker}`
        )
      }

      const createEnsembleResponsePromise = page.waitForResponse((response) => {
        return (
          response.request().method() === 'POST'
          && response.url().includes(`/api/simulation/${defaultSimulationId}/ensembles`)
          && !response.url().includes('/cleanup')
        )
      })

      await handoffButton.click()

      const createEnsembleResponse = await createEnsembleResponsePromise
      expect(createEnsembleResponse.status()).toBe(200)

      await expect(
        page.getByTestId('probabilistic-step3-shell')
      ).toBeVisible({ timeout: actionTimeout })

      await expect(page).toHaveURL(
        new RegExp(`/simulation/${defaultSimulationId}/start\\?mode=probabilistic`)
      )

      const routeIds = extractRouteIds(page.url())
      expect(routeIds.ensembleId).toBeTruthy()
      expect(routeIds.runId).toBeTruthy()

      evidence.ensembleId = routeIds.ensembleId
      evidence.initialRunId = routeIds.runId
      evidence.operatorActions.push({
        action: 'step2-handoff',
        result: 'created ensemble and opened Step 3 shell',
        ensembleId: routeIds.ensembleId,
        runId: routeIds.runId,
        responseStatus: createEnsembleResponse.status()
      })

      const startButton = page.getByTestId('probabilistic-start-button')
      const cleanupButton = page.getByTestId('probabilistic-cleanup-button')
      const rerunButton = page.getByTestId('probabilistic-rerun-button')
      const stopButton = page.getByRole('button', { name: /Stop selected run/i })
      const operatorGuidance = page.getByTestId('probabilistic-operator-guidance')

      await expect(operatorGuidance).toContainText('Launch selected run starts this stored shell for the first time', {
        timeout: actionTimeout
      })
      await expect(startButton).toContainText('Launch selected run', { timeout: actionTimeout })
      await expect(stopButton).toBeDisabled()
      await expect(cleanupButton).toBeEnabled({ timeout: actionTimeout })
      await expect(rerunButton).toBeEnabled({ timeout: actionTimeout })

      const firstStartResponsePromise = page.waitForResponse((response) => {
        return (
          response.request().method() === 'POST'
          && response.url().includes(
            `/api/simulation/${defaultSimulationId}/ensembles/${routeIds.ensembleId}/runs/${routeIds.runId}/start`
          )
        )
      })

      await startButton.click()

      const firstStartResponse = await firstStartResponsePromise
      expect(firstStartResponse.status()).toBe(200)

      await expect(operatorGuidance).toContainText('Stop the active run before cleanup or child rerun', {
        timeout: actionTimeout
      })
      await expect(stopButton).toBeEnabled({ timeout: actionTimeout })

      evidence.operatorActions.push({
        action: 'launch',
        result: 'selected run launched from prepared shell',
        runId: routeIds.runId,
        responseStatus: firstStartResponse.status()
      })

      const firstStopResponsePromise = page.waitForResponse((response) => {
        return (
          response.request().method() === 'POST'
          && response.url().includes(
            `/api/simulation/${defaultSimulationId}/ensembles/${routeIds.ensembleId}/runs/${routeIds.runId}/stop`
          )
        )
      })

      await stopButton.click()

      const firstStopResponse = await firstStopResponsePromise
      expect(firstStopResponse.status()).toBe(200)
      await expect(startButton).toContainText('Retry selected run', { timeout: actionTimeout })
      await expect(cleanupButton).toBeEnabled({ timeout: actionTimeout })
      await expect(rerunButton).toBeEnabled({ timeout: actionTimeout })

      evidence.operatorActions.push({
        action: 'stop',
        result: 'selected run stopped cleanly',
        runId: routeIds.runId,
        responseStatus: firstStopResponse.status()
      })

      const retryResponsePromise = page.waitForResponse((response) => {
        return (
          response.request().method() === 'POST'
          && response.url().includes(
            `/api/simulation/${defaultSimulationId}/ensembles/${routeIds.ensembleId}/runs/${routeIds.runId}/start`
          )
        )
      })

      await startButton.click()

      const retryResponse = await retryResponsePromise
      expect(retryResponse.status()).toBe(200)
      await expect(stopButton).toBeEnabled({ timeout: actionTimeout })

      const retriedRouteIds = extractRouteIds(page.url())
      expect(retriedRouteIds.runId).toBe(routeIds.runId)

      evidence.operatorActions.push({
        action: 'retry',
        result: 'same run ID relaunched',
        runId: retriedRouteIds.runId,
        responseStatus: retryResponse.status()
      })

      const secondStopResponsePromise = page.waitForResponse((response) => {
        return (
          response.request().method() === 'POST'
          && response.url().includes(
            `/api/simulation/${defaultSimulationId}/ensembles/${routeIds.ensembleId}/runs/${routeIds.runId}/stop`
          )
        )
      })

      await stopButton.click()

      const secondStopResponse = await secondStopResponsePromise
      expect(secondStopResponse.status()).toBe(200)
      await expect(cleanupButton).toBeEnabled({ timeout: actionTimeout })

      evidence.operatorActions.push({
        action: 'stop-after-retry',
        result: 'retried run stopped cleanly',
        runId: routeIds.runId,
        responseStatus: secondStopResponse.status()
      })

      const cleanupResponsePromise = page.waitForResponse((response) => {
        return (
          response.request().method() === 'POST'
          && response.url().includes(
            `/api/simulation/${defaultSimulationId}/ensembles/${routeIds.ensembleId}/cleanup`
          )
        )
      })

      await cleanupButton.click()

      const cleanupResponse = await cleanupResponsePromise
      expect(cleanupResponse.status()).toBe(200)
      await expect(startButton).toContainText('Launch selected run', { timeout: actionTimeout })

      evidence.operatorActions.push({
        action: 'cleanup',
        result: 'selected run reset to prepared shell',
        runId: routeIds.runId,
        responseStatus: cleanupResponse.status()
      })

      const rerunResponsePromise = page.waitForResponse((response) => {
        return (
          response.request().method() === 'POST'
          && response.url().includes(
            `/api/simulation/${defaultSimulationId}/ensembles/${routeIds.ensembleId}/runs/${routeIds.runId}/rerun`
          )
        )
      })

      await rerunButton.click()

      const rerunResponse = await rerunResponsePromise
      expect(rerunResponse.status()).toBe(200)

      const rerunPayload = await rerunResponse.json()
      const childRunId = rerunPayload?.data?.run?.run_id
      expect(childRunId).toBeTruthy()
      expect(childRunId).not.toBe(routeIds.runId)

      await expect(page).toHaveURL(
        new RegExp(`ensembleId=${routeIds.ensembleId}.*runId=${childRunId}`),
        { timeout: actionTimeout }
      )
      await expect(startButton).toContainText('Launch selected run', { timeout: actionTimeout })

      evidence.childRunId = childRunId
      evidence.operatorActions.push({
        action: 'rerun',
        result: 'child run created and selected',
        sourceRunId: routeIds.runId,
        childRunId,
        responseStatus: rerunResponse.status()
      })
    } finally {
      writeEvidence(evidence)
    }
  })

  test('Step 4 report and Step 5 report-agent work on a live probabilistic report', async ({ page }) => {
    test.setTimeout(liveStep45Timeout)

    const resolvedStep45Selection = resolveLiveStep45Selection()
    const step45SimulationId = resolvedStep45Selection.simulationId
    const step45SimulationSelection = resolvedStep45Selection.simulationSelection
    const step45ReportScopeSelection = resolvedStep45Selection.reportScopeSelection

    const evidence = {
      evidenceClass: 'local-only non-fixture step4-step5',
      mutationAllowed: process.env.PLAYWRIGHT_LIVE_ALLOW_MUTATION === 'true',
      simulationId: step45SimulationId,
      simulationSelection: step45SimulationSelection,
      reportScopeSelection: step45ReportScopeSelection,
      startedAt: new Date().toISOString(),
      forecastBootstrap: null,
      reportGeneration: null,
      step4: null,
      step5: null,
      chat: null,
      console: [],
      pageErrors: []
    }

    page.on('console', (message) => {
      evidence.console.push({
        type: message.type(),
        text: message.text()
      })
    })

    page.on('pageerror', (error) => {
      evidence.pageErrors.push(String(error))
    })

    try {
      if (!step45SimulationId) {
        throw new Error(
          `Live Step 4/5 verification could not select a report-ready prepared-and-grounded simulation: ${
            step45ReportScopeSelection.reason || resolvedSimulationSelection.reason
          }`
        )
      }

      const executionNonce = Date.now().toString(36)
      const liveOutcomeLabels = ['labor market', 'cybersecurity', 'regulatory']
      const liveForecastId = [
        'live-forecast',
        step45SimulationId,
        executionNonce
      ].join('-')
      const liveSimulationWorkerId = `worker-sim-${step45SimulationId}-${executionNonce}`
      const liveForecastRequestedAt = new Date().toISOString()
      const liveForecastQuestion = (
        `Which topic dominates the fresh live probabilistic discussion for ${step45SimulationId}: `
        + `${liveOutcomeLabels.join(', ')}?`
      )

      const createForecastResponse = await page.request.post(
        buildLiveBackendApiUrl('/api/forecast/questions'),
        {
          data: {
            forecast_id: liveForecastId,
            project_id: `live-${step45SimulationId}`,
            title: `Live probabilistic report proof ${step45SimulationId}`,
            question: liveForecastQuestion,
            question_text: liveForecastQuestion,
            question_type: 'categorical',
            question_spec: {
              outcome_labels: liveOutcomeLabels
            },
            status: 'active',
            source: 'live-operator-local',
            horizon: { type: 'date', value: '2026-12-31' },
            primary_simulation_id: step45SimulationId,
            issue_timestamp: liveForecastRequestedAt,
            created_at: liveForecastRequestedAt,
            updated_at: liveForecastRequestedAt,
            forecast_workers: [
              {
                worker_id: liveSimulationWorkerId,
                forecast_id: liveForecastId,
                kind: 'simulation',
                label: 'Live scenario simulation worker',
                status: 'ready',
                capabilities: ['scenario_generation', 'scenario_analysis'],
                primary_output_semantics: 'scenario_evidence'
              }
            ],
            simulation_worker_contract: {
              forecast_id: liveForecastId,
              worker_id: liveSimulationWorkerId,
              simulation_id: step45SimulationId
            }
          }
        }
      )
      expect(createForecastResponse.status()).toBe(201)
      const createForecastResult = await createForecastResponse.json()
      expect(createForecastResult?.success).toBeTruthy()

      const createEnsembleResponse = await page.request.post(
        buildLiveBackendApiUrl(`/api/simulation/${step45SimulationId}/ensembles`),
        {
          data: {
            run_count: 1,
            max_concurrency: 1,
            root_seed: Date.now() % 2_147_483_647,
            forecast_id: liveForecastId
          }
        }
      )
      expect(createEnsembleResponse.status()).toBe(200)
      const createEnsembleResult = await createEnsembleResponse.json()
      expect(createEnsembleResult?.success).toBeTruthy()

      const liveEnsembleId = createEnsembleResult?.data?.ensemble_id
      const liveRunId = createEnsembleResult?.data?.runs?.[0]?.run_id
      expect(liveEnsembleId).toBeTruthy()
      expect(liveRunId).toBeTruthy()

      const startRunResponse = await page.request.post(
        buildLiveBackendApiUrl(
          `/api/simulation/${step45SimulationId}/ensembles/${liveEnsembleId}/runs/${liveRunId}/start`
        ),
        {
          data: {
            platform: 'parallel',
            close_environment_on_complete: true,
            max_rounds: 8,
            forecast_id: liveForecastId
          }
        }
      )
      expect(startRunResponse.status()).toBe(200)
      const startRunResult = await startRunResponse.json()
      expect(startRunResult?.success).toBeTruthy()

      const liveRunEvidence = await waitForLiveRunScopeEvidence({
        simulationId: step45SimulationId,
        ensembleId: liveEnsembleId,
        runId: liveRunId
      })

      const generateForecastAnswerResponse = await page.request.post(
        buildLiveBackendApiUrl(`/api/forecast/questions/${liveForecastId}/forecast-answers/generate`),
        {
          data: {
            requested_at: liveForecastRequestedAt
          }
        }
      )
      expect(generateForecastAnswerResponse.status()).toBe(200)
      const generateForecastAnswerResult = await generateForecastAnswerResponse.json()
      expect(generateForecastAnswerResult?.success).toBeTruthy()
      expect(generateForecastAnswerResult?.forecast_answer?.answer_type).toBe('hybrid_forecast')

      const workerContributionTrace = (
        generateForecastAnswerResult?.forecast_answer?.answer_payload?.worker_contribution_trace || []
      )
      const simulationWorkerTrace = (
        workerContributionTrace
      ).find((item) => item?.worker_id === liveSimulationWorkerId)
      const simulationMarketTrace = workerContributionTrace.find(
        (item) => item?.worker_kind === 'simulation_market'
      )
      expect(simulationWorkerTrace).toBeTruthy()
      expect(simulationMarketTrace).toBeTruthy()
      expect(generateForecastAnswerResult?.forecast_answer?.answer_payload?.best_estimate).toBeTruthy()

      const liveForecastWorkspaceResponse = await page.request.get(
        buildLiveBackendApiUrl(`/api/forecast/questions/${liveForecastId}`)
      )
      expect(liveForecastWorkspaceResponse.status()).toBe(200)
      const liveForecastWorkspaceResult = await liveForecastWorkspaceResponse.json()
      expect(liveForecastWorkspaceResult?.success).toBeTruthy()
      expect(
        liveForecastWorkspaceResult?.workspace?.forecast_question?.primary_simulation_id
      ).toBe(step45SimulationId)
      expect(
        liveForecastWorkspaceResult?.workspace?.simulation_scope?.latest_ensemble_id
      ).toBe(liveEnsembleId)
      expect(
        liveForecastWorkspaceResult?.workspace?.simulation_scope?.latest_run_id
      ).toBe(liveRunId)

      const liveReportScopeSelection = {
        source: 'fresh-live-run',
        simulationId: step45SimulationId,
        reportId: null,
        ensembleId: liveEnsembleId,
        clusterId: null,
        runId: liveRunId,
        createdAt: (
          liveRunEvidence.runState?.completed_at
          || liveRunEvidence.runManifest?.completed_at
          || liveRunEvidence.runManifest?.updated_at
          || null
        )
      }
      evidence.reportScopeSelection = liveReportScopeSelection

      evidence.forecastBootstrap = {
        forecastId: liveForecastId,
        simulationWorkerId: liveSimulationWorkerId,
        ensembleId: liveEnsembleId,
        runId: liveRunId,
        startResponseStatus: startRunResponse.status(),
        actionLogs: liveRunEvidence.actionLogPaths,
        extractionStatus: liveRunEvidence.marketManifest?.extraction_status || null,
        signalCounts: liveRunEvidence.marketManifest?.signal_counts || null,
        latestAnswerId: generateForecastAnswerResult?.forecast_answer?.answer_id || null,
        workerTraceCount: workerContributionTrace.length,
        simulationTraceWorkerId: simulationWorkerTrace?.worker_id || null,
        simulationMarketWorkerId: simulationMarketTrace?.worker_id || null
      }

      const deadline = Date.now() + liveStep45Timeout
      const generatePayload = {
        simulation_id: step45SimulationId,
        ensemble_id: liveEnsembleId,
        run_id: liveRunId,
        force_regenerate: true
      }

      // The app runtime targets the backend API base directly via VITE_API_BASE_URL.
      // Keep live operator verification on that same contract instead of depending
      // on the Vite dev proxy for mutating report calls.
      const generateResponse = await page.request.post(buildLiveBackendApiUrl('/api/report/generate'), {
        data: generatePayload
      })
      expect(generateResponse.status()).toBe(200)

      const generateResult = await generateResponse.json()
      expect(generateResult?.success).toBeTruthy()

      const reportId = generateResult?.data?.report_id
      const taskId = generateResult?.data?.task_id
      expect(reportId).toBeTruthy()
      expect(taskId).toBeTruthy()

      evidence.reportGeneration = {
        sourceReportId: null,
        generatedReportId: reportId,
        taskId,
        reusedCompletedScope: false,
        scope: {
          ensembleId: generatePayload.ensemble_id,
          clusterId: null,
          runId: generatePayload.run_id || null
        }
      }

      let statusPayload = null
      while (Date.now() < deadline) {
        const statusResponse = await page.request.post(buildLiveBackendApiUrl('/api/report/generate/status'), {
          data: {
            task_id: taskId
          }
        })
        expect(statusResponse.status()).toBe(200)

        const statusResult = await statusResponse.json()
        expect(statusResult?.success).toBeTruthy()
        statusPayload = statusResult?.data || null

        if (statusPayload?.status === 'completed') {
          break
        }
        if (statusPayload?.status === 'failed') {
          throw new Error(
            `Live probabilistic report generation failed: ${statusPayload?.message || 'unknown failure'}`
          )
        }

        await page.waitForTimeout(1_000)
      }

      if (!statusPayload || statusPayload.status !== 'completed') {
        throw new Error(
          `Timed out waiting for live probabilistic report generation to complete for ${reportId}`
        )
      }

      evidence.reportGeneration.status = statusPayload.status
      evidence.reportGeneration.progress = statusPayload.progress ?? null
      evidence.reportGeneration.message = statusPayload.message || null

      let reportPayload = null
      while (Date.now() < deadline) {
        const reportResponse = await page.request.get(buildLiveBackendApiUrl(`/api/report/${reportId}`))
        expect(reportResponse.status()).toBe(200)
        const reportResult = await reportResponse.json()
        expect(reportResult?.success).toBeTruthy()

        if (
          reportResult?.data?.status === 'completed'
          && reportResult?.data?.probabilistic_context
        ) {
          reportPayload = reportResult.data
          break
        }

        await page.waitForTimeout(1_000)
      }

      if (!reportPayload?.probabilistic_context) {
        throw new Error(
          `Live probabilistic report ${reportId} completed without saved probabilistic context`
        )
      }

      const reportContext = reportPayload?.probabilistic_context || null
      const forecastWorkspace = reportContext?.forecast_workspace || null
      const forecastAnswer = forecastWorkspace?.forecast_answer || null
      const forecastObject = reportContext?.forecast_object || null
      const simulationMarketSummary = reportContext?.simulation_market_summary || null
      const signalProvenanceSummary = reportContext?.signal_provenance_summary || null

      expect(forecastWorkspace).toBeTruthy()
      expect(forecastAnswer).toBeTruthy()
      expect(forecastAnswer?.answer_payload?.best_estimate).toBeTruthy()
      expect(forecastObject?.latest_answer_id).toBeTruthy()
      expect(simulationMarketSummary).toBeTruthy()
      expect(signalProvenanceSummary).toBeTruthy()
      expect(reportContext?.selected_run?.simulation_market?.market_snapshot).toBeTruthy()

      evidence.reportGeneration.contextSummary = {
        selectedRunId: reportContext?.selected_run?.run_id || null,
        forecastAnswerId: forecastAnswer?.answer_id || null,
        latestAnswerId: forecastObject?.latest_answer_id || null,
        predictionLedgerEntryCount: forecastWorkspace?.prediction_ledger?.entry_count ?? null,
        provenanceStatus: signalProvenanceSummary?.status || null
      }

      const expectedStep4Title = (
        forecastWorkspace || forecastObject
          ? 'Forecast Object And Supporting Evidence'
          : 'Scoped Simulation Evidence'
      )

      await page.goto(`/report/${reportId}`)
      await expect(page.getByTestId('probabilistic-report-context')).toBeVisible({
        timeout: actionTimeout
      })
      await expect(page.getByText(expectedStep4Title)).toBeVisible({
        timeout: actionTimeout
      })
      await expect(page.getByText('Upstream Grounding')).toBeVisible({
        timeout: actionTimeout
      })
      await expect(page.getByTestId('probabilistic-compare-workspace')).toBeVisible({
        timeout: actionTimeout
      })

      const compareOptions = page.getByTestId('probabilistic-compare-option')
      await expect(compareOptions.first()).toBeVisible({ timeout: actionTimeout })
      await compareOptions.first().click()
      const compareHandoff = page.getByTestId('probabilistic-compare-handoff')
      await expect(compareHandoff).toBeVisible({ timeout: actionTimeout })

      const reportUrl = new URL(page.url())
      evidence.step4 = {
        reportId,
        compareOptionCount: await compareOptions.count(),
        compareId: reportUrl.searchParams.get('compareId')
      }

      await compareHandoff.click()

      await expect(page).toHaveURL(new RegExp(`/interaction/${reportId}`), {
        timeout: actionTimeout
      })
      await expect(page).toHaveURL(/compareId=/, { timeout: actionTimeout })
      await expect(page.getByTestId('probabilistic-step5-banner')).toBeVisible({
        timeout: actionTimeout
      })
      await expect(page.getByTestId('probabilistic-step5-evidence')).toBeVisible({
        timeout: actionTimeout
      })
      await expect(page.getByTestId('probabilistic-step5-scope-control')).toBeVisible({
        timeout: actionTimeout
      })
      await expect(page.getByTestId('probabilistic-step5-compare')).toBeVisible({
        timeout: actionTimeout
      })

      const interactionUrl = new URL(page.url())
      evidence.step5 = {
        reportId,
        compareId: interactionUrl.searchParams.get('compareId')
      }

      const chatInput = page.locator('.chat-input')
      await expect(chatInput).toBeVisible({ timeout: actionTimeout })
      await chatInput.fill(
        'What evidence boundaries should I keep in mind for this scoped probabilistic report?'
      )

      const priorAssistantMessages = page.locator('.chat-message.assistant')
      const priorAssistantCount = await priorAssistantMessages.count()
      const chatResponsePromise = page.waitForResponse((response) => {
        return (
          response.request().method() === 'POST'
          && response.url().includes('/api/report/chat')
        )
      })

      await chatInput.press('Enter')

      const chatResponse = await chatResponsePromise
      expect(chatResponse.status()).toBe(200)
      const chatResult = await chatResponse.json()
      expect(chatResult?.success).toBeTruthy()
      expect(typeof chatResult?.data?.response).toBe('string')
      expect(chatResult.data.response.trim().length).toBeGreaterThan(0)

      await expect(page.locator('.chat-message.assistant')).toHaveCount(priorAssistantCount + 1, {
        timeout: actionTimeout
      })
      await expect(page.locator('.chat-message.assistant .message-text').last()).toBeVisible({
        timeout: actionTimeout
      })

      evidence.chat = {
        responseLength: chatResult.data.response.trim().length,
        toolCalls: Array.isArray(chatResult?.data?.tool_calls) ? chatResult.data.tool_calls.length : 0,
        sources: Array.isArray(chatResult?.data?.sources) ? chatResult.data.sources.length : 0,
        responseExcerpt: chatResult.data.response.trim().slice(0, 240)
      }
    } finally {
      writeEvidence(evidence, {
        basename: 'report-pass',
        latestName: 'report-latest.json'
      })
    }
  })
})
