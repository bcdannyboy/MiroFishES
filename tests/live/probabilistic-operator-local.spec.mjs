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

const resolveLiveSimulationSelection = () => {
  if (process.env.PLAYWRIGHT_LIVE_SIMULATION_ID) {
    return {
      simulationId: process.env.PLAYWRIGHT_LIVE_SIMULATION_ID,
      source: 'env'
    }
  }

  if (!fs.existsSync(simulationsRoot)) {
    return {
      simulationId: null,
      source: 'auto',
      reason: `No simulation storage root found at ${simulationsRoot}`
    }
  }

  const candidates = []
  for (const entry of fs.readdirSync(simulationsRoot)) {
    if (!entry || entry.startsWith('.')) {
      continue
    }

    const simulationDir = path.join(simulationsRoot, entry)
    if (!fs.statSync(simulationDir).isDirectory()) {
      continue
    }
    if (fs.existsSync(path.join(simulationDir, smokeFixtureMarkerFilename))) {
      continue
    }
    if (fs.existsSync(path.join(simulationDir, 'forecast_archive.json'))) {
      continue
    }

    const preparedSnapshot = safeReadJson(path.join(simulationDir, 'prepared_snapshot.json'))
    if (!isProbabilisticPrepared(preparedSnapshot)) {
      continue
    }

    const groundingBundle = safeReadJson(path.join(simulationDir, 'grounding_bundle.json'))
    if (!groundingBundle || groundingBundle.status !== 'ready') {
      continue
    }

    const state = safeReadJson(path.join(simulationDir, 'state.json'))
    const configReasoning = typeof state?.config_reasoning === 'string'
      ? state.config_reasoning
      : ''
    if (configReasoning.includes('Synthetic smoke-fixture configuration')) {
      continue
    }
    const sourceRequirement = groundingBundle?.source_summary?.simulation_requirement
    if (
      typeof sourceRequirement === 'string'
      && sourceRequirement.includes('Smoke-test the probabilistic Step 2 to Step 3 handoff')
    ) {
      continue
    }
    candidates.push({
      simulationId: entry,
      createdAt: state?.created_at || state?.updated_at || null
    })
  }

  candidates.sort((left, right) => {
    const leftKey = left.createdAt || ''
    const rightKey = right.createdAt || ''
    return rightKey.localeCompare(leftKey) || right.simulationId.localeCompare(left.simulationId)
  })

  if (candidates.length === 0) {
    return {
      simulationId: null,
      source: 'auto',
      reason: 'No active prepared-and-grounded simulation was found under backend/uploads/simulations.'
    }
  }

  return {
    simulationId: candidates[0].simulationId,
    source: 'auto'
  }
}

const resolvedSimulationSelection = resolveLiveSimulationSelection()
const defaultSimulationId = resolvedSimulationSelection.simulationId

const resolveLiveProbabilisticReportScope = (simulationId) => {
  if (!simulationId) {
    return {
      source: 'auto',
      reportId: null,
      reason: 'No live simulation was selected for report verification.'
    }
  }

  if (!fs.existsSync(reportsRoot)) {
    return {
      source: 'auto',
      reportId: null,
      reason: `No report storage root found at ${reportsRoot}`
    }
  }

  const candidates = []
  for (const entry of fs.readdirSync(reportsRoot)) {
    if (!entry || entry.startsWith('.') || entry.startsWith('smoke-')) {
      continue
    }

    const reportDir = path.join(reportsRoot, entry)
    if (!fs.statSync(reportDir).isDirectory()) {
      continue
    }

    const meta = safeReadJson(path.join(reportDir, 'meta.json'))
    if (!meta || meta.simulation_id !== simulationId || meta.status !== 'completed') {
      continue
    }

    const probabilisticContext = (
      meta.probabilistic_context
      && typeof meta.probabilistic_context === 'object'
    )
      ? meta.probabilistic_context
      : null
    const ensembleId = meta.ensemble_id || probabilisticContext?.ensemble_id || null
    if (!ensembleId) {
      continue
    }

    candidates.push({
      source: 'auto',
      reportId: entry,
      ensembleId,
      clusterId: meta.cluster_id || probabilisticContext?.cluster_id || null,
      runId: meta.run_id || probabilisticContext?.run_id || null,
      createdAt: meta.completed_at || meta.created_at || null
    })
  }

  candidates.sort((left, right) => {
    const leftRunScoped = left.runId ? 1 : 0
    const rightRunScoped = right.runId ? 1 : 0
    if (rightRunScoped !== leftRunScoped) {
      return rightRunScoped - leftRunScoped
    }
    const leftKey = left.createdAt || ''
    const rightKey = right.createdAt || ''
    return rightKey.localeCompare(leftKey) || right.reportId.localeCompare(left.reportId)
  })

  if (candidates.length === 0) {
    return {
      source: 'auto',
      reportId: null,
      reason: `No completed live probabilistic report scope was found for ${simulationId}.`
    }
  }

  return candidates[0]
}

const resolvedReportScopeSelection = resolveLiveProbabilisticReportScope(defaultSimulationId)

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
    test.setTimeout(reportTimeout)

    const evidence = {
      evidenceClass: 'local-only non-fixture step4-step5',
      mutationAllowed: process.env.PLAYWRIGHT_LIVE_ALLOW_MUTATION === 'true',
      simulationId: defaultSimulationId,
      simulationSelection: resolvedSimulationSelection,
      reportScopeSelection: resolvedReportScopeSelection,
      startedAt: new Date().toISOString(),
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
      if (!defaultSimulationId) {
        throw new Error(
          `Live Step 4/5 verification could not select a prepared-and-grounded simulation: ${resolvedSimulationSelection.reason}`
        )
      }

      if (!resolvedReportScopeSelection.reportId || !resolvedReportScopeSelection.ensembleId) {
        throw new Error(
          `Live Step 4/5 verification could not resolve a completed probabilistic report scope: ${resolvedReportScopeSelection.reason}`
        )
      }

      const generatePayload = {
        simulation_id: defaultSimulationId,
        ensemble_id: resolvedReportScopeSelection.ensembleId,
        force_regenerate: true
      }
      if (resolvedReportScopeSelection.clusterId) {
        generatePayload.cluster_id = resolvedReportScopeSelection.clusterId
      }
      if (resolvedReportScopeSelection.runId) {
        generatePayload.run_id = resolvedReportScopeSelection.runId
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
        sourceReportId: resolvedReportScopeSelection.reportId,
        generatedReportId: reportId,
        taskId,
        scope: {
          ensembleId: generatePayload.ensemble_id,
          clusterId: generatePayload.cluster_id || null,
          runId: generatePayload.run_id || null
        }
      }

      let statusPayload = null
      const deadline = Date.now() + reportTimeout
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

      await page.goto(`/report/${reportId}`)
      await expect(page.getByTestId('probabilistic-report-context')).toBeVisible({
        timeout: actionTimeout
      })
      await expect(page.getByText('Scoped Simulation Evidence')).toBeVisible({
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
