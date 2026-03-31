export const FORECAST_REQUIRED_PRIMITIVES = Object.freeze([
  'forecast_question',
  'resolution_criteria',
  'evidence_bundle',
  'forecast_worker',
  'prediction_ledger',
  'evaluation_case',
  'forecast_answer',
  'simulation_worker_contract'
])

const normalizeStringArray = (values = []) => (
  Array.isArray(values)
    ? values
      .map(value => String(value || '').trim())
      .filter(Boolean)
    : []
)

const normalizeOptionalNumber = (value) => {
  const numericValue = Number(value)
  return Number.isFinite(numericValue) ? numericValue : null
}

const normalizeOptionalString = (value) => {
  const normalizedValue = String(value || '').trim()
  return normalizedValue || null
}

const normalizeRecord = (value) => (
  value && typeof value === 'object'
    ? value
    : {}
)

const AVAILABLE_OR_READY_STATUSES = new Set(['available', 'ready'])
const PERCENT_ESTIMATE_SEMANTICS = new Set([
  'forecast_probability',
  'calibrated_probability',
  'probability'
])

const normalizeStatus = (value) => String(value || '').trim()

const formatEstimateNumber = (value) => {
  const numericValue = normalizeOptionalNumber(value)
  if (numericValue === null) {
    return null
  }
  if (Number.isInteger(numericValue)) {
    return `${numericValue}`
  }
  return `${Number.parseFloat(numericValue.toFixed(4))}`
}

const formatQuestionHorizon = (value) => {
  if (value && typeof value === 'object') {
    return String(value.value || value.label || value.type || '').trim()
  }
  return String(value || '').trim()
}

const normalizeDistribution = (value) => {
  if (!value || typeof value !== 'object') {
    return {}
  }
  const entries = Object.entries(value)
    .map(([label, share]) => [String(label || '').trim(), normalizeOptionalNumber(share)])
    .filter(([label, share]) => label && share !== null)
  if (!entries.length) {
    return {}
  }
  return Object.fromEntries(entries)
}

const normalizeIntervals = (value) => {
  if (!value || typeof value !== 'object') {
    return {}
  }
  if (Array.isArray(value)) {
    return Object.fromEntries(
      value
        .map((item) => {
          if (!item || typeof item !== 'object') {
            return null
          }
          const level = normalizeOptionalNumber(item.level)
          const low = normalizeOptionalNumber(item.low)
          const high = normalizeOptionalNumber(item.high)
          if (level === null || low === null || high === null) {
            return null
          }
          return [String(level), { low, high }]
        })
        .filter(Boolean)
    )
  }
  return Object.fromEntries(
    Object.entries(value)
      .map(([level, bounds]) => {
        if (!bounds || typeof bounds !== 'object') {
          return null
        }
        const low = normalizeOptionalNumber(bounds.low)
        const high = normalizeOptionalNumber(bounds.high)
        if (low === null || high === null) {
          return null
        }
        return [String(level), { low, high }]
      })
      .filter(Boolean)
  )
}

const pickDisplayInterval = (intervals = {}) => {
  if (intervals['80']) {
    return ['80', intervals['80']]
  }
  const orderedLevels = Object.keys(intervals)
    .map((level) => Number(level))
    .filter(Number.isFinite)
    .sort((left, right) => right - left)
  if (!orderedLevels.length) {
    return [null, null]
  }
  const level = String(orderedLevels[0])
  return [level, intervals[level] || null]
}

const normalizeBestEstimateDetails = (bestEstimate, latestAnswerPayload = {}) => {
  const estimateRecord = bestEstimate && typeof bestEstimate === 'object'
    ? bestEstimate
    : {}
  const valueType = String(
    estimateRecord.value_type
      || estimateRecord.valueType
      || ''
  ).trim()
  const semantics = String(
    estimateRecord.value_semantics
      || estimateRecord.semantics
      || latestAnswerPayload?.value_semantics
      || latestAnswerPayload?.semantics
      || ''
  ).trim()
  const numericValue = normalizeOptionalNumber(
    estimateRecord.value
      ?? estimateRecord.estimate
      ?? estimateRecord.point_estimate
      ?? estimateRecord.pointEstimate
      ?? latestAnswerPayload?.estimate
  )
  const topLabel = normalizeOptionalString(
    estimateRecord.top_label ?? estimateRecord.topLabel
  )
  const distribution = normalizeDistribution(estimateRecord.distribution)
  const intervals = normalizeIntervals(estimateRecord.intervals)
  const unit = normalizeOptionalString(estimateRecord.unit)
  let topLabelShare = normalizeOptionalNumber(
    estimateRecord.top_label_share ?? estimateRecord.topLabelShare
  )
  let derivedTopLabel = topLabel
  if ((!derivedTopLabel || topLabelShare === null) && Object.keys(distribution).length) {
    const [label, share] = Object.entries(distribution)
      .sort((left, right) => {
        if (right[1] !== left[1]) {
          return right[1] - left[1]
        }
        return left[0].localeCompare(right[0])
      })[0]
    derivedTopLabel = derivedTopLabel || label
    if (topLabelShare === null) {
      topLabelShare = share
    }
  }

  let display = '-'
  if (valueType === 'categorical_distribution' || semantics === 'forecast_distribution') {
    if (derivedTopLabel && topLabelShare !== null) {
      display = `${derivedTopLabel} (${Math.round(topLabelShare * 100)}%)`
    } else if (derivedTopLabel) {
      display = derivedTopLabel
    }
  } else if (valueType === 'numeric_interval' || semantics === 'numeric_interval_estimate') {
    const pointEstimate = numericValue
    if (pointEstimate !== null) {
      const [intervalLevel, intervalBounds] = pickDisplayInterval(intervals)
      const pointText = formatEstimateNumber(pointEstimate)
      const unitSuffix = unit ? ` ${unit}` : ''
      if (intervalLevel && intervalBounds) {
        display = `${pointText}${unitSuffix} (${intervalLevel}% interval ${formatEstimateNumber(intervalBounds.low)} to ${formatEstimateNumber(intervalBounds.high)})`
      } else {
        display = `${pointText}${unitSuffix}`
      }
    }
  } else {
    display = formatForecastBestEstimate(numericValue, semantics)
  }

  return {
    valueType,
    semantics,
    numericValue,
    display,
    topLabel: derivedTopLabel,
    topLabelShare,
    distribution,
    intervals,
    unit
  }
}

export const formatForecastBestEstimate = (value, semantics = '') => {
  if (value && typeof value === 'object') {
    return normalizeBestEstimateDetails(value, {}).display
  }
  const numericValue = normalizeOptionalNumber(value)
  if (numericValue === null) {
    return '-'
  }

  const normalizedSemantics = normalizeStatus(semantics)
  if (PERCENT_ESTIMATE_SEMANTICS.has(normalizedSemantics)) {
    return `${Math.round(numericValue * 100)}%`
  }

  if (!normalizedSemantics) {
    return `${numericValue}`
  }

  return `${numericValue} (${normalizedSemantics.replaceAll('_', ' ')})`
}

export const hasEarnedCalibratedConfidence = ({
  latestAnswer = {},
  confidenceBasis = {},
  calibrationSummary = {}
} = {}) => {
  const confidenceSemantics = normalizeStatus(latestAnswer?.confidence_semantics)
  const confidenceStatus = normalizeStatus(confidenceBasis?.status)
  const resolvedCaseCount = normalizeOptionalNumber(confidenceBasis?.resolved_case_count) || 0
  const calibrationStatus = normalizeStatus(calibrationSummary?.status)
  const benchmarkStatus = normalizeStatus(confidenceBasis?.benchmark_status)
  const backtestStatus = normalizeStatus(confidenceBasis?.backtest_status)

  return (
    confidenceSemantics === 'calibrated'
    && confidenceStatus === 'available'
    && resolvedCaseCount > 0
    && calibrationStatus === 'ready'
    && AVAILABLE_OR_READY_STATUSES.has(benchmarkStatus)
    && AVAILABLE_OR_READY_STATUSES.has(backtestStatus)
  )
}

export const normalizeForecastCapabilities = (payload = {}) => {
  const capabilities = payload?.capabilities && typeof payload.capabilities === 'object'
    ? payload.capabilities
    : payload
  const requiredPrimitives = normalizeStringArray(capabilities.required_primitives)
  const supportedWorkerKinds = normalizeStringArray(capabilities.supported_worker_kinds)
  const supportedQuestionTemplates = Array.isArray(capabilities.supported_question_templates)
    ? capabilities.supported_question_templates
        .filter((template) => template && typeof template === 'object')
        .map((template, index) => ({
          templateId: String(template.template_id || `template-${index + 1}`),
          label: String(template.label || template.prompt_template || `Template ${index + 1}`),
          questionType: String(template.question_type || ''),
          promptTemplate: String(template.prompt_template || ''),
          requiredFields: normalizeStringArray(template.required_fields),
          abstainGuidance: String(template.abstain_guidance || ''),
          notes: normalizeStringArray(template.notes)
        }))
    : []
  const simulation = capabilities?.simulation && typeof capabilities.simulation === 'object'
    ? capabilities.simulation
    : {}

  return {
    requiredPrimitives: requiredPrimitives.length ? requiredPrimitives : [...FORECAST_REQUIRED_PRIMITIVES],
    supportedWorkerKinds,
    supportsHybridWorkers: supportedWorkerKinds.length > 1 && supportedWorkerKinds.includes('simulation'),
    supportedQuestionTemplates,
    simulationRole: String(simulation.role || 'scenario_worker'),
    simulationProbabilityInterpretation: String(
      simulation.probability_interpretation || 'do_not_treat_as_real_world_probability'
    ),
    simulationNotes: normalizeStringArray(simulation.notes)
  }
}

export const summarizeForecastWorkspace = (workspace = {}) => {
  const forecastQuestion = normalizeRecord(workspace?.forecast_question || workspace?.question)
  const predictionLedger = normalizeRecord(workspace?.prediction_ledger || workspace?.predictionLedger)
  const evidenceBundle = normalizeRecord(workspace?.evidence_bundle || workspace?.evidence)
  const resolutionRecord = normalizeRecord(workspace?.resolution_record)
  const scoringEvents = Array.isArray(workspace?.scoring_events)
    ? workspace.scoring_events
    : []
  const latestScoringEvent = (
    scoringEvents.length
      && scoringEvents[scoringEvents.length - 1]
      && typeof scoringEvents[scoringEvents.length - 1] === 'object'
  )
    ? scoringEvents[scoringEvents.length - 1]
    : {}
  const workers = Array.isArray(workspace?.forecast_workers) ? workspace.forecast_workers : []
  const workerKinds = workers
    .map(worker => String(worker?.kind || '').trim())
    .filter(Boolean)
  const simulationWorkerCount = workerKinds.filter(kind => kind === 'simulation').length
  const answers = Array.isArray(workspace?.forecast_answers) ? workspace.forecast_answers : []
  const latestAnswer = answers.length && answers[answers.length - 1] && typeof answers[answers.length - 1] === 'object'
    ? answers[answers.length - 1]
    : {}
  const latestAnswerPayload = latestAnswer?.answer_payload && typeof latestAnswer.answer_payload === 'object'
    ? latestAnswer.answer_payload
    : {}
  const calibrationSummary = normalizeRecord(latestAnswer?.calibration_summary)
  const predictionEntries = Array.isArray(predictionLedger?.entries)
    ? predictionLedger.entries
    : []
  const workerOutputs = Array.isArray(predictionLedger?.worker_outputs)
    ? predictionLedger.worker_outputs
    : []
  const evaluationCases = Array.isArray(workspace?.evaluation_cases)
    ? workspace.evaluation_cases
    : []
  const finalResolutionStateRaw = predictionLedger?.final_resolution_state
  const finalResolutionState = typeof finalResolutionStateRaw === 'string'
    ? finalResolutionStateRaw
    : String(
      resolutionRecord?.status
      || finalResolutionStateRaw?.status
      || predictionLedger?.resolution_status
      || 'pending'
    )
  const evidenceUncertaintyCauses = Array.isArray(evidenceBundle?.uncertainty_summary?.causes)
    ? evidenceBundle.uncertainty_summary.causes
      .map(cause => String(cause || '').trim())
      .filter(Boolean)
    : []
  const supportedQuestionTemplateDetails = Array.isArray(forecastQuestion?.supported_question_templates)
    ? forecastQuestion.supported_question_templates
      .map((template) => (template && typeof template === 'object' ? template : null))
      .filter(Boolean)
      .map((template, index) => ({
        templateId: String(template.template_id || `${forecastQuestion?.forecast_id || 'forecast'}-template-${index + 1}`),
        label: String(template.label || template.prompt_template || `Template ${index + 1}`),
        promptTemplate: String(template.prompt_template || ''),
        questionType: String(template.question_type || forecastQuestion.question_type || ''),
        requiredFields: normalizeStringArray(template.required_fields),
        abstainGuidance: String(template.abstain_guidance || ''),
        notes: normalizeStringArray(template.notes)
      }))
    : []
  const supportedQuestionTemplates = Array.isArray(forecastQuestion?.supported_question_templates)
    ? forecastQuestion.supported_question_templates
      .map((template, index) => {
        if (typeof template === 'string') {
          return template.trim()
        }
        if (template && typeof template === 'object') {
          return String(template.label || template.question_text || template.template_id || `Template ${index + 1}`).trim()
        }
        return ''
      })
      .filter(Boolean)
    : supportedQuestionTemplateDetails.map(template => template.label)
  const bestEstimate = latestAnswerPayload?.best_estimate && typeof latestAnswerPayload.best_estimate === 'object'
    ? latestAnswerPayload.best_estimate
    : null
  const bestEstimateDetails = normalizeBestEstimateDetails(bestEstimate, latestAnswerPayload)
  const workerTrace = Array.isArray(latestAnswerPayload?.worker_contribution_trace)
    ? latestAnswerPayload.worker_contribution_trace
    : []
  const confidenceBasis = normalizeRecord(
    latestAnswerPayload?.confidence_basis
    || predictionLedger?.confidence_basis
  )
  const evaluationSummary = normalizeRecord(
    latestAnswerPayload?.evaluation_summary
    || predictionLedger?.evaluation_summary
  )
  const simulationContext = normalizeRecord(
    latestAnswerPayload?.simulation_context
    || predictionLedger?.simulation_context
  )
  const evidenceEntryCount = Array.isArray(evidenceBundle.source_entries)
    ? evidenceBundle.source_entries.length
    : (Array.isArray(evidenceBundle.entries) ? evidenceBundle.entries.length : 0)
  const evidenceStatus = String(evidenceBundle.status || 'unavailable')
  const evidenceFreshness = String(
    evidenceBundle.freshness_status
    || evidenceBundle.freshness
    || 'unknown'
  )
  const evidenceRelevance = String(
    evidenceBundle.relevance_status
    || evidenceBundle.relevance
    || 'unknown'
  )
  const evidenceConflictCount = Array.isArray(evidenceBundle.conflict_markers)
    ? evidenceBundle.conflict_markers.length
    : 0
  const missingEvidenceCount = Array.isArray(evidenceBundle.missing_evidence_markers)
    ? evidenceBundle.missing_evidence_markers.length
    : 0
  const evidenceQualityScore = normalizeOptionalNumber(
    evidenceBundle.quality_score
    || evidenceBundle.retrieval_quality?.score
    || evidenceBundle.retrieval_quality?.quality_score
  )
  const evidenceAvailable = (
    evidenceStatus === 'ready'
    || evidenceStatus === 'partial'
    || evidenceEntryCount > 0
  )
  const resolvedCaseCount = normalizeOptionalNumber(
    evaluationSummary?.resolved_case_count
    ?? confidenceBasis?.resolved_case_count
  ) || 0
  const evaluationAvailable = (
    evaluationCases.length > 0
    || String(evaluationSummary.status || '') === 'available'
    || resolvedCaseCount > 0
  )
  const latestAnswerAbstained = Boolean(
    latestAnswerPayload?.abstain ?? latestAnswerPayload?.abstained
  )
  const calibratedConfidenceEarned = (
    !latestAnswerAbstained
    && hasEarnedCalibratedConfidence({
      latestAnswer,
      confidenceBasis,
      calibrationSummary
    })
  )
  const simulationOnlyScenarioExploration = (
    simulationWorkerCount > 0
    && simulationWorkerCount === workerKinds.length
  )

  return {
    forecastId: String(forecastQuestion.forecast_id || ''),
    title: String(forecastQuestion.title || ''),
    questionText: String(forecastQuestion.question_text || forecastQuestion.question || ''),
    questionType: String(forecastQuestion.question_type || forecastQuestion.type || ''),
    questionHorizon: formatQuestionHorizon(forecastQuestion.horizon || forecastQuestion.time_horizon || ''),
    issuedAt: String(forecastQuestion.issued_at || forecastQuestion.issue_timestamp || ''),
    owner: String(forecastQuestion.owner || forecastQuestion.source || ''),
    source: String(forecastQuestion.source || forecastQuestion.owner || ''),
    decompositionSupport: Array.isArray(forecastQuestion.decomposition_support)
      ? forecastQuestion.decomposition_support.map(item => String(item || '').trim()).filter(Boolean)
      : [],
    abstentionConditions: Array.isArray(forecastQuestion.abstention_conditions)
      ? forecastQuestion.abstention_conditions.map(item => String(item || '').trim()).filter(Boolean)
      : [],
    supportedQuestionTemplates,
    supportedQuestionTemplateDetails,
    finalResolutionState,
    resolutionStatus: String(resolutionRecord.status || finalResolutionState),
    resolvedAt: String(
      resolutionRecord.resolved_at
      || predictionLedger.resolved_at
      || ''
    ),
    resolutionNote: String(
      resolutionRecord.resolution_note
      || predictionLedger.resolution_note
      || ''
    ),
    scoringEventCount: scoringEvents.length,
    latestScoringMethod: String(latestScoringEvent.scoring_method || ''),
    latestScoreValue: normalizeOptionalNumber(latestScoringEvent.score_value),
    workerCount: workers.length,
    simulationWorkerCount,
    simulationIsOnlyWorker: simulationWorkerCount > 0 && simulationWorkerCount === workers.length,
    hasHybridWorkers: new Set(workerKinds).size > 1,
    predictionEntryCount: predictionEntries.length,
    workerOutputCount: workerOutputs.length,
    evaluationCaseCount: evaluationCases.length,
    resolvedEvaluationCaseCount: evaluationCases.filter(caseItem => String(caseItem?.status || '') === 'resolved').length,
    answerCount: answers.length,
    latestAnswerType: String(latestAnswer?.answer_type || ''),
    latestAnswerAbstained: Boolean(latestAnswerPayload?.abstain ?? latestAnswerPayload?.abstained),
    latestBestEstimate: bestEstimateDetails.numericValue,
    latestBestEstimateValueType: bestEstimateDetails.valueType,
    latestBestEstimateSemantics: bestEstimateDetails.semantics,
    latestBestEstimateDisplay: bestEstimateDetails.display,
    latestBestEstimateTopLabel: bestEstimateDetails.topLabel,
    latestBestEstimateTopLabelShare: bestEstimateDetails.topLabelShare,
    latestBestEstimateDistribution: bestEstimateDetails.distribution,
    latestBestEstimateIntervals: bestEstimateDetails.intervals,
    latestBestEstimateUnit: bestEstimateDetails.unit,
    latestBestEstimateWhy: String(bestEstimate?.why || latestAnswerPayload?.why || ''),
    latestCounterevidence: Array.isArray(latestAnswerPayload?.counterevidence)
      ? latestAnswerPayload.counterevidence.map(item => String(item || '').trim()).filter(Boolean)
      : [],
    latestAssumptionItems: Array.isArray(latestAnswerPayload?.assumption_summary?.items)
      ? latestAnswerPayload.assumption_summary.items.map(item => String(item || '').trim()).filter(Boolean)
      : [],
    latestUncertaintyComponents: Array.isArray(latestAnswerPayload?.uncertainty_decomposition?.components)
      ? latestAnswerPayload.uncertainty_decomposition.components
          .map(item => String(item?.summary || item?.code || '').trim())
          .filter(Boolean)
      : [],
    latestWorkerComparison: workerTrace.map(item => String(item?.summary || item?.worker_id || '').trim()).filter(Boolean),
    latestSimulationObservedRunShare: simulationContext
      ? normalizeOptionalNumber(simulationContext.observed_run_share)
      : null,
    latestSimulationContext: simulationContext,
    confidenceBasis,
    calibrationSummary,
    evaluationSummary,
    hasSimulationWorkerContract: Boolean(workspace?.simulation_worker_contract),
    evidenceBundleStatus: evidenceStatus,
    evidenceEntryCount,
    evidenceFreshness,
    evidenceRelevance,
    evidenceConflictCount,
    missingEvidenceCount,
    evidenceQualityScore,
    retrievalQualityStatus: String(evidenceBundle?.retrieval_quality?.status || ''),
    evidenceUncertaintyCauses,
    forecastWorkspaceStatus: String(workspace?.forecast_workspace_status || (answers.length ? 'available' : 'unavailable')),
    statusSurface: {
      evidenceAvailable,
      evaluationAvailable,
      calibratedConfidenceEarned,
      simulationOnlyScenarioExploration
    },
    latestAnswerAbstainReason: String(latestAnswerPayload?.abstain_reason || ''),
    latestAnswerWorkerTrace: workerTrace,
    latestAnswerPayload,
    latestAnswer,
    forecastAnswer: latestAnswer,
    predictionLedger,
    resolutionRecord,
    scoringEvents
  }
}
