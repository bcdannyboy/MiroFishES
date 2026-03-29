const LEGACY_RUNTIME_MODE = 'legacy'
const PROBABILISTIC_RUNTIME_MODE = 'probabilistic'
const PROBABILISTIC_SCOPE_LEVELS = new Set(['ensemble', 'cluster', 'run'])
const DEFAULT_PROBABILISTIC_RUN_COUNT = 8
const DEFAULT_PROBABILISTIC_MAX_CONCURRENCY = 1
const DEFAULT_STEP3_PREVIEW_MAX_NODES = 180
const DEFAULT_STEP3_PREVIEW_MAX_EDGES = 320
const MAX_INTERACTIVE_GRAPH_NODES = 160
const MAX_INTERACTIVE_GRAPH_EDGES = 240
const ANALYTICS_WARNING_LABELS = {
  observational_only: 'Observational only',
  thin_sample: 'Thin sample',
  degraded_runs_present: 'Degraded runs present',
  degraded_run_metrics: 'Degraded run metrics',
  missing_run_metrics: 'Missing run metrics',
  invalid_run_metrics: 'Invalid run metrics',
  invalid_run_manifest: 'Invalid run manifest',
  missing_resolved_values: 'Missing resolved values',
  low_confidence: 'Low confidence',
  no_varying_drivers: 'No varying drivers',
  no_shared_numeric_metrics: 'No shared numeric metrics',
  partial_feature_space: 'Partial feature space'
}

const normalizeRuntimeMode = (runtimeMode) => {
  return runtimeMode === PROBABILISTIC_RUNTIME_MODE
    ? PROBABILISTIC_RUNTIME_MODE
    : LEGACY_RUNTIME_MODE
}

const normalizeScopeLevel = (scopeLevel) => {
  const normalizedScopeLevel = normalizeOptionalString(scopeLevel)
  return PROBABILISTIC_SCOPE_LEVELS.has(normalizedScopeLevel)
    ? normalizedScopeLevel
    : null
}

const resolveRouteScopeLevel = ({
  scopeLevel,
  clusterId,
  runId
} = {}) => {
  const normalizedScopeLevel = normalizeScopeLevel(scopeLevel)
  const normalizedClusterId = normalizeOptionalString(clusterId)
  const normalizedRunId = normalizeOptionalString(runId)

  if (normalizedScopeLevel === 'run' && normalizedRunId) {
    return 'run'
  }

  if (normalizedScopeLevel === 'cluster' && normalizedClusterId) {
    return 'cluster'
  }

  if (normalizedScopeLevel === 'ensemble') {
    return 'ensemble'
  }

  if (normalizedRunId) {
    return 'run'
  }

  if (normalizedClusterId) {
    return 'cluster'
  }

  return 'ensemble'
}

const normalizePositiveInteger = (value) => {
  const parsed = Number.parseInt(value, 10)
  if (!Number.isInteger(parsed) || parsed <= 0) {
    return null
  }
  return parsed
}

const normalizeNonNegativeInteger = (value) => {
  const parsed = Number.parseInt(value, 10)
  if (!Number.isInteger(parsed) || parsed < 0) {
    return null
  }
  return parsed
}

const normalizeOptionalString = (value) => {
  if (typeof value !== 'string') {
    return null
  }

  const trimmed = value.trim()
  return trimmed ? trimmed : null
}

const normalizeTimestamp = (value) => {
  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? Number.NEGATIVE_INFINITY : value.getTime()
  }

  if (typeof value === 'number') {
    return Number.isFinite(value) ? value : Number.NEGATIVE_INFINITY
  }

  const normalizedValue = normalizeOptionalString(value)
  if (!normalizedValue) {
    return Number.NEGATIVE_INFINITY
  }

  const parsed = Date.parse(normalizedValue)
  return Number.isNaN(parsed) ? Number.NEGATIVE_INFINITY : parsed
}

const sanitizeHistoryTestIdPart = (value, fallback) => {
  const normalizedValue = normalizeOptionalString(value)
  if (!normalizedValue) {
    return fallback
  }

  const sanitizedValue = normalizedValue.replace(/[^a-zA-Z0-9_-]+/g, '-')
  return sanitizedValue || fallback
}

const getHistoryIdentityParts = (project = {}) => ({
  simulationId: sanitizeHistoryTestIdPart(project?.simulation_id, 'unknown-simulation'),
  reportId: sanitizeHistoryTestIdPart(project?.report_id, 'no-report')
})

const getHistoryProbabilisticReplaySource = (project = {}) => {
  const latestRuntime = (
    project?.latest_probabilistic_runtime
    && typeof project.latest_probabilistic_runtime === 'object'
  )
    ? project.latest_probabilistic_runtime
    : null

  if (latestRuntime) {
    return {
      source: normalizeOptionalString(latestRuntime.source) || 'report',
      reportId: normalizeOptionalString(latestRuntime.report_id),
      ensembleId: normalizeOptionalString(latestRuntime.ensemble_id),
      clusterId: normalizeOptionalString(latestRuntime.cluster_id),
      runId: normalizeOptionalString(latestRuntime.run_id)
    }
  }

  const latestReport = (
    project?.latest_report
    && typeof project.latest_report === 'object'
  )
    ? project.latest_report
    : null

  if (!latestReport) {
    return {
      source: null,
      reportId: null,
      ensembleId: null,
      clusterId: null,
      runId: null
    }
  }

  return {
    source: 'report',
    reportId: normalizeOptionalString(latestReport.report_id),
    ensembleId: normalizeOptionalString(latestReport.ensemble_id),
    clusterId: normalizeOptionalString(latestReport.cluster_id),
    runId: normalizeOptionalString(latestReport.run_id)
  }
}

const getNormalizedRunSelectionStatus = (runOrStatus) => {
  if (typeof runOrStatus === 'string') {
    return normalizeOptionalString(runOrStatus) || 'unknown'
  }

  if (!runOrStatus || typeof runOrStatus !== 'object') {
    return 'unknown'
  }

  return (
    normalizeOptionalString(runOrStatus.status)
    || normalizeOptionalString(runOrStatus.runner_status)
    || normalizeOptionalString(runOrStatus.storage_status)
    || 'unknown'
  )
}

const getRunSelectionPriority = (runOrStatus) => {
  const normalizedStatus = getNormalizedRunSelectionStatus(runOrStatus)
  const priorities = {
    running: 0,
    starting: 1,
    prepared: 2,
    completed: 3,
    stopped: 4,
    failed: 5,
    error: 5,
    unknown: 6
  }

  return priorities[normalizedStatus] ?? priorities.unknown
}

const getEffectiveRunLifecycleStatus = ({
  runtimeStatus,
  detailRecord
} = {}) => {
  const runnerStatus = normalizeOptionalString(runtimeStatus?.runner_status)
    || normalizeOptionalString(detailRecord?.runner_status)
  const detailStatus = normalizeOptionalString(detailRecord?.status)
  const storageStatus = normalizeOptionalString(runtimeStatus?.storage_status)
    || normalizeOptionalString(detailRecord?.storage_status)

  if (runnerStatus && runnerStatus !== 'idle') {
    return runnerStatus
  }

  return detailStatus || storageStatus || runnerStatus || 'prepared'
}

export const sortSimulationHistory = (projects = []) => {
  if (!Array.isArray(projects)) {
    return []
  }

  return [...projects].sort((left, right) => {
    const timestampDelta = normalizeTimestamp(right?.created_at) - normalizeTimestamp(left?.created_at)
    if (timestampDelta !== 0) {
      return timestampDelta
    }

    const tieBreakerFields = ['report_id', 'simulation_id', 'project_id']
    for (const field of tieBreakerFields) {
      const comparison = String(right?.[field] || '').localeCompare(String(left?.[field] || ''))
      if (comparison !== 0) {
        return comparison
      }
    }

    return 0
  })
}

export const getHistoryCardZIndex = ({
  index = 0,
  total = 0,
  isExpanded = false
} = {}) => {
  if (isExpanded) {
    return 100 + index
  }

  const normalizedTotal = Number.isInteger(total) && total > 0 ? total : 0
  return 10 + Math.max(normalizedTotal - index, 0)
}

export const isHistoryCardInteractive = ({
  index = 0,
  isExpanded = false
} = {}) => {
  if (isExpanded) {
    return true
  }

  return index === 0
}

export const getHistoryExpansionToggleLabel = ({
  isExpanded = false
} = {}) => {
  return isExpanded ? 'Collapse history' : 'Expand history'
}

export const buildHistoryCardTestId = (project = {}) => {
  const { simulationId, reportId } = getHistoryIdentityParts(project)
  return `history-card--${simulationId}--${reportId}`
}

export const buildHistoryActionTestId = (project = {}, action = 'open') => {
  const actionId = sanitizeHistoryTestIdPart(action, 'open')
  const { simulationId, reportId } = getHistoryIdentityParts(project)
  return `history-action-${actionId}--${simulationId}--${reportId}`
}

export const deriveHistoryStep3ReplayState = (project = {}) => {
  const simulationId = normalizeOptionalString(project?.simulation_id)
  const replaySource = getHistoryProbabilisticReplaySource(project)
  const ensembleId = replaySource.ensembleId
  const clusterId = replaySource.clusterId
  const runId = replaySource.runId
  const enabled = Boolean(simulationId && ensembleId && runId)

  if (!enabled) {
    return {
      enabled: false,
      simulationId,
      ensembleId: null,
      clusterId: null,
      runId: null,
      routeTarget: null,
      helperText: 'Step 3 replay is available only when history includes probabilistic runtime scope for one ensemble and run.'
    }
  }

  return {
    enabled: true,
    simulationId,
    ensembleId,
    clusterId,
    runId,
    routeTarget: {
      name: 'SimulationRun',
      params: {
        simulationId
      },
      query: buildSimulationRunRouteQuery({
        runtimeMode: PROBABILISTIC_RUNTIME_MODE,
        ensembleId,
        clusterId,
        runId,
        scopeLevel: 'run'
      })
    },
    helperText: replaySource.source === 'storage'
      ? 'Reopen the latest stored probabilistic Step 3 shell for this simulation.'
      : 'Reopen the saved probabilistic Step 3 shell for this report-scoped run.'
  }
}

export const buildProbabilisticEnsembleRequest = ({
  runCount = DEFAULT_PROBABILISTIC_RUN_COUNT,
  maxConcurrency = DEFAULT_PROBABILISTIC_MAX_CONCURRENCY
} = {}) => {
  const normalizedRunCount = normalizePositiveInteger(runCount)
  if (normalizedRunCount === null) {
    throw new Error('Probabilistic ensemble run count must be a positive integer.')
  }

  const normalizedMaxConcurrency = normalizePositiveInteger(maxConcurrency)
  if (normalizedMaxConcurrency === null) {
    throw new Error('Probabilistic ensemble max concurrency must be a positive integer.')
  }
  if (normalizedMaxConcurrency > normalizedRunCount) {
    throw new Error('Probabilistic ensemble max concurrency cannot exceed run count.')
  }

  return {
    run_count: normalizedRunCount,
    max_concurrency: normalizedMaxConcurrency
  }
}

export const getProbabilisticRuntimeShellErrorMessage = (
  error,
  fallbackMessage = 'Stored run shell creation failed'
) => {
  const backendError = normalizeOptionalString(error?.response?.data?.error)
  if (backendError) {
    return backendError
  }

  const inlineError = normalizeOptionalString(error?.error)
  if (inlineError) {
    return inlineError
  }

  return normalizeOptionalString(error?.message) || fallbackMessage
}

export const buildProbabilisticRunStartRequest = ({
  maxRounds,
  force = true,
  enableGraphMemoryUpdate = true,
  closeEnvironmentOnComplete = true
} = {}) => {
  const payload = {
    platform: 'parallel',
    force: force !== false,
    enable_graph_memory_update: enableGraphMemoryUpdate === true,
    close_environment_on_complete: closeEnvironmentOnComplete !== false
  }

  const normalizedMaxRounds = normalizePositiveInteger(maxRounds)
  if (normalizedMaxRounds !== null) {
    payload.max_rounds = normalizedMaxRounds
  }

  return payload
}

export const deriveStep3GraphRequest = ({
  currentStatus = 'processing'
} = {}) => {
  const normalizedStatus = normalizeOptionalString(currentStatus) || 'processing'
  const usePreviewMode = normalizedStatus === 'processing'

  return {
    mode: usePreviewMode ? 'preview' : 'full',
    maxNodes: usePreviewMode ? DEFAULT_STEP3_PREVIEW_MAX_NODES : null,
    maxEdges: usePreviewMode ? DEFAULT_STEP3_PREVIEW_MAX_EDGES : null,
    allowAutoRefresh: usePreviewMode,
    manualOnlyAfterCompletion: !usePreviewMode
  }
}

export const resolveStep3GraphScope = ({
  runtimeMode = LEGACY_RUNTIME_MODE,
  projectGraphId = null,
  runStatus = null
} = {}) => {
  const normalizedProjectGraphId = normalizeOptionalString(projectGraphId)
  const normalizedRunStatus = runStatus && typeof runStatus === 'object'
    ? runStatus
    : {}
  const isProbabilisticMode = (
    normalizeRuntimeMode(runtimeMode) === PROBABILISTIC_RUNTIME_MODE
  )
  const baseGraphId = (
    normalizeOptionalString(normalizedRunStatus.base_graph_id)
    || normalizeOptionalString(normalizedRunStatus.graph_id)
    || normalizedProjectGraphId
  )
  const runtimeGraphId = isProbabilisticMode
    ? normalizeOptionalString(normalizedRunStatus.runtime_graph_id)
    : null
  const graphId = runtimeGraphId || baseGraphId

  return {
    graphId,
    baseGraphId,
    runtimeGraphId,
    usesRuntimeGraph: Boolean(runtimeGraphId && graphId === runtimeGraphId)
  }
}

const getGraphPayloadCount = (payload, countKey, collectionKey) => {
  const normalizedPayload = payload && typeof payload === 'object'
    ? payload
    : {}

  return (
    normalizeNonNegativeInteger(normalizedPayload[countKey])
    ?? (
      Array.isArray(normalizedPayload[collectionKey])
        ? normalizedPayload[collectionKey].length
        : 0
    )
  )
}

const buildGraphNodeMergeKey = (node = {}) => {
  const nodeUuid = normalizeOptionalString(node?.uuid)
  if (nodeUuid) {
    return `uuid:${nodeUuid}`
  }

  const nodeName = normalizeOptionalString(node?.name) || 'unnamed'
  const labels = Array.isArray(node?.labels)
    ? [...node.labels].map((label) => String(label)).sort()
    : []
  return `node:${nodeName}:${labels.join('|')}`
}

const buildGraphEdgeMergeKey = (edge = {}) => {
  const edgeUuid = normalizeOptionalString(edge?.uuid)
  if (edgeUuid) {
    return `uuid:${edgeUuid}`
  }

  return [
    normalizeOptionalString(edge?.name) || 'edge',
    normalizeOptionalString(edge?.fact) || '',
    normalizeOptionalString(edge?.source_node_uuid) || '',
    normalizeOptionalString(edge?.target_node_uuid) || ''
  ].join('::')
}

export const mergeGraphDataPayloads = ({
  payloads = [],
  mode = 'preview',
  maxNodes = null,
  maxEdges = null
} = {}) => {
  const normalizedPayloads = Array.isArray(payloads)
    ? payloads.filter((payload) => payload && typeof payload === 'object')
    : []
  const mergedNodes = []
  const mergedEdges = []
  const seenNodes = new Set()
  const seenEdges = new Set()
  let totalNodes = 0
  let totalEdges = 0
  let truncated = false

  for (const payload of normalizedPayloads) {
    totalNodes += getGraphPayloadCount(payload, 'total_nodes', 'nodes')
    totalEdges += getGraphPayloadCount(payload, 'total_edges', 'edges')
    if (payload.truncated === true) {
      truncated = true
    }

    const payloadNodes = Array.isArray(payload.nodes) ? payload.nodes : []
    for (const node of payloadNodes) {
      const mergeKey = buildGraphNodeMergeKey(node)
      if (seenNodes.has(mergeKey)) {
        continue
      }
      seenNodes.add(mergeKey)
      if (maxNodes !== null && mergedNodes.length >= maxNodes) {
        truncated = true
        continue
      }
      mergedNodes.push(node)
    }

    const payloadEdges = Array.isArray(payload.edges) ? payload.edges : []
    for (const edge of payloadEdges) {
      const mergeKey = buildGraphEdgeMergeKey(edge)
      if (seenEdges.has(mergeKey)) {
        continue
      }
      seenEdges.add(mergeKey)
      if (maxEdges !== null && mergedEdges.length >= maxEdges) {
        truncated = true
        continue
      }
      mergedEdges.push(edge)
    }
  }

  if (mergedNodes.length < totalNodes || mergedEdges.length < totalEdges) {
    truncated = true
  }

  return {
    mode: normalizeOptionalString(mode) || 'preview',
    truncated,
    returned_nodes: mergedNodes.length,
    returned_edges: mergedEdges.length,
    total_nodes: Math.max(totalNodes, mergedNodes.length),
    total_edges: Math.max(totalEdges, mergedEdges.length),
    node_count: mergedNodes.length,
    edge_count: mergedEdges.length,
    nodes: mergedNodes,
    edges: mergedEdges
  }
}

export const deriveGraphPanelState = ({
  graphData = null
} = {}) => {
  const normalizedGraphData = graphData && typeof graphData === 'object'
    ? graphData
    : {}
  const mode = normalizedGraphData.mode === 'preview' ? 'preview' : 'full'
  const returnedNodes = (
    normalizeNonNegativeInteger(normalizedGraphData.returned_nodes)
    ?? (
      Array.isArray(normalizedGraphData.nodes)
        ? normalizedGraphData.nodes.length
        : 0
    )
  )
  const returnedEdges = (
    normalizeNonNegativeInteger(normalizedGraphData.returned_edges)
    ?? (
      Array.isArray(normalizedGraphData.edges)
        ? normalizedGraphData.edges.length
        : 0
    )
  )
  const totalNodes = normalizeNonNegativeInteger(normalizedGraphData.total_nodes) ?? returnedNodes
  const totalEdges = normalizeNonNegativeInteger(normalizedGraphData.total_edges) ?? returnedEdges
  const isPreview = mode === 'preview'
  const isTruncated = normalizedGraphData.truncated === true
  const exceedsInteractiveLimit = (
    returnedNodes > MAX_INTERACTIVE_GRAPH_NODES
    || returnedEdges > MAX_INTERACTIVE_GRAPH_EDGES
    || totalNodes > MAX_INTERACTIVE_GRAPH_NODES
    || totalEdges > MAX_INTERACTIVE_GRAPH_EDGES
  )
  const reason = isPreview
    ? 'preview'
    : isTruncated
      ? 'truncated'
      : exceedsInteractiveLimit
        ? 'large'
        : 'interactive'

  let summaryTitle = ''
  let summaryBody = ''

  if (reason === 'preview') {
    summaryTitle = 'Live graph preview'
    summaryBody = 'Showing a capped sample while the simulation is active. Load the full graph manually after completion.'
  } else if (reason === 'truncated') {
    summaryTitle = 'Large graph sample'
    summaryBody = 'The backend returned a capped sample for stability. This graph is too large for the interactive renderer.'
  } else if (reason === 'large') {
    summaryTitle = 'Large graph loaded'
    summaryBody = 'The full dataset was fetched, but the interactive renderer stays disabled at this size. Review the sampled metadata instead.'
  }

  const summaryDetail = reason === 'interactive'
    ? ''
    : `Sampled ${returnedNodes} nodes and ${returnedEdges} edges from ${totalNodes} nodes and ${totalEdges} edges.`

  return {
    mode,
    isInteractive: reason === 'interactive',
    isPreview,
    isTruncated,
    returnedNodes,
    returnedEdges,
    totalNodes,
    totalEdges,
    reason,
    summaryTitle,
    summaryBody,
    summaryDetail
  }
}

export const isStep2PrepareInFlight = ({
  hasStartedPrepare = false,
  phase = 0,
  activePrepareTaskId = null
} = {}) => {
  if (!hasStartedPrepare) {
    return false
  }

  if (normalizeOptionalString(activePrepareTaskId)) {
    return true
  }

  return !Number.isInteger(phase) || phase < 4
}

export const shouldPromoteStep2ReadyState = ({
  configGenerated = false,
  config = null,
  activePrepareTaskId = null
} = {}) => {
  if (!configGenerated || !config) {
    return false
  }

  return !normalizeOptionalString(activePrepareTaskId)
}

export const resolveProbabilisticRunSelection = ({
  requestedRunId,
  runs = []
} = {}) => {
  const normalizedRequestedRunId = normalizeOptionalString(requestedRunId)
  const normalizedRuns = Array.isArray(runs)
    ? runs
      .filter((run) => normalizeOptionalString(run?.run_id))
      .map((run) => ({
        ...run,
        run_id: normalizeOptionalString(run.run_id)
      }))
    : []

  if (!normalizedRequestedRunId) {
    return {
      selectedRunId: null,
      selectedRun: null,
      selectionMode: 'missing-request',
      requestedRunMissing: false
    }
  }

  if (!normalizedRuns.length) {
    return {
      selectedRunId: null,
      selectedRun: null,
      selectionMode: 'empty',
      requestedRunMissing: true
    }
  }

  const explicitSelection = normalizedRuns.find((run) => run.run_id === normalizedRequestedRunId)
  if (explicitSelection) {
    return {
      selectedRunId: explicitSelection.run_id,
      selectedRun: explicitSelection,
      selectionMode: 'requested',
      requestedRunMissing: false
    }
  }

  const fallbackSelection = [...normalizedRuns].sort((left, right) => {
    const priorityDelta = getRunSelectionPriority(left) - getRunSelectionPriority(right)
    if (priorityDelta !== 0) {
      return priorityDelta
    }
    return String(left?.run_id || '').localeCompare(String(right?.run_id || ''))
  })[0] || null

  return {
    selectedRunId: fallbackSelection?.run_id || null,
    selectedRun: fallbackSelection,
    selectionMode: fallbackSelection ? 'fallback' : 'empty',
    requestedRunMissing: true
  }
}

export const buildSimulationRunRouteQuery = ({
  maxRounds,
  runtimeMode,
  ensembleId,
  clusterId,
  runId,
  scopeLevel,
  compareId
} = {}) => {
  const query = {}
  const normalizedMaxRounds = normalizePositiveInteger(maxRounds)
  const normalizedRuntimeMode = normalizeRuntimeMode(runtimeMode)
  const normalizedEnsembleId = normalizeOptionalString(ensembleId)
  const normalizedClusterId = normalizeOptionalString(clusterId)
  const normalizedRunId = normalizeOptionalString(runId)
  const normalizedCompareId = normalizeOptionalString(compareId)
  const resolvedScopeLevel = resolveRouteScopeLevel({
    scopeLevel,
    clusterId: normalizedClusterId,
    runId: normalizedRunId
  })

  if (normalizedMaxRounds !== null) {
    query.maxRounds = String(normalizedMaxRounds)
  }
  if (normalizedRuntimeMode === PROBABILISTIC_RUNTIME_MODE) {
    query.mode = PROBABILISTIC_RUNTIME_MODE
  }
  if (normalizedEnsembleId) {
    query.ensembleId = normalizedEnsembleId
    if (normalizedRuntimeMode === PROBABILISTIC_RUNTIME_MODE) {
      query.scope = resolvedScopeLevel
    }
  }
  if (normalizedEnsembleId && normalizedClusterId) {
    query.clusterId = normalizedClusterId
  }
  if (normalizedRunId) {
    query.runId = normalizedRunId
  }
  if (normalizedCompareId) {
    query.compareId = normalizedCompareId
  }

  return query
}

export const buildReportGenerationRequest = ({
  simulationId,
  runtimeMode,
  ensembleId,
  clusterId,
  runId,
  forceRegenerate = true
} = {}) => {
  const payload = {
    simulation_id: simulationId,
    force_regenerate: forceRegenerate
  }

  if (normalizeRuntimeMode(runtimeMode) !== PROBABILISTIC_RUNTIME_MODE) {
    return payload
  }

  const normalizedEnsembleId = normalizeOptionalString(ensembleId)
  const normalizedClusterId = normalizeOptionalString(clusterId)
  const normalizedRunId = normalizeOptionalString(runId)

  if (normalizedEnsembleId) {
    payload.ensemble_id = normalizedEnsembleId
  }
  if (normalizedEnsembleId && normalizedClusterId) {
    payload.cluster_id = normalizedClusterId
  }
  if (normalizedEnsembleId && normalizedRunId) {
    payload.run_id = normalizedRunId
  }

  return payload
}

export const buildReportAgentChatRequest = ({
  simulationId,
  reportId,
  runtimeMode,
  ensembleId,
  clusterId,
  runId,
  scopeLevel,
  compareId,
  reportContext = null,
  message,
  chatHistory = []
} = {}) => {
  const payload = {
    simulation_id: simulationId,
    message,
    chat_history: Array.isArray(chatHistory) ? chatHistory : []
  }

  const normalizedReportId = normalizeOptionalString(reportId)
  if (normalizedReportId) {
    payload.report_id = normalizedReportId
  }

  if (normalizeRuntimeMode(runtimeMode) === PROBABILISTIC_RUNTIME_MODE) {
    const evidenceSummary = deriveProbabilisticEvidenceSummary({
      runtimeMode,
      ensembleId,
      clusterId,
      runId,
      scopeLevel,
      compareId,
      reportContext
    })
    const scopedEnsembleId = normalizeOptionalString(evidenceSummary.scope?.ensembleId)
    const scopedClusterId = normalizeOptionalString(evidenceSummary.scope?.clusterId)
    const scopedRunId = normalizeOptionalString(evidenceSummary.scope?.runId)
    const scopedLevel = normalizeScopeLevel(evidenceSummary.scope?.level)
    const scopedCompareId = normalizeOptionalString(
      evidenceSummary.selectedCompare?.compareId
    ) || normalizeOptionalString(compareId)

    if (scopedEnsembleId) {
      payload.ensemble_id = scopedEnsembleId
    }
    if (scopedEnsembleId && scopedClusterId) {
      payload.cluster_id = scopedClusterId
    }
    if (scopedEnsembleId && scopedRunId) {
      payload.run_id = scopedRunId
    }
    if (scopedLevel) {
      payload.scope_level = scopedLevel
    }
    if (scopedCompareId) {
      payload.compare_id = scopedCompareId
    }
  }

  return payload
}

export const normalizeSimulationRunRouteQuery = (query = {}) => {
  const runtimeMode = normalizeRuntimeMode(query.mode)
  const ensembleId = normalizeOptionalString(query.ensembleId)
  const clusterId = normalizeOptionalString(query.clusterId)
  const runId = normalizeOptionalString(query.runId)
  const compareId = normalizeOptionalString(query.compareId)
  const scopeLevel = resolveRouteScopeLevel({
    scopeLevel: query.scope ?? query.scopeLevel,
    clusterId,
    runId
  })

  return {
    maxRounds: normalizePositiveInteger(query.maxRounds),
    runtimeMode,
    ensembleId,
    clusterId,
    runId,
    compareId,
    scopeLevel,
    probabilisticRuntimeActive: (
      runtimeMode === PROBABILISTIC_RUNTIME_MODE
      && Boolean(ensembleId)
    )
  }
}

export const deriveProbabilisticReportRouteState = ({
  routeQuery = {},
  reportRecord = null
} = {}) => {
  const normalizedRoute = normalizeSimulationRunRouteQuery(routeQuery)
  const hasLoadedReportRecord = reportRecord !== null && reportRecord !== undefined
  const normalizedRecord = hasLoadedReportRecord && typeof reportRecord === 'object'
    ? reportRecord
    : {}
  const normalizedContext = normalizedRecord.probabilistic_context
    && typeof normalizedRecord.probabilistic_context === 'object'
      ? normalizedRecord.probabilistic_context
      : {}
  const reportEnsembleId = (
    normalizeOptionalString(normalizedRecord.ensemble_id)
    || normalizeOptionalString(normalizedContext.ensemble_id)
  )
  const reportClusterId = (
    normalizeOptionalString(normalizedRecord.cluster_id)
    || normalizeOptionalString(normalizedContext.cluster_id)
    || normalizeOptionalString(normalizedContext.scope?.cluster_id)
  )
  const reportRunId = (
    normalizeOptionalString(normalizedRecord.run_id)
    || normalizeOptionalString(normalizedContext.run_id)
  )
  const reportScopeLevel = (
    normalizeOptionalString(normalizedContext.scope?.level)
    || (reportRunId ? 'run' : (reportClusterId ? 'cluster' : 'ensemble'))
  )
  const probabilisticReportActive = Boolean(reportEnsembleId || reportRunId || reportClusterId)

  if (hasLoadedReportRecord) {
    return {
      runtimeMode: probabilisticReportActive
        ? PROBABILISTIC_RUNTIME_MODE
        : LEGACY_RUNTIME_MODE,
      ensembleId: reportEnsembleId,
      clusterId: reportClusterId,
      runId: reportRunId,
      compareId: normalizedRoute.compareId,
      scopeLevel: probabilisticReportActive ? reportScopeLevel : 'ensemble',
      probabilisticReportActive
    }
  }

  return {
    runtimeMode: probabilisticReportActive || normalizedRoute.probabilisticRuntimeActive
      ? PROBABILISTIC_RUNTIME_MODE
      : normalizedRoute.runtimeMode,
    ensembleId: reportEnsembleId || normalizedRoute.ensembleId,
    clusterId: reportClusterId || normalizedRoute.clusterId,
    runId: reportRunId || normalizedRoute.runId,
    compareId: normalizedRoute.compareId,
    scopeLevel: probabilisticReportActive
      ? reportScopeLevel
      : normalizedRoute.scopeLevel,
    probabilisticReportActive: probabilisticReportActive || normalizedRoute.probabilisticRuntimeActive
  }
}

export const getStep2PrepareBootstrapState = ({
  probabilisticPrepareEnabled = false,
  preparedArtifactSummary = null
} = {}) => {
  const hasPreparedForecastArtifacts = hasPreparedProbabilisticArtifacts(preparedArtifactSummary)
  if (probabilisticPrepareEnabled || hasPreparedForecastArtifacts) {
    return {
      selectedPrepareMode: PROBABILISTIC_RUNTIME_MODE,
      autoStartMode: null
    }
  }

  return {
    selectedPrepareMode: LEGACY_RUNTIME_MODE,
    autoStartMode: LEGACY_RUNTIME_MODE
  }
}

const hasPreparedProbabilisticArtifacts = (preparedArtifactSummary) => {
  if (!preparedArtifactSummary || typeof preparedArtifactSummary !== 'object') {
    return false
  }

  return (
    preparedArtifactSummary.probabilistic_mode === true
    || preparedArtifactSummary.mode === PROBABILISTIC_RUNTIME_MODE
  )
}

export const shouldLaunchProbabilisticRuntime = ({
  preparedArtifactSummary
} = {}) => hasPreparedProbabilisticArtifacts(preparedArtifactSummary)

export const getStep2StartSimulationState = ({
  simulationId = null,
  phase = 0,
  step3HandoffInFlight = false,
  prepareInFlight = false,
  selectedPrepareMode,
  preparedArtifactSummary,
  capabilities = {}
} = {}) => {
  const probabilisticRequested = (
    selectedPrepareMode === PROBABILISTIC_RUNTIME_MODE
    || hasPreparedProbabilisticArtifacts(preparedArtifactSummary)
  )
  const wantsProbabilisticRuntime = shouldLaunchProbabilisticRuntime({
    preparedArtifactSummary
  })
  const hasExplicitRuntimeCapability = (
    capabilities
    && typeof capabilities === 'object'
    && (
      Object.hasOwn(capabilities, 'probabilistic_ensemble_storage_enabled')
      || Object.hasOwn(capabilities, 'ensemble_runtime_enabled')
    )
  )
  const capabilityState = deriveProbabilisticCapabilityState(capabilities || {})
  const runtimeBlocked = (
    wantsProbabilisticRuntime
    && hasExplicitRuntimeCapability
    && capabilityState.runtimeEnabled === false
  )
  const artifactsMissing = probabilisticRequested && !wantsProbabilisticRuntime
  const readyForHandoff = phase >= 4 && !step3HandoffInFlight && !prepareInFlight

  return {
    enabled: (
      Boolean(normalizeOptionalString(simulationId))
      && readyForHandoff
      && !artifactsMissing
      && !runtimeBlocked
    ),
    helperText: readyForHandoff
      ? artifactsMissing
        ? 'Probabilistic Step 3 requires probabilistic prepare artifacts. Run probabilistic prepare first or return to the legacy path.'
        : runtimeBlocked
          ? 'Probabilistic Step 3 runtime shells are disabled by backend capabilities. Re-enable probabilistic runtime support or return to the legacy path.'
          : ''
      : ''
  }
}

export const getStep2HandoffState = ({
  simulationId = null,
  phase = 0,
  prepareInFlight = false,
  step3HandoffInFlight = false,
  selectedPrepareMode,
  preparedArtifactSummary = null,
  capabilities = null,
  capabilitiesKnown = false
} = {}) => {
  const normalizedCapabilities = (
    capabilitiesKnown && capabilities && typeof capabilities === 'object'
      ? capabilities
      : {}
  )
  const handoffState = getStep2StartSimulationState({
    simulationId,
    phase,
    prepareInFlight,
    step3HandoffInFlight,
    selectedPrepareMode,
    preparedArtifactSummary,
    capabilities: normalizedCapabilities
  })

  return {
    disabled: !handoffState.enabled,
    helperText: handoffState.helperText,
    runtimeBlocked: Boolean(handoffState.helperText)
  }
}

export const getStep3ReportState = (runtimeMode, capabilities = {}) => {
  if (normalizeRuntimeMode(runtimeMode) === PROBABILISTIC_RUNTIME_MODE) {
    if (capabilities?.probabilistic_report_enabled === true) {
      return {
        enabled: true,
        buttonLabel: 'Start generating the result report',
        helperText: 'Step 4 will keep the legacy report body and add observed empirical ensemble context for this probabilistic run family.'
      }
    }

    return {
      enabled: false,
      buttonLabel: 'Report generation unavailable',
      helperText: 'Step 4 report generation remains legacy-only for probabilistic Step 3 runs.'
    }
  }

  return {
    enabled: true,
    buttonLabel: 'Start generating the result report',
    helperText: ''
  }
}

export const getStep5InteractionState = (
  runtimeMode,
  {
    hasSavedProbabilisticContext = false,
    ensembleId = null,
    clusterId = null,
    runId = null,
    reportContext = null
  } = {}
) => {
  if (normalizeRuntimeMode(runtimeMode) !== PROBABILISTIC_RUNTIME_MODE) {
    return {
      showNotice: false,
      title: '',
      body: ''
    }
  }

  const evidenceSummary = deriveProbabilisticEvidenceSummary({
    runtimeMode,
    ensembleId,
    clusterId,
    runId,
    reportContext
  })
  const hasScopedProbabilisticContext = (
    hasSavedProbabilisticContext === true
    || Boolean(normalizeOptionalString(evidenceSummary.scope?.ensembleId))
  )

  if (hasScopedProbabilisticContext) {
    const scopeLevel = evidenceSummary.scope?.level || 'ensemble'
    const scopeLabel = scopeLevel === 'run'
      ? 'Run-scoped probabilistic context available'
      : (scopeLevel === 'cluster'
        ? 'Cluster-scoped probabilistic context available'
        : 'Ensemble-scoped probabilistic context available')
    let body = 'Report Agent chat can request ensemble evidence directly for this probabilistic scope.'
    if (scopeLevel === 'cluster') {
      body = 'Report Agent chat can request ensemble and scenario-family evidence directly for this probabilistic scope.'
    } else if (scopeLevel === 'run') {
      body = 'Report Agent chat can request ensemble, scenario-family, and run evidence directly for this probabilistic scope.'
    }
    if (Array.isArray(evidenceSummary.calibration?.readyMetricIds) && evidenceSummary.calibration.readyMetricIds.length) {
      body += ` Backtested calibration artifacts are available for ${evidenceSummary.calibration.readyMetricIds.join(', ')}.`
    } else if (evidenceSummary.confidenceStatus?.status === 'not_ready') {
      body += ' Calibration artifacts are present but not ready for calibrated language yet.'
    }
    body += ' Interviews with simulated individuals and surveys still use the legacy interaction path, so treat only the report-agent lane as probabilistic-context-aware.'
    return {
      showNotice: true,
      title: scopeLabel,
      body
    }
  }

  return {
    showNotice: true,
    title: 'Probabilistic interaction context unavailable',
    body: 'This Step 5 session has no saved probabilistic report scope, so Report Agent chat falls back to the legacy report and simulation context. Interviews and surveys still use the legacy interaction path.'
  }
}

export const deriveProbabilisticCapabilityState = (capabilities = {}) => {
  const runtimeEnabled = (
    capabilities.probabilistic_ensemble_storage_enabled === true
    || capabilities.ensemble_runtime_enabled === true
  )
  const reportEnabled = capabilities.probabilistic_report_enabled === true
  const interactionEnabled = capabilities.probabilistic_interaction_enabled === true
  const calibratedEnabled = (
    capabilities.calibrated_probability_enabled === true
    || capabilities.calibration_artifact_support_enabled === true
  )
  const calibrationSurfaceMode = normalizeOptionalString(capabilities.calibration_surface_mode)
    || (calibratedEnabled ? 'artifact-gated' : 'empirical-only')

  return {
    prepareEnabled: capabilities.probabilistic_prepare_enabled === true,
    runtimeEnabled,
    reportEnabled,
    interactionEnabled,
    calibratedEnabled,
    calibrationSurfaceMode,
    reportModeLabel: reportEnabled ? 'probabilistic-ready' : 'legacy-only',
    interactionModeLabel: interactionEnabled ? 'probabilistic-ready' : 'legacy-only',
    calibrationModeLabel: calibrationSurfaceMode
  }
}

export const deriveProbabilisticReportContextState = ({
  simulationId = null,
  runtimeMode = LEGACY_RUNTIME_MODE,
  ensembleId = null,
  clusterId = null,
  runId = null,
  reportContext = null,
  capabilities = null,
  capabilitiesKnown = false,
  capabilitiesLoading = false,
  capabilitiesError = ''
} = {}) => {
  const resolvedCapabilitiesKnown = (
    capabilitiesKnown
    || (
      capabilitiesLoading === false
      && capabilitiesError === ''
      && capabilities
      && typeof capabilities === 'object'
    )
  )
  const normalizedContext = reportContext && typeof reportContext === 'object'
    ? reportContext
    : {}
  const hasEmbeddedArtifacts = Boolean(
    normalizedContext.aggregate_summary
    || normalizedContext.scenario_clusters
    || normalizedContext.sensitivity
  )
  const capabilityState = deriveProbabilisticCapabilityState(
    resolvedCapabilitiesKnown ? (capabilities || {}) : {}
  )
  const shouldRender = normalizeRuntimeMode(runtimeMode) === PROBABILISTIC_RUNTIME_MODE
  const isFlaggedOff = (
    shouldRender
    && resolvedCapabilitiesKnown
    && capabilityState.reportEnabled === false
    && hasEmbeddedArtifacts === false
  )
  const hasExplicitScope = (
    Boolean(normalizeOptionalString(simulationId))
    && Boolean(normalizeOptionalString(ensembleId))
  )

  return {
    shouldRender,
    hasEmbeddedArtifacts,
    isFlaggedOff,
    historicalNotice: (
      shouldRender
      && resolvedCapabilitiesKnown
      && capabilityState.reportEnabled === false
      && hasEmbeddedArtifacts
    )
      ? 'Saved probabilistic report context is shown from report metadata even though live probabilistic report surfaces are currently disabled by the backend flag.'
      : '',
    fetchPlan: {
      summary: (
        shouldRender
        && hasExplicitScope
        && resolvedCapabilitiesKnown
        && capabilityState.reportEnabled === true
        && !normalizedContext.aggregate_summary
      ),
      clusters: (
        shouldRender
        && hasExplicitScope
        && resolvedCapabilitiesKnown
        && capabilityState.reportEnabled === true
        && !normalizedContext.scenario_clusters
      ),
      sensitivity: (
        shouldRender
        && hasExplicitScope
        && resolvedCapabilitiesKnown
        && capabilityState.reportEnabled === true
        && !normalizedContext.sensitivity
      )
    }
  }
}

const normalizeRuntimeRecord = (value) => {
  return value && typeof value === 'object' ? value : {}
}

const deriveSelectedRunSeed = (runDetail, runtimeStatus) => {
  const manifest = normalizeRuntimeRecord(runDetail?.run_manifest)
  const seedMetadata = normalizeRuntimeRecord(manifest.seed_metadata)

  return (
    seedMetadata.resolution_seed
    ?? seedMetadata.root_seed
    ?? manifest.root_seed
    ?? runtimeStatus.root_seed
    ?? '-'
  )
}

const buildProbabilisticWaitingText = ({
  requestedProbabilisticMode,
  isProbabilisticMode,
  normalizedRunId,
  lifecycleStatus
}) => {
  if (requestedProbabilisticMode && !isProbabilisticMode) {
    return 'Probabilistic Step 3 is waiting for a stored run shell from Step 2.'
  }

  if (!normalizedRunId) {
    return 'Waiting for one stored run to become available.'
  }

  if (lifecycleStatus === 'stopped') {
    return `Stored run ${normalizedRunId} stopped before completion. Step 3 remains monitor-only.`
  }

  if (lifecycleStatus === 'failed' || lifecycleStatus === 'error') {
    return `Stored run ${normalizedRunId} entered ${lifecycleStatus}. Step 3 remains monitor-only.`
  }

  if (lifecycleStatus === 'completed') {
    return `Stored run ${normalizedRunId} completed. Raw actions remain available for review.`
  }

  return `Waiting for actions from stored run ${normalizedRunId} (${lifecycleStatus}).`
}

const getProbabilisticOperatorGuidance = (lifecycleStatus) => {
  if (lifecycleStatus === 'running' || lifecycleStatus === 'starting') {
    return 'Stop the active run before cleanup or child rerun. Retry of the same run ID stays unavailable while the process is still active.'
  }

  if (['completed', 'stopped', 'failed', 'error'].includes(lifecycleStatus)) {
    return 'Retry selected run restarts the same run ID and clears transient runtime traces first. Clean selected run resets transient runtime artifacts while preserving resolved inputs. Create child rerun keeps this run as evidence and prepares a new run ID with lineage back to it.'
  }

  return 'Launch selected run starts this stored shell for the first time. Clean selected run only clears transient runtime traces if any exist. Create child rerun prepares a separate run ID before launch while keeping this shell unchanged.'
}

export const deriveProbabilisticOperatorActions = ({
  lifecycleStatus,
  isStarting = false,
  isStopping = false,
  isCleaning = false,
  isRerunning = false
} = {}) => {
  const normalizedLifecycleStatus = normalizeOptionalString(lifecycleStatus) || 'prepared'
  const runActive = ['running', 'starting'].includes(normalizedLifecycleStatus)
  const isRetryState = ['completed', 'stopped', 'failed', 'error'].includes(normalizedLifecycleStatus)
  const actionBlocked = isCleaning || isRerunning

  return {
    start: {
      enabled: !isStarting && !runActive && !actionBlocked,
      label: isStarting
        ? `${isRetryState ? 'Retrying' : 'Launching'} selected run...`
        : `${isRetryState ? 'Retry' : 'Launch'} selected run`,
      intent: isRetryState ? 'retry' : 'launch'
    },
    stop: {
      enabled: !isStopping && !isStarting && runActive && !actionBlocked,
      label: isStopping ? 'Stopping selected run...' : 'Stop selected run'
    },
    cleanup: {
      enabled: !isCleaning && !isStarting && !isStopping && !runActive && !isRerunning,
      label: isCleaning ? 'Cleaning selected run...' : 'Clean selected run'
    },
    rerun: {
      enabled: !isRerunning && !isStarting && !isStopping && !runActive && !isCleaning,
      label: isRerunning ? 'Creating child rerun...' : 'Create child rerun'
    },
    guidance: getProbabilisticOperatorGuidance(normalizedLifecycleStatus)
  }
}

export const deriveProbabilisticStep3Runtime = ({
  runtimeMode,
  ensembleId,
  runId,
  runDetail,
  runStatus
} = {}) => {
  const requestedProbabilisticMode = (
    normalizeRuntimeMode(runtimeMode) === PROBABILISTIC_RUNTIME_MODE
  )
  const normalizedEnsembleId = normalizeOptionalString(ensembleId)
  const normalizedRunId = normalizeOptionalString(runId)
  const runtimeStatus = normalizeRuntimeRecord(runStatus)
  const detailRecord = normalizeRuntimeRecord(runDetail)
  const detailRuntimeStatus = normalizeRuntimeRecord(detailRecord.runtime_status)
  const effectiveRuntimeStatus = Object.keys(runtimeStatus).length ? runtimeStatus : detailRuntimeStatus
  const isProbabilisticMode = (
    requestedProbabilisticMode
    && Boolean(normalizedEnsembleId)
    && Boolean(normalizedRunId)
  )
  const lifecycleStatus = getEffectiveRunLifecycleStatus({
    runtimeStatus: effectiveRuntimeStatus,
    detailRecord
  })
  const storageStatus = (
    effectiveRuntimeStatus.storage_status
    || detailRecord.storage_status
    || detailRecord.status
    || 'prepared'
  )
  const runtimeError = (
    requestedProbabilisticMode && !isProbabilisticMode
      ? 'Probabilistic Step 3 requires both ensemble and run identifiers from Step 2. Return to Step 2 and recreate the stored run shell.'
      : ''
  )

  return {
    requestedProbabilisticMode,
    isProbabilisticMode,
    normalizedEnsembleId,
    normalizedRunId,
    lifecycleStatus,
    storageStatus,
    selectedRunSeed: deriveSelectedRunSeed(detailRecord, effectiveRuntimeStatus),
    waitingText: buildProbabilisticWaitingText({
      requestedProbabilisticMode,
      isProbabilisticMode,
      normalizedRunId,
      lifecycleStatus
    }),
    runtimeError
  }
}

export const deriveProbabilisticProgressSummary = ({
  runStatus,
  latestTimelineRound,
  maxRounds
} = {}) => {
  const currentRound = (
    normalizeNonNegativeInteger(runStatus?.current_round)
    ?? normalizeNonNegativeInteger(latestTimelineRound)
  )
  const totalRounds = (
    normalizePositiveInteger(runStatus?.total_rounds)
    ?? normalizePositiveInteger(maxRounds)
  )

  if (currentRound === null && totalRounds === null) {
    return 'No rounds yet'
  }

  return `R${currentRound ?? 0}/${totalRounds ?? '-'}`
}

export const deriveProbabilisticActionRoundsMeta = ({
  timeline
} = {}) => {
  const count = Array.isArray(timeline) ? timeline.length : 0
  return `${count} populated rounds`
}

export const deriveProbabilisticPlatformSkewCopy = ({
  runStatus
} = {}) => {
  const twitterRound = normalizeNonNegativeInteger(runStatus?.twitter_current_round) ?? 0
  const redditRound = normalizeNonNegativeInteger(runStatus?.reddit_current_round) ?? 0

  if (twitterRound === redditRound || (!twitterRound && !redditRound)) {
    return ''
  }

  const twitterAhead = twitterRound > redditRound
  const lead = Math.abs(twitterRound - redditRound)
  const leadingPlatform = twitterAhead ? 'Info Plaza' : 'Topic Community'
  const trailingPlatform = twitterAhead ? 'Topic Community' : 'Info Plaza'
  const trailingInflightRound = normalizePositiveInteger(
    twitterAhead ? runStatus?.reddit_inflight_round : runStatus?.twitter_inflight_round
  )

  let message = `${leadingPlatform} is ahead by ${lead} round${lead === 1 ? '' : 's'}`
  if (trailingInflightRound !== null) {
    message += `; ${trailingPlatform} is working on R${trailingInflightRound}`
  }
  return `${message}.`
}

const normalizeAnalyticsRecord = (value) => {
  return value && typeof value === 'object' ? value : null
}

const normalizeStringList = (values = []) => {
  if (!Array.isArray(values)) {
    return []
  }

  return values
    .map((value) => normalizeOptionalString(value))
    .filter(Boolean)
}

const normalizeWarningList = (warnings = []) => {
  if (!Array.isArray(warnings)) {
    return []
  }

  const uniqueWarnings = []
  const seen = new Set()
  for (const warning of warnings) {
    if (typeof warning !== 'string' || seen.has(warning)) {
      continue
    }
    seen.add(warning)
    uniqueWarnings.push(
      ANALYTICS_WARNING_LABELS[warning]
      || warning.replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase())
    )
  }
  return uniqueWarnings
}

const formatAnalyticsNumber = (value) => {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return null
  }

  return Number.isInteger(value)
    ? String(value)
    : value.toFixed(2).replace(/\.?0+$/, '')
}

const formatProbabilityMass = (value) => {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return null
  }
  return `${(value * 100).toFixed(0)}%`
}

const formatScoringRuleLabel = (rule) => {
  const labels = {
    brier_score: 'Brier score',
    log_score: 'Log score',
    crps: 'CRPS'
  }

  if (typeof rule !== 'string') {
    return null
  }
  return labels[rule] || rule.replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase())
}

const countNonEmptyReliabilityBins = (bins = []) => {
  if (!Array.isArray(bins)) {
    return 0
  }

  return bins.reduce((count, bin) => {
    const caseCount = normalizeNonNegativeInteger(bin?.case_count)
    return count + (caseCount && caseCount > 0 ? 1 : 0)
  }, 0)
}

const normalizeConfidenceStatus = (reportContext = null) => {
  const normalizedContext = normalizeAnalyticsRecord(reportContext) || {}
  const rawStatus = normalizeAnalyticsRecord(normalizedContext.confidence_status) || {}
  const calibrationProvenance = normalizeAnalyticsRecord(normalizedContext.calibration_provenance) || {}
  const readyMetricIds = normalizeStringList(
    rawStatus.ready_metric_ids ?? calibrationProvenance.ready_metric_ids
  )
  const supportedMetricIds = normalizeStringList(
    rawStatus.supported_metric_ids ?? calibrationProvenance.ready_metric_ids
  )
  const notReadyMetricIds = normalizeStringList(rawStatus.not_ready_metric_ids)
  const status = normalizeOptionalString(rawStatus.status)
    || (readyMetricIds.length
      ? 'ready'
      : ((supportedMetricIds.length || notReadyMetricIds.length) ? 'not_ready' : 'absent'))

  return {
    status,
    supportedMetricIds,
    readyMetricIds,
    notReadyMetricIds,
    gatingReasons: normalizeStringList(rawStatus.gating_reasons),
    warnings: normalizeWarningList(rawStatus.warnings),
    boundaryNote: (
      normalizeOptionalString(rawStatus.boundary_note)
      || 'Calibration in this repo is binary-only and applies only to named metrics with ready backtest artifacts.'
    )
  }
}

const resolveProbabilisticScope = ({
  ensembleId = null,
  clusterId = null,
  runId = null,
  scopeLevel = null,
  reportContext = null
} = {}) => {
  const normalizedContext = normalizeAnalyticsRecord(reportContext) || {}
  const normalizedScope = normalizeAnalyticsRecord(normalizedContext.scope) || {}
  const normalizedSelectedCluster = normalizeAnalyticsRecord(normalizedContext.selected_cluster) || {}
  const normalizedSelectedRun = normalizeAnalyticsRecord(normalizedContext.selected_run) || {}
  const requestedScopeLevel = normalizeScopeLevel(scopeLevel)
  const resolvedLevel = (
    requestedScopeLevel
    || normalizeOptionalString(normalizedScope.level)
    || ((
      normalizeOptionalString(runId)
      || normalizeOptionalString(normalizedContext.run_id)
      || normalizeOptionalString(normalizedSelectedRun.run_id)
    )
      ? 'run'
      : ((
          normalizeOptionalString(clusterId)
          || normalizeOptionalString(normalizedContext.cluster_id)
          || normalizeOptionalString(normalizedSelectedCluster.cluster_id)
        )
          ? 'cluster'
          : 'ensemble'))
  )

  return {
    ensembleId: (
      normalizeOptionalString(ensembleId)
      || normalizeOptionalString(normalizedContext.ensemble_id)
      || normalizeOptionalString(normalizedScope.ensemble_id)
    ),
    clusterId: (
      resolvedLevel === 'ensemble'
        ? null
        : (
            normalizeOptionalString(clusterId)
            || normalizeOptionalString(normalizedContext.cluster_id)
            || normalizeOptionalString(normalizedScope.cluster_id)
            || normalizeOptionalString(normalizedSelectedCluster.cluster_id)
          )
    ),
    runId: (
      resolvedLevel === 'run'
        ? (
            normalizeOptionalString(runId)
            || normalizeOptionalString(normalizedContext.run_id)
            || normalizeOptionalString(normalizedScope.run_id)
            || normalizeOptionalString(normalizedSelectedRun.run_id)
          )
        : null
    ),
    representativeRunId: (
      resolvedLevel === 'ensemble'
        ? null
        : (
            normalizeOptionalString(normalizedScope.representative_run_id)
            || normalizeOptionalString(normalizedSelectedCluster.prototype_run_id)
            || normalizeOptionalString(normalizedSelectedRun.run_id)
          )
    ),
    source: (
      normalizeOptionalString(normalizedScope.source)
      || (normalizeOptionalString(normalizedSelectedCluster.cluster_id) ? 'derived_membership' : 'route')
    ),
    level: resolvedLevel
  }
}

const buildScopeSupportLabel = (support = {}) => {
  const preparedRunCount = normalizeNonNegativeInteger(support?.prepared_run_count)
  const runsWithMetrics = normalizeNonNegativeInteger(support?.runs_with_metrics)

  if (runsWithMetrics !== null && preparedRunCount !== null) {
    return `${runsWithMetrics} of ${preparedRunCount} runs with metrics`
  }
  if (preparedRunCount !== null) {
    return `${preparedRunCount} prepared runs`
  }
  return 'Support counts unavailable'
}

const buildSelectedRunSupportLabel = (selectedRun = {}) => {
  const support = normalizeAnalyticsRecord(selectedRun?.support) || {}
  const keyMetricCount = (
    normalizeNonNegativeInteger(support.key_metric_count)
    ?? (Array.isArray(selectedRun?.key_metrics) ? selectedRun.key_metrics.length : null)
  )

  if (keyMetricCount !== null) {
    return `${keyMetricCount} key metric${keyMetricCount === 1 ? '' : 's'} surfaced`
  }

  return 'Key metric support unavailable'
}

const getReadyCalibrationMetric = (reportContext = null) => {
  const normalizedContext = normalizeAnalyticsRecord(reportContext) || {}
  const calibratedSummary = normalizeAnalyticsRecord(normalizedContext.calibrated_summary) || {}
  const metrics = Array.isArray(calibratedSummary.metrics)
    ? calibratedSummary.metrics
    : []

  for (const metric of metrics) {
    if (metric?.readiness?.ready === true) {
      return normalizeAnalyticsRecord(metric)
    }
  }

  return normalizeAnalyticsRecord(metrics[0]) || null
}

const buildCalibrationSummary = (metric = null) => {
  if (!metric) {
    return ''
  }

  const scoringRules = normalizeStringList(metric.supported_scoring_rules)
    .map((rule) => formatScoringRuleLabel(rule))
    .filter(Boolean)
  const caseCount = (
    normalizeNonNegativeInteger(metric?.readiness?.actual_case_count)
    ?? normalizeNonNegativeInteger(metric?.case_count)
  )
  const nonEmptyBinCount = (
    normalizeNonNegativeInteger(metric?.readiness?.non_empty_bin_count)
    ?? countNonEmptyReliabilityBins(metric?.reliability_bins)
  )

  const parts = []
  if (scoringRules.length) {
    parts.push(scoringRules.join(' + '))
  }
  if (caseCount !== null) {
    parts.push(`${caseCount} resolved cases`)
  }
  if (nonEmptyBinCount !== null) {
    parts.push(`${nonEmptyBinCount} non-empty reliability bins`)
  }

  return parts.join('; ')
}

const normalizeGroundingCitationCounts = (counts = {}) => ({
  source: normalizeNonNegativeInteger(counts?.source) ?? 0,
  graph: normalizeNonNegativeInteger(counts?.graph) ?? 0,
  code: normalizeNonNegativeInteger(counts?.code) ?? 0
})

const buildGroundingSummary = (reportContext = null) => {
  const normalizedContext = normalizeAnalyticsRecord(reportContext) || {}
  const groundingContext = normalizeAnalyticsRecord(normalizedContext.grounding_context)

  if (!groundingContext) {
    return null
  }

  const evidenceItems = Array.isArray(groundingContext.evidence_items)
    ? groundingContext.evidence_items
      .filter((item) => item && typeof item === 'object')
      .slice(0, 5)
      .map((item) => ({
        citationId: normalizeOptionalString(item.citation_id),
        kind: normalizeOptionalString(item.kind) || 'evidence',
        title: normalizeOptionalString(item.title) || 'Untitled evidence',
        summary: normalizeOptionalString(item.summary) || '',
        locator: normalizeOptionalString(item.locator) || '',
        supportLabel: normalizeOptionalString(item.support_label) || ''
      }))
    : []

  return {
    status: normalizeOptionalString(groundingContext.status) || 'unavailable',
    boundaryNote: normalizeOptionalString(groundingContext.boundary_note) || '',
    citationCounts: normalizeGroundingCitationCounts(groundingContext.citation_counts),
    warnings: normalizeWarningList(groundingContext.warnings),
    evidenceCount: (
      normalizeNonNegativeInteger(groundingContext.evidence_count)
      ?? evidenceItems.length
    ),
    evidenceItems
  }
}

const normalizeCompareScope = (scope = {}) => {
  const normalizedScope = normalizeAnalyticsRecord(scope) || {}
  return {
    level: normalizeOptionalString(normalizedScope.level) || null,
    ensembleId: normalizeOptionalString(normalizedScope.ensemble_id) || null,
    clusterId: normalizeOptionalString(normalizedScope.cluster_id) || null,
    runId: normalizeOptionalString(normalizedScope.run_id) || null
  }
}

const normalizeCompareOptions = (compareOptions = []) => {
  if (!Array.isArray(compareOptions)) {
    return []
  }

  return compareOptions
    .filter((option) => option && typeof option === 'object')
    .map((option) => ({
      compareId: normalizeOptionalString(option.compare_id) || null,
      reason: normalizeOptionalString(option.reason) || '',
      label: normalizeOptionalString(option.label) || 'Compare current evidence',
      prompt: normalizeOptionalString(option.prompt) || 'Compare the current probabilistic scopes using only persisted evidence, support counts, warnings, and representative runs.',
      left: normalizeCompareScope(option.left),
      right: normalizeCompareScope(option.right)
    }))
}

const normalizeCompareSnapshot = (snapshot = {}) => {
  const normalizedSnapshot = normalizeAnalyticsRecord(snapshot) || {}
  return {
    scope: normalizeCompareScope(normalizedSnapshot.scope),
    headline: normalizeOptionalString(normalizedSnapshot.headline) || 'Unavailable scope',
    supportLabel: normalizeOptionalString(normalizedSnapshot.support_label) || 'Support unavailable',
    semantics: normalizeOptionalString(normalizedSnapshot.semantics) || 'empirical',
    representativeRunIds: normalizeStringList(normalizedSnapshot.representative_run_ids),
    warnings: normalizeWarningList(normalizedSnapshot.warnings),
    evidenceHighlights: normalizeStringList(normalizedSnapshot.evidence_highlights),
    confidenceStatus: normalizeOptionalString(normalizedSnapshot.confidence_status) || null,
    groundingStatus: normalizeOptionalString(normalizedSnapshot.grounding_status) || null
  }
}

const normalizeCompareSummary = (summary = {}) => {
  const normalizedSummary = normalizeAnalyticsRecord(summary) || {}
  return {
    whatDiffers: normalizeStringList(normalizedSummary.what_differs),
    weakSupport: normalizeStringList(normalizedSummary.weak_support),
    boundaryNote: normalizeOptionalString(normalizedSummary.boundary_note) || ''
  }
}

const normalizeCompareCatalog = (compareCatalog = null) => {
  const normalizedCatalog = normalizeAnalyticsRecord(compareCatalog)
  if (!normalizedCatalog) {
    return {
      boundaryNote: '',
      options: []
    }
  }

  return {
    boundaryNote: normalizeOptionalString(normalizedCatalog.boundary_note) || '',
    options: Array.isArray(normalizedCatalog.options)
      ? normalizedCatalog.options
        .filter((option) => option && typeof option === 'object')
        .map((option) => ({
          compareId: normalizeOptionalString(option.compare_id) || null,
          label: normalizeOptionalString(option.label) || 'Compare current evidence',
          reason: normalizeOptionalString(option.reason) || '',
          leftScope: normalizeCompareScope(option.left_scope),
          rightScope: normalizeCompareScope(option.right_scope),
          leftSnapshot: normalizeCompareSnapshot(option.left_snapshot),
          rightSnapshot: normalizeCompareSnapshot(option.right_snapshot),
          comparisonSummary: normalizeCompareSummary(option.comparison_summary),
          warnings: normalizeWarningList(option.warnings),
          prompt: normalizeOptionalString(option.prompt) || 'Compare the current probabilistic scopes using only persisted evidence, support counts, warnings, and representative runs.'
        }))
      : []
  }
}

const buildComparePrompts = ({
  scope,
  selectedRun,
  selectedCluster,
  compareOptions,
  compareCatalog,
  selectedCompare,
  representativeRunIds,
  scenarioFamilies,
  topOutcomes
} = {}) => {
  const prompts = []
  if (selectedCompare?.prompt) {
    prompts.push({
      label: selectedCompare.label || 'Selected compare',
      prompt: selectedCompare.prompt
    })
  }
  const structuredComparePrompts = Array.isArray(compareOptions)
    ? compareOptions
      .filter((option) => option && typeof option === 'object')
      .map((option) => ({
        label: normalizeOptionalString(option.label) || 'Compare current evidence',
        prompt: normalizeOptionalString(option.prompt) || 'Compare the current probabilistic scopes using only persisted evidence, support counts, warnings, and representative runs.'
      }))
    : []
  const catalogPrompts = Array.isArray(compareCatalog?.options)
    ? compareCatalog.options
      .filter((option) => option && typeof option === 'object' && option.prompt)
      .map((option) => ({
        label: normalizeOptionalString(option.label) || 'Compare current evidence',
        prompt: normalizeOptionalString(option.prompt) || 'Compare the current probabilistic scopes using only persisted evidence, support counts, warnings, and representative runs.'
      }))
    : []
  const selectedRunId = normalizeOptionalString(selectedRun?.run_id) || scope.runId
  const comparisonRunId = representativeRunIds.find((candidateId) => candidateId !== selectedRunId)
  const topOutcome = Array.isArray(topOutcomes) ? topOutcomes[0] : null
  const firstFamily = Array.isArray(scenarioFamilies) ? scenarioFamilies[0] : null
  const secondFamily = Array.isArray(scenarioFamilies) ? scenarioFamilies[1] : null

  if (selectedRunId && comparisonRunId) {
    prompts.push({
      label: `Run ${selectedRunId} vs ${comparisonRunId}`,
      prompt: `Compare run ${selectedRunId} against representative run ${comparisonRunId}. Focus on support counts, distinguishing outcomes, warnings, and assumption ledger differences only.`
    })
  }

  if (firstFamily?.cluster_id && secondFamily?.cluster_id) {
    prompts.push({
      label: `${firstFamily.cluster_id} vs ${secondFamily.cluster_id}`,
      prompt: `Compare scenario family ${firstFamily.cluster_id} against ${secondFamily.cluster_id}. Focus on probability mass, support counts, distinguishing metrics, representative runs, and explicit warnings only.`
    })
  }

  if (selectedCluster?.cluster_id && topOutcome?.metric_id) {
    prompts.push({
      label: `${selectedCluster.cluster_id} vs ensemble`,
      prompt: `Explain how scenario family ${selectedCluster.cluster_id} differs from the ensemble summary for ${topOutcome.metric_id}. Use only observed metrics, representative runs, support counts, and warnings.`
    })
  }

  if (selectedRunId && topOutcome?.metric_id) {
    prompts.push({
      label: `${selectedRunId} vs ensemble`,
      prompt: `Explain how selected run ${selectedRunId} differs from the ensemble summary for ${topOutcome.metric_id}. Use only observed metrics, representative runs, support counts, and assumption ledger details.`
    })
  }

  if (!prompts.length && scope.ensembleId) {
    prompts.push({
      label: 'Summarize current evidence',
      prompt: `Summarize the current probabilistic evidence for ensemble ${scope.ensembleId}${scope.runId ? ` and run ${scope.runId}` : ''}. Focus on support, warnings, provenance, and representative runs only.`
    })
  }

  for (const prompt of structuredComparePrompts) {
    if (prompts.some((existingPrompt) => existingPrompt.label === prompt.label)) {
      continue
    }
    prompts.push(prompt)
  }

  for (const prompt of catalogPrompts) {
    if (prompts.some((existingPrompt) => existingPrompt.label === prompt.label)) {
      continue
    }
    prompts.push(prompt)
  }

  return prompts.slice(0, 3)
}

export const deriveProbabilisticEvidenceSummary = ({
  runtimeMode = LEGACY_RUNTIME_MODE,
  ensembleId = null,
  clusterId = null,
  runId = null,
  scopeLevel = null,
  compareId = null,
  reportContext = null
} = {}) => {
  const isProbabilisticRuntime = (
    normalizeRuntimeMode(runtimeMode) === PROBABILISTIC_RUNTIME_MODE
  )
  const normalizedContext = normalizeAnalyticsRecord(reportContext) || {}
  const hasContext = Object.keys(normalizedContext).length > 0
  const scope = resolveProbabilisticScope({
    ensembleId,
    clusterId,
    runId,
    scopeLevel,
    reportContext: normalizedContext
  })
  const representativeRuns = Array.isArray(normalizedContext.representative_runs)
    ? normalizedContext.representative_runs
    : []
  const representativeRunIds = representativeRuns
    .map((run) => normalizeOptionalString(run?.run_id))
    .filter(Boolean)
  const selectedRun = normalizeAnalyticsRecord(normalizedContext.selected_run)
  const selectedCluster = normalizeAnalyticsRecord(normalizedContext.selected_cluster)
  const selectedRunLedger = normalizeAnalyticsRecord(selectedRun?.assumption_ledger) || {}
  const confidenceStatus = normalizeConfidenceStatus(normalizedContext)
  const calibrationProvenance = normalizeAnalyticsRecord(normalizedContext.calibration_provenance)
  const calibrationMetric = getReadyCalibrationMetric(normalizedContext)
  const ensembleSupport = normalizeAnalyticsRecord(normalizedContext.ensemble_facts?.support) || {}
  const selectedRunTemplates = normalizeStringList(selectedRunLedger.applied_templates)
  const selectedRunNotes = normalizeStringList(selectedRunLedger.notes)
  const calibrationSummaryText = buildCalibrationSummary(calibrationMetric)
  const groundingSummary = buildGroundingSummary(normalizedContext)

  const compareOptions = normalizeCompareOptions(
    Array.isArray(normalizedContext.compare_options)
      ? normalizedContext.compare_options
      : (Array.isArray(normalizedContext.scope_catalog?.compare_options)
        ? normalizedContext.scope_catalog.compare_options
        : [])
  )
  const compareCatalog = normalizeCompareCatalog(normalizedContext.compare_catalog)
  const selectedCompareId = normalizeOptionalString(compareId)
  const selectedCompare = compareCatalog.options.find(
    (option) => option.compareId && option.compareId === selectedCompareId
  ) || null
  const scopeSupportLabel = selectedCluster?.support?.label
    || buildScopeSupportLabel(ensembleSupport)

  return {
    available: isProbabilisticRuntime && (hasContext || Boolean(scope.ensembleId || scope.runId || scope.clusterId)),
    scope: {
      level: scope.level,
      ensembleId: scope.ensembleId,
      clusterId: scope.clusterId,
      runId: scope.runId,
      representativeRunId: scope.representativeRunId,
      source: scope.source,
      supportLabel: scopeSupportLabel,
      representativeRunIds,
      representativeRunCount: representativeRunIds.length,
      warnings: normalizeWarningList(normalizedContext.quality_summary?.warnings)
    },
    selectedCluster: selectedCluster
      ? {
          clusterId: normalizeOptionalString(selectedCluster.cluster_id),
          familyLabel: normalizeOptionalString(selectedCluster.family_label) || null,
          familySummary: normalizeOptionalString(selectedCluster.family_summary) || null
        }
      : null,
    selectedRun: selectedRun
      ? {
          runId: normalizeOptionalString(selectedRun.run_id),
          qualityStatus: normalizeOptionalString(selectedRun.quality_status) || 'unknown',
          supportLabel: buildSelectedRunSupportLabel(selectedRun),
          assumptionTemplates: selectedRunTemplates,
          assumptionNotes: selectedRunNotes,
          assumptionSummary: selectedRunTemplates.length
            ? `Templates: ${selectedRunTemplates.join(', ')}`
            : (selectedRunNotes[0] || 'No assumption ledger details stored')
        }
      : null,
    confidenceStatus,
    calibration: calibrationProvenance
      ? {
          mode: normalizeOptionalString(calibrationProvenance.mode) || 'calibrated',
          readyMetricIds: normalizeStringList(calibrationProvenance.ready_metric_ids),
          qualityStatus: normalizeOptionalString(calibrationProvenance.quality_status) || 'unknown',
          warnings: normalizeWarningList(calibrationProvenance.warnings),
          summary: calibrationSummaryText,
          confidenceLabel: normalizeOptionalString(calibrationMetric?.readiness?.confidence_label) || null
        }
      : null,
    grounding: groundingSummary,
    compareOptions,
    compareCatalog,
    selectedCompare,
    comparePrompts: buildComparePrompts({
      scope,
      selectedRun,
      selectedCluster,
      compareOptions,
      compareCatalog,
      selectedCompare,
      representativeRunIds,
      scenarioFamilies: Array.isArray(normalizedContext.scenario_families)
        ? normalizedContext.scenario_families
        : [],
      topOutcomes: Array.isArray(normalizedContext.top_outcomes)
        ? normalizedContext.top_outcomes
        : []
    })
  }
}

const getDominantCategory = (metricSummary = {}) => {
  const dominantValue = normalizeOptionalString(metricSummary?.dominant_value)
  if (dominantValue) {
    return dominantValue
  }

  const categoryCounts = metricSummary?.category_counts
  if (!categoryCounts || typeof categoryCounts !== 'object') {
    return null
  }

  const ranked = Object.entries(categoryCounts)
    .filter(([, count]) => typeof count === 'number' && Number.isFinite(count))
    .sort((left, right) => {
      if (right[1] !== left[1]) {
        return right[1] - left[1]
      }
      return String(left[0]).localeCompare(String(right[0]))
    })

  return ranked[0]?.[0] || null
}

const buildSummaryHeadline = (metricSummary, metricLabel) => {
  if (!metricSummary) {
    return 'Aggregate metrics available'
  }

  if (metricSummary.distribution_kind === 'binary') {
    const probability = formatProbabilityMass(metricSummary.empirical_probability)
    return `${metricLabel}: ${probability || '-'} true`
  }

  if (metricSummary.distribution_kind === 'categorical') {
    const dominantCategory = getDominantCategory(metricSummary)
    return dominantCategory
      ? `${metricLabel}: ${dominantCategory}`
      : `${metricLabel}: categorical summary`
  }

  const mean = formatAnalyticsNumber(metricSummary.mean)
  return `${metricLabel}: mean ${mean ?? '-'}`
}

const buildSummaryBody = (metricSummary) => {
  if (!metricSummary) {
    return 'No aggregate metric summaries were returned for this stored ensemble.'
  }

  const sampleCount = metricSummary.sample_count ?? 0

  if (metricSummary.distribution_kind === 'binary') {
    const trueCount = metricSummary.counts?.true ?? 0
    const falseCount = metricSummary.counts?.false ?? 0
    const probability = formatProbabilityMass(metricSummary.empirical_probability)
    return `${sampleCount} runs contribute to this empirical summary; ${trueCount} true and ${falseCount} false, with ${probability || '-'} observed true overall.`
  }

  if (metricSummary.distribution_kind === 'categorical') {
    const dominantCategory = getDominantCategory(metricSummary)
    const dominantProbability = (
      typeof metricSummary.dominant_probability === 'number'
        ? metricSummary.dominant_probability
        : metricSummary.category_probabilities?.[dominantCategory]
    )
    const dominantCount = dominantCategory
      ? metricSummary.category_counts?.[dominantCategory] ?? 0
      : 0
    return dominantCategory
      ? `${sampleCount} runs contribute to this empirical summary; ${dominantCategory} led with ${dominantCount} of ${sampleCount} runs (${formatProbabilityMass(dominantProbability) || '-'}).`
      : `${sampleCount} runs contribute to this empirical categorical summary.`
  }

  const mean = formatAnalyticsNumber(metricSummary.mean)
  return `${sampleCount} runs contribute to this empirical summary; mean ${mean ?? '-'} with range ${formatAnalyticsNumber(metricSummary.min) ?? '-'} to ${formatAnalyticsNumber(metricSummary.max) ?? '-'}.`
}

const getPreferredMetricSummary = (metricSummaries = {}) => {
  if (!metricSummaries || typeof metricSummaries !== 'object') {
    return null
  }

  if (metricSummaries['simulation.total_actions']) {
    return metricSummaries['simulation.total_actions']
  }

  const [firstMetric] = Object.values(metricSummaries)
  return firstMetric || null
}

const buildSummaryCard = ({ artifact, loading, error }) => {
  if (error) {
    return {
      status: 'error',
      headline: 'Aggregate summary unavailable',
      body: error,
      warnings: []
    }
  }

  if (loading && !artifact) {
    return {
      status: 'loading',
      headline: 'Loading aggregate summary',
      body: 'Loading empirical aggregate metrics for this stored ensemble.',
      warnings: []
    }
  }

  if (!artifact) {
    return {
      status: 'empty',
      headline: 'Aggregate summary not loaded',
      body: 'Aggregate metrics will appear here once the stored ensemble summary is fetched.',
      warnings: []
    }
  }

  const metricSummary = getPreferredMetricSummary(artifact.metric_summaries)
  const metricLabel = metricSummary?.label || 'Aggregate metrics'

  return {
    status: artifact.quality_summary?.status || 'complete',
    headline: buildSummaryHeadline(metricSummary, metricLabel),
    body: buildSummaryBody(metricSummary),
    warnings: normalizeWarningList(artifact.quality_summary?.warnings)
  }
}

const buildClustersCard = ({ artifact, loading, error }) => {
  if (error) {
    return {
      status: 'error',
      headline: 'Scenario clusters unavailable',
      body: error,
      warnings: []
    }
  }

  if (loading && !artifact) {
    return {
      status: 'loading',
      headline: 'Loading scenario clusters',
      body: 'Loading observed cluster groupings for this stored ensemble.',
      warnings: []
    }
  }

  if (!artifact) {
    return {
      status: 'empty',
      headline: 'Scenario clusters not loaded',
      body: 'Cluster groupings will appear here once the stored ensemble cluster artifact is fetched.',
      warnings: []
    }
  }

  const leadCluster = Array.isArray(artifact.clusters) ? artifact.clusters[0] : null
  const clusterCount = artifact.cluster_count ?? 0
  const leadMass = formatProbabilityMass(leadCluster?.probability_mass)
  const prototypeRun = leadCluster?.prototype_run_id || '-'

  return {
    status: artifact.quality_summary?.status || 'complete',
    headline: `${clusterCount} observed clusters`,
    body: leadCluster
      ? `The largest observed cluster currently covers ${leadMass || '-'} of runs, with prototype run ${prototypeRun}.`
      : 'No cluster memberships are available for this stored ensemble yet.',
    warnings: normalizeWarningList(artifact.quality_summary?.warnings)
  }
}

const buildSensitivityCard = ({ artifact, loading, error }) => {
  if (error) {
    return {
      status: 'error',
      headline: 'Sensitivity unavailable',
      body: error,
      warnings: []
    }
  }

  if (loading && !artifact) {
    return {
      status: 'loading',
      headline: 'Loading sensitivity',
      body: 'Loading observational sensitivity rankings for this stored ensemble.',
      warnings: []
    }
  }

  if (!artifact) {
    return {
      status: 'empty',
      headline: 'Sensitivity not loaded',
      body: 'Sensitivity rankings will appear here once the stored ensemble sensitivity artifact is fetched.',
      warnings: []
    }
  }

  const topDriver = Array.isArray(artifact.driver_rankings)
    ? artifact.driver_rankings[0]
    : null
  const topImpact = topDriver?.metric_impacts?.[0] || null
  const warnings = normalizeWarningList(artifact.quality_summary?.warnings)
  const body = topDriver
    ? `Observational only: the strongest observed driver is ${topDriver.field_path || topDriver.driver_id}, with a top effect size of ${formatAnalyticsNumber(topImpact?.effect_size) ?? '-'} on ${topImpact?.metric_id || 'the lead metric'}.`
    : 'No varying drivers were observed across the currently analyzable stored runs.'

  return {
    status: topDriver
      ? (artifact.quality_summary?.status || 'complete')
      : 'empty',
    headline: topDriver
      ? `Top observed driver: ${topDriver.field_path || topDriver.driver_id}`
      : 'No ranked sensitivity drivers',
    body,
    warnings
  }
}

export const deriveProbabilisticAnalyticsCards = ({
  summaryArtifact,
  clustersArtifact,
  sensitivityArtifact,
  loadingByKey = {},
  errorByKey = {}
} = {}) => {
  return {
    summary: buildSummaryCard({
      artifact: normalizeAnalyticsRecord(summaryArtifact),
      loading: loadingByKey.summary === true,
      error: errorByKey.summary || ''
    }),
    clusters: buildClustersCard({
      artifact: normalizeAnalyticsRecord(clustersArtifact),
      loading: loadingByKey.clusters === true,
      error: errorByKey.clusters || ''
    }),
    sensitivity: buildSensitivityCard({
      artifact: normalizeAnalyticsRecord(sensitivityArtifact),
      loading: loadingByKey.sensitivity === true,
      error: errorByKey.sensitivity || ''
    })
  }
}
