import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { expect, test } from '@playwright/test'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const repoRoot = path.resolve(__dirname, '..', '..')
const liveEvidenceDir = path.join(repoRoot, 'output', 'playwright', 'live-operator')
const defaultSimulationId = process.env.PLAYWRIGHT_LIVE_SIMULATION_ID || 'sim_7a6661c37719'
const actionTimeout = 30_000

const buildEvidencePath = () => {
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-')
  return {
    latestPath: path.join(liveEvidenceDir, 'latest.json'),
    timestampedPath: path.join(liveEvidenceDir, `operator-pass-${timestamp}.json`)
  }
}

const writeEvidence = (payload) => {
  const normalizedPayload = {
    ...payload,
    completedAt: new Date().toISOString()
  }
  const { latestPath, timestampedPath } = buildEvidencePath()
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
      await page.goto(`/simulation/${defaultSimulationId}`)

      const handoffButton = page.getByRole('button', {
        name: /Start Dual-World Parallel Simulation/i
      })

      await expect(handoffButton).toBeVisible({ timeout: actionTimeout })

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

      await expect(operatorGuidance).toContainText('Stop the active run before cleanup or child rerun', {
        timeout: actionTimeout
      })
      await expect(stopButton).toBeEnabled({ timeout: actionTimeout })

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
})
