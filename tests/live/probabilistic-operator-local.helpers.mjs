import fs from 'node:fs'
import path from 'node:path'

const defaultSmokeFixtureMarkerFilename = 'probabilistic_smoke_fixture.json'

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

const getSignalCount = (signalCounts, key) => {
  if (!signalCounts || typeof signalCounts !== 'object') {
    return 0
  }
  const rawValue = signalCounts[key]
  return Number.isFinite(rawValue) ? Number(rawValue) : 0
}

export const createLiveOperatorArtifactReader = ({
  simulationsRoot,
  reportsRoot,
  processEnv = process.env,
  smokeFixtureMarkerFilename = defaultSmokeFixtureMarkerFilename
} = {}) => {
  const readLiveSimulationRecord = (simulationId) => {
    if (!simulationId || !simulationsRoot) {
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
    if (!simulationsRoot || !fs.existsSync(simulationsRoot)) {
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
    if (processEnv.PLAYWRIGHT_LIVE_SIMULATION_ID) {
      return {
        simulationId: processEnv.PLAYWRIGHT_LIVE_SIMULATION_ID,
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

  const listCompletedProbabilisticReportScopes = ({ simulationId = null } = {}) => {
    if (!reportsRoot || !fs.existsSync(reportsRoot)) {
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
    if (!simulationId || !simulationsRoot) {
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
    const preferFreshGeneration = processEnv.PLAYWRIGHT_LIVE_ALLOW_MUTATION === 'true'
    const resolvedSimulationSelection = resolveLiveSimulationSelection()

    if (processEnv.PLAYWRIGHT_LIVE_SIMULATION_ID) {
      const envSimulationId = processEnv.PLAYWRIGHT_LIVE_SIMULATION_ID
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

    const simulationCandidates = listLiveSimulationCandidates()
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

    if (preferFreshGeneration) {
      const candidateSelections = simulationCandidates.map((candidate) => ({
        candidate,
        readyRunScope: listCompletedRunScopeCandidates(candidate.simulationId)[0] || null,
        savedReportScope: listCompletedProbabilisticReportScopes({
          simulationId: candidate.simulationId
        })[0] || null
      }))

      const historicalReadyCandidate = candidateSelections.find((entry) => entry.readyRunScope)
      if (historicalReadyCandidate) {
        return {
          simulationId: historicalReadyCandidate.candidate.simulationId,
          simulationSelection: historicalReadyCandidate.candidate,
          reportScopeSelection: historicalReadyCandidate.readyRunScope
        }
      }

      const fallbackReasons = candidateSelections.map(({ candidate, savedReportScope }) => {
        return `${candidate.simulationId}: ${
          savedReportScope?.reportId
            ? 'saved reports exist but no completed ready run-scoped evidence was found'
            : 'no completed ready run-scoped evidence was found'
        }`
      })

      return {
        simulationId: null,
        simulationSelection: resolvedSimulationSelection.simulationId
          ? resolvedSimulationSelection
          : simulationCandidates[0],
        reportScopeSelection: {
          source: 'auto',
          reportId: null,
          reason: (
            'No active prepared-and-grounded simulation with completed ready run-scoped evidence '
            + `was available for live Step 4/5 verification. ${fallbackReasons.join(' | ')}`
          ).trim()
        }
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

  const readLiveRunScopeEvidence = ({ simulationId, ensembleId, runId }) => {
    if (!simulationId || !ensembleId || !runId || !simulationsRoot) {
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
      getSignalCount(signalCounts, 'agent_beliefs') > 0
      || getSignalCount(signalCounts, 'belief_updates') > 0
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
      hasExtractedSignals
    }
  }

  const isLiveRunScopeReady = (evidence) => {
    if (!evidence || typeof evidence !== 'object') {
      return false
    }
    return Boolean(
      evidence.runState?.runner_status === 'completed'
      && evidence.runManifest?.status === 'completed'
      && evidence.marketManifest?.extraction_status === 'ready'
      && evidence.marketManifest?.forecast_workspace_linked === true
      && evidence.marketManifest?.scope_linked_to_run === true
      && evidence.actionLogPaths.length > 0
      && evidence.hasExtractedSignals
      && evidence.marketSnapshot
      && evidence.metrics
    )
  }

  const summarizeLiveRunScopeEvidence = (evidence) => {
    if (!evidence || typeof evidence !== 'object') {
      return null
    }
    return {
      runnerStatus: evidence.runState?.runner_status || null,
      runStatus: evidence.runManifest?.status || null,
      extractionStatus: evidence.marketManifest?.extraction_status || null,
      forecastWorkspaceLinked: evidence.marketManifest?.forecast_workspace_linked === true,
      scopeLinkedToRun: evidence.marketManifest?.scope_linked_to_run === true,
      actionLogs: evidence.actionLogPaths,
      signalCounts: evidence.marketManifest?.signal_counts || null,
      hasMarketSnapshot: Boolean(evidence.marketSnapshot),
      hasMetrics: Boolean(evidence.metrics)
    }
  }

  const getLiveRunScopeTerminalIssue = (evidence) => {
    if (!evidence || typeof evidence !== 'object') {
      return null
    }

    const runnerStatus = evidence.runState?.runner_status || null
    const runStatus = evidence.runManifest?.status || null
    const extractionStatus = evidence.marketManifest?.extraction_status || null
    const totalActions = (
      evidence.metrics?.metric_values?.['simulation.total_actions']?.value
      ?? evidence.metrics?.timeline_summaries?.total_actions
      ?? evidence.runState?.total_actions_count
      ?? null
    )

    if (runnerStatus === 'failed') {
      const errorSummary = evidence.runState?.error || evidence.runManifest?.error || 'unknown error'
      return `runner_status=failed error=${errorSummary}`
    }

    const reachedTerminalState = runnerStatus === 'completed' || runStatus === 'completed'
    if (!reachedTerminalState || isLiveRunScopeReady(evidence)) {
      return null
    }

    if (extractionStatus) {
      return `extraction_status=${extractionStatus} total_actions=${totalActions ?? 'unknown'}`
    }

    if (typeof totalActions === 'number' && totalActions === 0) {
      return 'total_actions=0'
    }

    if (evidence.actionLogPaths.length === 0) {
      return 'missing_action_logs'
    }

    return 'completed_without_ready_run_scope_evidence'
  }

  return {
    safeReadJson,
    isProbabilisticPrepared,
    hasSavedReportInferenceEvidence,
    readLiveSimulationRecord,
    listLiveSimulationCandidates,
    resolveLiveSimulationSelection,
    listCompletedProbabilisticReportScopes,
    listCompletedRunScopeCandidates,
    resolveLiveProbabilisticReportScope,
    resolveLiveStep45Selection,
    readLiveRunScopeEvidence,
    isLiveRunScopeReady,
    summarizeLiveRunScopeEvidence,
    getLiveRunScopeTerminalIssue
  }
}
