import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { expect, test } from '@playwright/test'

import {
  createLiveOperatorArtifactReader
} from './probabilistic-operator-local.helpers.mjs'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const repoRoot = path.resolve(__dirname, '..', '..')
const liveEvidenceDir = path.join(repoRoot, 'output', 'playwright', 'live-operator')
const simulationsRoot = path.join(repoRoot, 'backend', 'uploads', 'simulations')
const reportsRoot = path.join(repoRoot, 'backend', 'uploads', 'reports')
const actionTimeout = 30_000
const readinessTimeout = 5_000
const reportTimeout = 300_000
const liveStep45Timeout = 600_000
const liveBackendPort = process.env.PLAYWRIGHT_BACKEND_PORT || '50141'
const liveBackendBaseURL = process.env.PLAYWRIGHT_BACKEND_BASE_URL || `http://127.0.0.1:${liveBackendPort}`

const liveArtifactReader = createLiveOperatorArtifactReader({
  simulationsRoot,
  reportsRoot,
  processEnv: process.env
})

const resolvedSimulationSelection = liveArtifactReader.resolveLiveSimulationSelection()
const defaultSimulationId = resolvedSimulationSelection.simulationId

const delay = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds))

const waitForLiveRunScopeEvidence = async (
  { simulationId, ensembleId, runId },
  {
    timeoutMs = liveStep45Timeout,
    pollIntervalMs = 2_000
  } = {}
) => {
  const deadline = Date.now() + timeoutMs
  let lastEvidence = liveArtifactReader.readLiveRunScopeEvidence({ simulationId, ensembleId, runId })

  while (Date.now() < deadline) {
    lastEvidence = (
      liveArtifactReader.readLiveRunScopeEvidence({ simulationId, ensembleId, runId })
      || lastEvidence
    )
    if (liveArtifactReader.isLiveRunScopeReady(lastEvidence)) {
      return lastEvidence
    }
    const terminalIssue = liveArtifactReader.getLiveRunScopeTerminalIssue(lastEvidence)
    if (terminalIssue) {
      throw new Error(
        `Live run-scoped report evidence reached a terminal non-ready state `
        + `${simulationId}/${ensembleId}/${runId}: ${terminalIssue}; ${
          JSON.stringify(liveArtifactReader.summarizeLiveRunScopeEvidence(lastEvidence))
        }`
      )
    }
    await delay(pollIntervalMs)
  }

  const timeoutSummary = liveArtifactReader.summarizeLiveRunScopeEvidence(lastEvidence)

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

    const resolvedStep45Selection = liveArtifactReader.resolveLiveStep45Selection()
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
