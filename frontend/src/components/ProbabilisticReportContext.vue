<template>
  <section
    v-if="shouldRender"
    class="report-context-card"
    :class="`tone-${cardTone}`"
    data-testid="probabilistic-report-context"
  >
    <div class="report-context-header">
      <div>
        <span class="context-eyebrow">{{ contextEyebrow }}</span>
        <h3 class="context-title">{{ contextTitle }}</h3>
      </div>
      <div class="context-meta mono">
        <span>E {{ ensembleId || '-' }}</span>
        <span>C {{ clusterId || '-' }}</span>
        <span>R {{ runId || '-' }}</span>
      </div>
    </div>

    <p class="context-copy">
      {{ contextCopy }}
    </p>

    <div v-if="contextError" class="context-banner error">
      {{ contextError }}
    </div>
    <template v-else>
      <div v-if="capabilitiesLoading" class="context-banner neutral">
        Loading probabilistic report capabilities...
      </div>
      <div v-if="isFlaggedOff && !hasViewableReportContext" class="context-banner warning">
        Scoped report evidence surfaces are disabled by the backend flag. The legacy report remains available without
        ensemble analytics cards.
      </div>
      <template v-if="hasViewableReportContext">
      <div v-if="historicalNotice" class="context-banner warning">
        {{ historicalNotice }}
      </div>
      <div class="context-pill-row">
        <span class="context-pill">{{ evidenceSummary.forecastObject || evidenceSummary.hybridWorkspace?.available ? 'Forecast object first' : 'Scoped evidence addendum' }}</span>
        <span class="context-pill">{{ scopePillLabel }}</span>
        <span class="context-pill">
          {{ evidenceSummary.hybridWorkspace?.statusSurface?.calibratedConfidenceEarned ? 'Calibrated confidence earned' : 'No calibrated claims' }}
        </span>
      </div>
      <div
        v-if="evidenceSummary.hybridWorkspace?.available"
        class="context-pill-row"
        data-testid="probabilistic-hybrid-status"
      >
        <span class="context-pill capability">
          Evidence available: {{ evidenceSummary.hybridWorkspace.statusSurface.evidenceAvailable ? 'yes' : 'no' }}
        </span>
        <span class="context-pill epistemic">
          Evaluation available: {{ evidenceSummary.hybridWorkspace.statusSurface.evaluationAvailable ? 'yes' : 'no' }}
        </span>
        <span class="context-pill epistemic">
          Calibrated confidence earned: {{ evidenceSummary.hybridWorkspace.statusSurface.calibratedConfidenceEarned ? 'yes' : 'no' }}
        </span>
        <span class="context-pill capability">
          Simulation-only scenario exploration: {{ evidenceSummary.hybridWorkspace.statusSurface.simulationOnlyScenarioExploration ? 'yes' : 'no' }}
        </span>
      </div>

      <div v-if="evidenceEntries.length" class="context-evidence-grid">
        <article
          v-for="entry in evidenceEntries"
          :key="entry.key"
          class="context-evidence-card"
        >
          <div class="context-evidence-label">{{ entry.title }}</div>
          <div class="context-evidence-headline">{{ entry.headline }}</div>
          <p class="context-evidence-body">{{ entry.body }}</p>
          <div v-if="entry.key === 'compare' && evidenceSummary.comparePrompts.length" class="context-compare-list">
            <span
              v-for="prompt in evidenceSummary.comparePrompts"
              :key="prompt.label"
              class="context-compare-chip"
            >
              {{ prompt.label }}
            </span>
          </div>
          <div
            v-else-if="entry.chips && entry.chips.length"
            class="context-warning-list"
          >
            <span
              v-for="chip in entry.chips"
              :key="`${entry.key}-${chip}`"
              class="context-warning-chip"
            >
              {{ chip }}
            </span>
          </div>
        </article>
      </div>

      <section
        v-if="evidenceSummary.compareCatalog?.options?.length"
        class="context-compare-workspace"
        data-testid="probabilistic-compare-workspace"
      >
        <div class="context-compare-header">
          <div>
            <div class="context-evidence-label">Compare Evidence</div>
            <div class="context-compare-title">Bounded scope comparison</div>
          </div>
          <div class="context-compare-boundary">
            {{ evidenceSummary.compareCatalog.boundaryNote }}
          </div>
        </div>

        <div class="context-compare-picker">
          <button
            v-for="option in evidenceSummary.compareCatalog.options"
            :key="option.compareId"
            type="button"
            class="context-compare-picker-btn"
            data-testid="probabilistic-compare-option"
            :class="{ active: option.compareId === evidenceSummary.selectedCompare?.compareId }"
            @click="selectCompareOption(option.compareId)"
          >
            <span class="context-compare-picker-label">{{ option.label }}</span>
            <span v-if="option.reason" class="context-compare-picker-reason">{{ option.reason }}</span>
          </button>
        </div>

        <div v-if="evidenceSummary.selectedCompare" class="context-compare-detail">
          <article class="context-compare-scope-card">
            <div class="context-evidence-label">Left Scope</div>
            <div class="context-compare-scope-headline">{{ evidenceSummary.selectedCompare.leftSnapshot.headline }}</div>
            <div
              class="context-compare-scope-identity mono"
              data-testid="probabilistic-compare-scope-identity"
            >
              <span
                v-for="part in buildCompareScopeIdentityParts(evidenceSummary.selectedCompare.leftSnapshot)"
                :key="`left-scope-${part}`"
                class="context-compare-scope-part"
              >
                {{ part }}
              </span>
            </div>
            <p class="context-evidence-body">{{ evidenceSummary.selectedCompare.leftSnapshot.supportLabel }}</p>
            <div class="context-warning-list">
              <span class="context-warning-chip">{{ evidenceSummary.selectedCompare.leftSnapshot.semantics }}</span>
              <span
                v-for="runIdValue in evidenceSummary.selectedCompare.leftSnapshot.representativeRunIds"
                :key="`left-rep-${runIdValue}`"
                class="context-warning-chip"
              >
                Rep {{ runIdValue }}
              </span>
              <span
                v-for="highlight in evidenceSummary.selectedCompare.leftSnapshot.evidenceHighlights"
                :key="`left-highlight-${highlight}`"
                class="context-warning-chip"
              >
                {{ highlight }}
              </span>
              <span
                v-for="warning in evidenceSummary.selectedCompare.leftSnapshot.warnings"
                :key="`left-warning-${warning}`"
                class="context-warning-chip"
              >
                {{ warning }}
              </span>
            </div>
          </article>

          <article class="context-compare-scope-card">
            <div class="context-evidence-label">Right Scope</div>
            <div class="context-compare-scope-headline">{{ evidenceSummary.selectedCompare.rightSnapshot.headline }}</div>
            <div
              class="context-compare-scope-identity mono"
              data-testid="probabilistic-compare-scope-identity"
            >
              <span
                v-for="part in buildCompareScopeIdentityParts(evidenceSummary.selectedCompare.rightSnapshot)"
                :key="`right-scope-${part}`"
                class="context-compare-scope-part"
              >
                {{ part }}
              </span>
            </div>
            <p class="context-evidence-body">{{ evidenceSummary.selectedCompare.rightSnapshot.supportLabel }}</p>
            <div class="context-warning-list">
              <span class="context-warning-chip">{{ evidenceSummary.selectedCompare.rightSnapshot.semantics }}</span>
              <span
                v-for="runIdValue in evidenceSummary.selectedCompare.rightSnapshot.representativeRunIds"
                :key="`right-rep-${runIdValue}`"
                class="context-warning-chip"
              >
                Rep {{ runIdValue }}
              </span>
              <span
                v-for="highlight in evidenceSummary.selectedCompare.rightSnapshot.evidenceHighlights"
                :key="`right-highlight-${highlight}`"
                class="context-warning-chip"
              >
                {{ highlight }}
              </span>
              <span
                v-for="warning in evidenceSummary.selectedCompare.rightSnapshot.warnings"
                :key="`right-warning-${warning}`"
                class="context-warning-chip"
              >
                {{ warning }}
              </span>
            </div>
          </article>
        </div>

        <div v-if="evidenceSummary.selectedCompare" class="context-compare-summary">
          <div class="context-evidence-label">Comparison Summary</div>
          <p v-if="evidenceSummary.selectedCompare.reason" class="context-evidence-body">
            {{ evidenceSummary.selectedCompare.reason }}
          </p>
          <p
            v-for="line in evidenceSummary.selectedCompare.comparisonSummary.whatDiffers"
            :key="`compare-diff-${line}`"
            class="context-evidence-body"
          >
            {{ line }}
          </p>
          <p
            v-for="line in evidenceSummary.selectedCompare.comparisonSummary.weakSupport"
            :key="`compare-weak-${line}`"
            class="context-evidence-body"
          >
            {{ line }}
          </p>
          <p
            v-if="evidenceSummary.selectedCompare.comparisonSummary.boundaryNote"
            class="context-evidence-body"
          >
            {{ evidenceSummary.selectedCompare.comparisonSummary.boundaryNote }}
          </p>
          <div class="context-warning-list">
            <span
              v-for="warning in evidenceSummary.selectedCompare.warnings"
              :key="`compare-warning-${warning}`"
              class="context-warning-chip"
            >
              {{ warning }}
            </span>
          </div>
          <button
            type="button"
            class="context-compare-action"
            data-testid="probabilistic-compare-handoff"
            @click="handoffCompare(evidenceSummary.selectedCompare.compareId)"
          >
            Open In Step 5 Report Agent
          </button>
        </div>
        <p v-else class="context-compare-empty">
          Select one compare pair to inspect the saved left/right evidence before handing it into Step 5.
        </p>
      </section>

      <div class="context-grid">
        <article
          v-for="entry in analyticsEntries"
          :key="entry.key"
          class="context-analytics-card"
          :class="`tone-${getAnalyticsTone(entry.card.status)}`"
        >
          <div class="context-analytics-header">
            <span class="context-analytics-label">{{ entry.title }}</span>
            <span class="context-analytics-status">{{ formatAnalyticsStatus(entry.card.status) }}</span>
          </div>
          <div class="context-analytics-headline">{{ entry.card.headline }}</div>
          <p class="context-analytics-body">{{ entry.card.body }}</p>
          <div
            v-if="entry.card.warnings && entry.card.warnings.length"
            class="context-warning-list"
          >
            <span
              v-for="warning in entry.card.warnings"
              :key="`${entry.key}-${warning}`"
              class="context-warning-chip"
            >
              {{ warning }}
            </span>
          </div>
        </article>
      </div>
      </template>
    </template>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

import {
  getPrepareCapabilities,
  getSimulationEnsembleClusters,
  getSimulationEnsembleSensitivity,
  getSimulationEnsembleSummary
} from '../api/simulation'
import {
  deriveProbabilisticAnalyticsCards,
  deriveProbabilisticEvidenceSummary,
  deriveProbabilisticReportContextState
} from '../utils/probabilisticRuntime'
import { formatForecastBestEstimate } from '../utils/forecastRuntime'

const props = defineProps({
  simulationId: {
    type: String,
    default: null
  },
  runtimeMode: {
    type: String,
    default: 'legacy'
  },
  ensembleId: {
    type: String,
    default: null
  },
  clusterId: {
    type: String,
    default: null
  },
  runId: {
    type: String,
    default: null
  },
  compareId: {
    type: String,
    default: null
  },
  reportContext: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['update:compareId', 'handoff-compare'])

const capabilities = ref(null)
const capabilitiesLoading = ref(false)
const capabilitiesError = ref('')
const summaryArtifact = ref(null)
const clustersArtifact = ref(null)
const sensitivityArtifact = ref(null)
const loadingByKey = ref({
  summary: false,
  clusters: false,
  sensitivity: false
})
const errorByKey = ref({
  summary: '',
  clusters: '',
  sensitivity: ''
})

const embeddedReportContext = computed(() => (
  props.reportContext
  && typeof props.reportContext === 'object'
  && Object.keys(props.reportContext).length > 0
    ? props.reportContext
    : null
))

const normalizedRuntimeMode = computed(() => (
  props.runtimeMode === 'probabilistic'
    || Boolean(embeddedReportContext.value && Object.keys(embeddedReportContext.value).length)
    || Boolean(props.ensembleId || props.clusterId || props.runId)
    ? 'probabilistic'
    : 'legacy'
))

const effectiveSummaryArtifact = computed(() => (
  embeddedReportContext.value?.aggregate_summary || summaryArtifact.value
))

const effectiveClustersArtifact = computed(() => (
  embeddedReportContext.value?.scenario_clusters || clustersArtifact.value
))

const effectiveSensitivityArtifact = computed(() => (
  embeddedReportContext.value?.sensitivity || sensitivityArtifact.value
))
const hasViewableReportContext = computed(() => (
  Boolean(embeddedReportContext.value)
  || Boolean(effectiveSummaryArtifact.value)
  || Boolean(effectiveClustersArtifact.value)
  || Boolean(effectiveSensitivityArtifact.value)
))

const reportContextState = computed(() => deriveProbabilisticReportContextState({
  simulationId: props.simulationId,
  runtimeMode: normalizedRuntimeMode.value,
  ensembleId: props.ensembleId,
  clusterId: props.clusterId,
  runId: props.runId,
  reportContext: embeddedReportContext.value,
  capabilities: capabilities.value || {},
  capabilitiesKnown: capabilitiesLoading.value === false && capabilitiesError.value === ''
}))

const shouldRender = computed(() => (
  reportContextState.value.shouldRender
))

const contextEyebrow = computed(() => (
  hybridWorkspace.value || evidenceSummary.value.forecastObject ? 'Forecast Object' : 'Scoped Evidence'
))

const contextTitle = computed(() => (
  hybridWorkspace.value || evidenceSummary.value.forecastObject
    ? 'Forecast Object And Supporting Evidence'
    : 'Scoped Simulation Evidence'
))

const contextCopy = computed(() => {
  if (hybridWorkspace.value || evidenceSummary.value.forecastObject) {
    return 'This Step 4 surface now leads with the forecast object when it exists: question, latest answer, bounded simulation-market support, provenance, resolution, and scoring. The report body remains downstream narrative. Calibration is only earned on supported evaluated question lanes with type-correct evidence, and simulation remains supporting scenario analysis only.'
  }
  return 'The report body remains the legacy simulation-scoped artifact. These cards add empirical ensemble or scenario-family summaries, observed run facts, and observational sensitivity only. They do not turn simulation frequencies into real-world probability or imply calibrated or causal claims.'
})

const isFlaggedOff = computed(() => (
  reportContextState.value.isFlaggedOff
))

const historicalNotice = computed(() => (
  reportContextState.value.historicalNotice
))

const hybridWorkspace = computed(() => evidenceSummary.value.hybridWorkspace || null)
const localCompareId = ref(props.compareId || null)

const analyticsCards = computed(() => deriveProbabilisticAnalyticsCards({
  summaryArtifact: effectiveSummaryArtifact.value,
  clustersArtifact: effectiveClustersArtifact.value,
  sensitivityArtifact: effectiveSensitivityArtifact.value,
  loadingByKey: loadingByKey.value,
  errorByKey: errorByKey.value
}))

const evidenceSummary = computed(() => deriveProbabilisticEvidenceSummary({
  runtimeMode: normalizedRuntimeMode.value,
  ensembleId: props.ensembleId,
  clusterId: props.clusterId,
  runId: props.runId,
  compareId: localCompareId.value,
  reportContext: embeddedReportContext.value
}))

const reconcileCompareSelection = (requestedCompareId = null) => {
  const summary = deriveProbabilisticEvidenceSummary({
    runtimeMode: normalizedRuntimeMode.value,
    ensembleId: props.ensembleId,
    clusterId: props.clusterId,
    runId: props.runId,
    compareId: requestedCompareId || localCompareId.value || props.compareId || null,
    reportContext: embeddedReportContext.value
  })

  localCompareId.value = summary.selectedCompare?.compareId || null
  return localCompareId.value
}

const contextError = computed(() => {
  if (!shouldRender.value) {
    return ''
  }
  if (!evidenceSummary.value.scope?.ensembleId) {
    return 'Scoped Step 4 evidence requires at least an ensemble identifier from Step 3.'
  }
  return capabilitiesError.value
})

const scopePillLabel = computed(() => {
  const level = evidenceSummary.value.scope?.level || 'ensemble'
  if (level === 'run') {
    return 'Observed run scope'
  }
  if (level === 'cluster') {
    return 'Empirical scenario-family scope'
  }
  return 'Empirical ensemble scope'
})

const analyticsEntries = computed(() => ([
  {
    key: 'summary',
    title: 'Aggregate Summary',
    card: analyticsCards.value.summary
  },
  {
    key: 'clusters',
    title: 'Scenario Clusters',
    card: analyticsCards.value.clusters
  },
  {
    key: 'sensitivity',
    title: 'Sensitivity',
    card: analyticsCards.value.sensitivity
  }
]))

const evidenceEntries = computed(() => {
  if (!evidenceSummary.value.available) {
    return []
  }

  const entries = [
    ...(evidenceSummary.value.forecastObject ? [
      {
        key: 'forecast-object',
        title: 'Forecast Object',
        headline: evidenceSummary.value.forecastObject.questionText || `Forecast ${evidenceSummary.value.forecastObject.forecastId || '-'}`,
        body: [
          evidenceSummary.value.forecastObject.resolution?.status
            ? `Resolution status: ${evidenceSummary.value.forecastObject.resolution.status}.`
            : 'Resolution is still pending.',
          typeof evidenceSummary.value.forecastObject.scoring?.eventCount === 'number'
            ? `Scoring events: ${evidenceSummary.value.forecastObject.scoring.eventCount}.`
            : null,
          evidenceSummary.value.forecastObject.scoring?.latestMethod
            ? `Latest scoring method: ${evidenceSummary.value.forecastObject.scoring.latestMethod}.`
            : null
        ].filter(Boolean).join(' '),
        chips: [
          evidenceSummary.value.forecastObject.status ? `Status ${evidenceSummary.value.forecastObject.status}` : null,
          evidenceSummary.value.forecastObject.resolution?.status || null,
          evidenceSummary.value.forecastObject.scoring?.latestMethod || null
        ].filter(Boolean)
      }
    ] : []),
    ...(hybridWorkspace.value ? [
      {
        key: 'hybrid-question',
        title: 'Forecast Question',
        headline: hybridWorkspace.value.forecastQuestion.questionText || hybridWorkspace.value.forecastQuestion.title || 'Forecast question unavailable',
        body: [
          hybridWorkspace.value.forecastQuestion.questionType ? `Type: ${hybridWorkspace.value.forecastQuestion.questionType}.` : null,
          hybridWorkspace.value.forecastQuestion.questionHorizon ? `Horizon: ${hybridWorkspace.value.forecastQuestion.questionHorizon}.` : null,
          hybridWorkspace.value.forecastQuestion.issuedAt ? `Issued: ${hybridWorkspace.value.forecastQuestion.issuedAt}.` : null,
          hybridWorkspace.value.forecastQuestion.owner ? `Owner/source: ${hybridWorkspace.value.forecastQuestion.owner}.` : null,
          hybridWorkspace.value.forecastQuestion.abstentionConditions.length
            ? `Abstention conditions: ${hybridWorkspace.value.forecastQuestion.abstentionConditions.join('; ')}.`
            : null
        ].filter(Boolean).join(' '),
        chips: [
          ...hybridWorkspace.value.forecastQuestion.supportedQuestionTemplates,
          ...hybridWorkspace.value.forecastQuestion.decompositionSupport
        ].filter(Boolean)
      },
      {
        key: 'hybrid-answer',
        title: 'Hybrid Answer',
        headline: hybridWorkspace.value.latestAnswer.abstain
          ? `Abstained: ${hybridWorkspace.value.latestAnswer.abstainReason || 'insufficient support'}`
          : `Best estimate ${hybridWorkspace.value.latestAnswer.bestEstimateDisplay || formatForecastBestEstimate(
              hybridWorkspace.value.latestAnswer.bestEstimate,
              hybridWorkspace.value.latestAnswer.bestEstimateSemantics
            )}`,
        body: hybridWorkspace.value.latestAnswer.abstain
          ? [
              hybridWorkspace.value.latestAnswer.bestEstimateWhy ? hybridWorkspace.value.latestAnswer.bestEstimateWhy : null,
              hybridWorkspace.value.latestAnswer.evaluationSummary?.status
                ? `Evaluation status: ${hybridWorkspace.value.latestAnswer.evaluationSummary.status}.`
                : null
            ].filter(Boolean).join(' ')
          : [
              hybridWorkspace.value.latestAnswer.bestEstimateWhy ? `Why: ${hybridWorkspace.value.latestAnswer.bestEstimateWhy}.` : null,
              hybridWorkspace.value.latestAnswer.counterevidence.length
                ? `Counterevidence: ${hybridWorkspace.value.latestAnswer.counterevidence.join('; ')}.`
                : null,
              hybridWorkspace.value.latestAnswer.assumptionLedger.items.length
                ? `Assumption ledger: ${hybridWorkspace.value.latestAnswer.assumptionLedger.items.join('; ')}.`
                : null,
              hybridWorkspace.value.latestAnswer.uncertaintyDecomposition.components.length
                ? `Uncertainty: ${hybridWorkspace.value.latestAnswer.uncertaintyDecomposition.components.map((item) => item.summary || item.code).filter(Boolean).join('; ')}.`
                : null,
              hybridWorkspace.value.simulationScenarioAnalysis.available
                ? `Simulation remains supporting scenario analysis with observed run share ${formatHybridPercent(hybridWorkspace.value.simulationScenarioAnalysis.observedRunShare)}.`
                : null
            ].filter(Boolean).join(' '),
        chips: [
          hybridWorkspace.value.statusSurface.evidenceAvailable ? 'Evidence available' : 'Evidence unavailable',
          hybridWorkspace.value.statusSurface.evaluationAvailable ? 'Evaluation available' : 'Evaluation unavailable',
          hybridWorkspace.value.statusSurface.calibratedConfidenceEarned ? 'Calibrated confidence earned' : 'Confidence not earned',
          hybridWorkspace.value.statusSurface.simulationOnlyScenarioExploration ? 'Simulation-only scenario exploration' : 'Hybrid answer assembled',
          ...(hybridWorkspace.value.supportedQuestionTemplates || [])
        ].filter(Boolean)
      },
      {
        key: 'hybrid-evidence',
        title: 'Evidence Bundle',
        headline: hybridWorkspace.value.evidenceBundle.title || hybridWorkspace.value.evidenceBundle.status || 'Evidence bundle',
        body: [
          hybridWorkspace.value.evidenceBundle.summary || null,
          hybridWorkspace.value.evidenceBundle.boundaryNote ? `Boundary: ${hybridWorkspace.value.evidenceBundle.boundaryNote}.` : null
        ].filter(Boolean).join(' ') || 'Evidence bundle details are available for this hybrid workspace.',
        chips: [
          `Status ${hybridWorkspace.value.evidenceBundle.status}`,
          `Sources ${hybridWorkspace.value.evidenceBundle.sourceEntryCount}`,
          `Freshness ${hybridWorkspace.value.evidenceBundle.freshness}`,
          `Relevance ${hybridWorkspace.value.evidenceBundle.relevance}`,
          hybridWorkspace.value.evidenceBundle.qualityScore !== null ? `Quality ${Math.round(hybridWorkspace.value.evidenceBundle.qualityScore * 100)}%` : null,
          hybridWorkspace.value.evidenceBundle.conflictCount > 0 ? `Conflicts ${hybridWorkspace.value.evidenceBundle.conflictCount}` : null,
          hybridWorkspace.value.evidenceBundle.missingEvidenceCount > 0 ? `Missing ${hybridWorkspace.value.evidenceBundle.missingEvidenceCount}` : null,
          ...hybridWorkspace.value.evidenceBundle.uncertaintyCauses.map((cause) => String(cause || '').replace(/_/g, ' '))
        ].filter(Boolean)
      },
      {
        key: 'hybrid-ledger',
        title: 'Prediction Ledger',
        headline: `${hybridWorkspace.value.predictionLedger.entryCount} ledger entries`,
        body: [
          `Final resolution state: ${hybridWorkspace.value.predictionLedger.finalResolutionState}.`,
          hybridWorkspace.value.predictionLedger.resolutionNote ? hybridWorkspace.value.predictionLedger.resolutionNote : null,
          hybridWorkspace.value.predictionLedger.workerOutputCount ? `${hybridWorkspace.value.predictionLedger.workerOutputCount} worker outputs retained.` : null
        ].filter(Boolean).join(' '),
        chips: [
          hybridWorkspace.value.predictionLedger.evaluationCaseCount ? `${hybridWorkspace.value.predictionLedger.evaluationCaseCount} evaluation cases` : null,
          hybridWorkspace.value.predictionLedger.resolvedEvaluationCaseCount ? `${hybridWorkspace.value.predictionLedger.resolvedEvaluationCaseCount} resolved` : null
        ].filter(Boolean)
      },
      {
        key: 'hybrid-evaluation',
        title: 'Evaluation',
        headline: hybridWorkspace.value.evaluation.available
          ? 'Evaluation available'
          : 'Evaluation not yet available',
        body: [
          hybridWorkspace.value.evaluation.caseCount ? `${hybridWorkspace.value.evaluation.caseCount} evaluation cases tracked.` : null,
          hybridWorkspace.value.evaluation.resolvedCaseCount ? `${hybridWorkspace.value.evaluation.resolvedCaseCount} resolved.` : null,
          hybridWorkspace.value.evaluation.calibratedConfidenceEarned
            ? 'Calibrated confidence has been earned for this workspace.'
            : 'Calibrated confidence has not been earned for this workspace on the current typed answer.',
          hybridWorkspace.value.evaluation.confidenceBasis?.note ? hybridWorkspace.value.evaluation.confidenceBasis.note : null
        ].filter(Boolean).join(' '),
        chips: [
          `Evidence ${hybridWorkspace.value.statusSurface.evidenceAvailable ? 'available' : 'missing'}`,
          `Evaluation ${hybridWorkspace.value.statusSurface.evaluationAvailable ? 'available' : 'missing'}`,
          `Calibration ${hybridWorkspace.value.statusSurface.calibratedConfidenceEarned ? 'earned' : 'not earned'}`
        ]
      },
      {
        key: 'hybrid-workers',
        title: 'Worker Comparison',
        headline: `${hybridWorkspace.value.workerComparison.workerCount} workers`,
        body: [
          hybridWorkspace.value.workerComparison.workerKinds.length
            ? `Worker kinds: ${hybridWorkspace.value.workerComparison.workerKinds.join(', ')}.`
            : null,
          hybridWorkspace.value.workerComparison.simulationIsOnlyWorker
            ? 'Simulation is the only worker and remains scenario analysis only.'
            : 'Simulation remains one worker inside the hybrid comparison.',
          hybridWorkspace.value.workerComparison.contributionTrace.length
            ? `Contribution trace: ${hybridWorkspace.value.workerComparison.contributionTrace.slice(0, 3).map((item) => item.summary || item.workerId || item.workerKind).filter(Boolean).join('; ')}.`
            : null
        ].filter(Boolean).join(' '),
        chips: [
          hybridWorkspace.value.workerComparison.simulationWorkerCount ? `Simulation workers ${hybridWorkspace.value.workerComparison.simulationWorkerCount}` : null,
          hybridWorkspace.value.workerComparison.simulationObservedRunShare !== null ? `Observed run share ${formatHybridPercent(hybridWorkspace.value.workerComparison.simulationObservedRunShare)}` : null,
          ...hybridWorkspace.value.workerComparison.contributionTrace
            .slice(0, 3)
            .map((item) => item.summary || item.workerId || item.workerKind)
        ].filter(Boolean)
      },
      {
        key: 'hybrid-simulation',
        title: 'Simulation Scenario Analysis',
        headline: 'Simulation remains supporting scenario analysis',
        body: hybridWorkspace.value.simulationScenarioAnalysis.available
          ? [
              hybridWorkspace.value.simulationScenarioAnalysis.onlyScenarioExploration
                ? 'The current workspace is simulation-only scenario exploration.'
                : 'The current workspace combines simulation with non-simulation workers.',
              hybridWorkspace.value.simulationScenarioAnalysis.observedRunShare !== null
                ? `Observed run share: ${formatHybridPercent(hybridWorkspace.value.simulationScenarioAnalysis.observedRunShare)}.`
                : null
            ].filter(Boolean).join(' ')
          : 'Simulation data are not attached to this hybrid workspace.',
        chips: [
          hybridWorkspace.value.simulationScenarioAnalysis.onlyScenarioExploration ? 'Simulation-only' : 'Supporting scenario analysis',
          hybridWorkspace.value.simulationScenarioAnalysis.available ? 'Scenario evidence attached' : 'Scenario evidence missing'
        ]
      }
    ] : []),
    {
      key: 'scope',
      title: 'Scope & Provenance',
      headline: evidenceSummary.value.scope.level === 'run'
        ? `Run ${evidenceSummary.value.scope.runId || '-'} in ensemble ${evidenceSummary.value.scope.ensembleId || '-'}`
        : (
          evidenceSummary.value.scope.level === 'cluster'
            ? `Scenario family ${evidenceSummary.value.scope.clusterId || '-'} in ensemble ${evidenceSummary.value.scope.ensembleId || '-'}`
            : `Ensemble ${evidenceSummary.value.scope.ensembleId || '-'}`
        ),
      body: `${evidenceSummary.value.scope.supportLabel}. ${evidenceSummary.value.scope.representativeRunCount || 0} representative run${evidenceSummary.value.scope.representativeRunCount === 1 ? '' : 's'} surfaced for inspection.`,
      chips: evidenceSummary.value.scope.warnings
    }
  ]

  if (evidenceSummary.value.grounding) {
    entries.push({
      key: 'grounding',
      title: 'Upstream Grounding',
      headline: evidenceSummary.value.grounding.status === 'ready'
        ? `${evidenceSummary.value.grounding.evidenceCount} cited upstream artifact${evidenceSummary.value.grounding.evidenceCount === 1 ? '' : 's'}`
        : `Grounding attachment ${evidenceSummary.value.grounding.status}`,
      body: evidenceSummary.value.grounding.boundaryNote || 'No upstream grounding bundle was attached to this report context.',
      chips: [
        `Source ${evidenceSummary.value.grounding.citationCounts.source}`,
        `Graph ${evidenceSummary.value.grounding.citationCounts.graph}`,
        ...evidenceSummary.value.grounding.evidenceItems
          .map((item) => item.citationId)
          .filter(Boolean)
          .slice(0, 3),
        ...evidenceSummary.value.grounding.warnings
      ].filter(Boolean)
    })
  }

  if (evidenceSummary.value.selectedCluster) {
    const supportAssessment = evidenceSummary.value.selectedCluster.supportAssessment || {}
    entries.push({
      key: 'selected-cluster',
      title: 'Selected Scenario Family',
      headline: evidenceSummary.value.selectedCluster.familyLabel || `Scenario family ${evidenceSummary.value.selectedCluster.clusterId || '-'}`,
      body: supportAssessment.downgraded && supportAssessment.reason
        ? `${evidenceSummary.value.selectedCluster.familySummary || 'Scenario-family evidence is available for the selected cluster scope.'} ${supportAssessment.reason}`
        : (evidenceSummary.value.selectedCluster.familySummary || 'Scenario-family evidence is available for the selected cluster scope.'),
      chips: [
        evidenceSummary.value.selectedCluster.clusterId,
        supportAssessment.label
      ].filter(Boolean)
    })
  }

  if (evidenceSummary.value.selectedRun) {
    const selectedRun = evidenceSummary.value.selectedRun
    const selectedRunMarketSummary = selectedRun.marketSummary || null
    entries.push({
      key: 'selected-run',
      title: 'Selected Run Evidence',
      headline: `Run ${selectedRun.runId || '-'}`,
      body: [
        `${selectedRun.supportLabel}.`,
        selectedRun.assumptionSummary,
        selectedRunMarketSummary?.syntheticConsensusProbability != null
          ? `Synthetic consensus ${formatHybridPercent(selectedRunMarketSummary.syntheticConsensusProbability)}.`
          : null,
        selectedRunMarketSummary?.disagreementIndex != null
          ? `Disagreement ${formatHybridPercent(selectedRunMarketSummary.disagreementIndex)}.`
          : null
      ].filter(Boolean).join(' '),
      chips: [
        selectedRun.qualityStatus,
        selectedRun.marketProvenance?.status
          ? `Provenance ${selectedRun.marketProvenance.status}`
          : null
      ].filter(Boolean)
    })
  }

  if (evidenceSummary.value.hybridWorkspace?.available) {
    const hybridWorkspace = evidenceSummary.value.hybridWorkspace
    const latestAnswer = hybridWorkspace.latestAnswer || {}
    const truthfulnessSurface = hybridWorkspace.statusSurface || {}
    const supportedTemplates = Array.isArray(hybridWorkspace.supportedQuestionTemplateDetails)
      ? hybridWorkspace.supportedQuestionTemplateDetails
      : []

    entries.push({
      key: 'hybrid-workspace',
      title: 'Hybrid Forecast',
      headline: hybridWorkspace.forecastQuestion?.questionText
        || hybridWorkspace.forecastQuestion?.title
        || `Forecast ${hybridWorkspace.forecastQuestion?.forecastId || '-'}`,
      body: latestAnswer.abstain
        ? `Abstaining because ${latestAnswer.abstainReason || 'support is insufficient'}. ${latestAnswer.bestEstimateWhy ? `Why: ${latestAnswer.bestEstimateWhy}` : ''} Simulation remains supporting scenario analysis only.`
        : `${latestAnswer.bestEstimateDisplay ? `Best estimate ${latestAnswer.bestEstimateDisplay}.` : latestAnswer.bestEstimate !== null && latestAnswer.bestEstimate !== undefined ? `Best estimate ${formatForecastBestEstimate(latestAnswer.bestEstimate, latestAnswer.bestEstimateSemantics)}.` : 'No best estimate yet.'} ${latestAnswer.bestEstimateWhy || 'The latest answer explains the estimate in the forecast answer payload.'}`.trim(),
      chips: [
        truthfulnessSurface.evidenceAvailable ? 'Evidence available' : 'Evidence missing',
        truthfulnessSurface.evaluationAvailable ? 'Evaluation available' : 'Evaluation missing',
        truthfulnessSurface.calibratedConfidenceEarned ? 'Calibrated confidence earned' : 'Confidence not yet calibrated',
        truthfulnessSurface.simulationOnlyScenarioExploration ? 'Simulation-only scenario exploration' : 'Simulation supporting scenario analysis',
        ...supportedTemplates.slice(0, 3).map((template) => template.label || template.questionText || template.templateId),
        ...((latestAnswer.counterevidence || []).slice(0, 2)),
        ...((latestAnswer.assumptionLedger?.items || []).slice(0, 2))
      ].filter(Boolean)
    })

    if (hybridWorkspace.workerComparison) {
      const workerComparison = hybridWorkspace.workerComparison
      entries.push({
        key: 'worker-comparison',
        title: 'Worker Comparison',
        headline: `${workerComparison.workerCount || 0} workers summarized`,
        body: workerComparison.abstain
          ? `The hybrid answer abstained because ${workerComparison.abstainReason || 'support is insufficient'}. Simulation remains scenario evidence only.`
          : (
              workerComparison.simulationContext
                ? 'Simulation remains supporting scenario analysis, while the non-simulation workers determine the best estimate unless they abstain or disagree too widely.'
                : 'Non-simulation workers determine the best estimate; simulation remains supporting scenario analysis only.'
            ),
        chips: [
          ...(workerComparison.workerKinds || []).slice(0, 4),
          ...(workerComparison.workerContributionTrace || [])
            .map((item) => item.summary || item.worker_id || item.workerId)
            .filter(Boolean)
            .slice(0, 3),
          workerComparison.simulationContext?.observed_run_share !== undefined && workerComparison.simulationContext?.observed_run_share !== null
            ? `Simulation observed run share ${workerComparison.simulationContext.observed_run_share}`
            : null
        ].filter(Boolean)
      })
    }
  }

  if (evidenceSummary.value.confidenceStatus) {
    const confidenceStatus = evidenceSummary.value.confidenceStatus
    entries.push({
      key: 'confidence',
      title: 'Confidence Status',
      headline: confidenceStatus.headline,
      body: confidenceStatus.body,
      chips: [
        `Status ${confidenceStatus.status}`,
        ...confidenceStatus.gatingReasons,
        ...confidenceStatus.warnings
      ].filter(Boolean)
    })
  }

  if (evidenceSummary.value.calibration) {
    entries.push({
      key: 'calibration',
      title: 'Calibration Provenance',
      headline: `Backtest-linked calibration for ${evidenceSummary.value.calibration.readyMetricIds.join(', ') || 'supported metrics'}`,
      body: evidenceSummary.value.calibration.summary || 'Backtested calibration metadata is available for this report context.',
      chips: [
        evidenceSummary.value.calibration.confidenceLabel,
        ...evidenceSummary.value.calibration.warnings
      ].filter(Boolean)
    })
  }

  if (evidenceSummary.value.comparePrompts.length) {
    entries.push({
      key: 'compare',
      title: 'Compare Next',
      headline: 'Bounded compare workflow available',
      body: 'Carry these prompts into Step 5 Report Agent chat to compare runs or scenario families without dropping provenance.',
      chips: []
    })
  }

  return entries
})

const formatHybridPercent = (value) => {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return '-'
  }
  return `${Math.round(value * 100)}%`
}

const cardTone = computed(() => {
  if (contextError.value) {
    return 'error'
  }
  if (isFlaggedOff.value) {
    return 'warning'
  }
  return 'neutral'
})

const resetArtifacts = () => {
  summaryArtifact.value = null
  clustersArtifact.value = null
  sensitivityArtifact.value = null
  loadingByKey.value = {
    summary: false,
    clusters: false,
    sensitivity: false
  }
  errorByKey.value = {
    summary: '',
    clusters: '',
    sensitivity: ''
  }
}

const loadCapabilities = async () => {
  capabilitiesLoading.value = true
  capabilitiesError.value = ''

  try {
    const res = await getPrepareCapabilities()
    if (!res?.success || !res.data) {
      throw new Error(res?.error || 'Unable to load probabilistic capability state.')
    }
    capabilities.value = res.data
  } catch (err) {
    capabilities.value = null
    capabilitiesError.value = err.message || 'Unable to load probabilistic capability state.'
  } finally {
    capabilitiesLoading.value = false
  }
}

const loadArtifact = async (key, loader, targetRef) => {
  loadingByKey.value = {
    ...loadingByKey.value,
    [key]: true
  }
  errorByKey.value = {
    ...errorByKey.value,
    [key]: ''
  }

  try {
    const res = await loader()
    if (!res?.success || !res.data) {
      throw new Error(res?.error || `Unable to load ${key} artifact.`)
    }
    targetRef.value = res.data
  } catch (err) {
    targetRef.value = null
    errorByKey.value = {
      ...errorByKey.value,
      [key]: err.message || `Unable to load ${key} artifact.`
    }
  } finally {
    loadingByKey.value = {
      ...loadingByKey.value,
      [key]: false
    }
  }
}

const loadReportContext = async () => {
  resetArtifacts()

  if (!shouldRender.value) {
    capabilities.value = null
    capabilitiesError.value = ''
    capabilitiesLoading.value = false
    return
  }

  await loadCapabilities()
  if (contextError.value || isFlaggedOff.value) {
    return
  }

  const { fetchPlan } = reportContextState.value
  const loaders = []

  if (fetchPlan.summary) {
    loaders.push(
      loadArtifact(
        'summary',
        () => getSimulationEnsembleSummary(props.simulationId, props.ensembleId),
        summaryArtifact
      )
    )
  }
  if (fetchPlan.clusters) {
    loaders.push(
      loadArtifact(
        'clusters',
        () => getSimulationEnsembleClusters(props.simulationId, props.ensembleId),
        clustersArtifact
      )
    )
  }
  if (fetchPlan.sensitivity) {
    loaders.push(
      loadArtifact(
        'sensitivity',
        () => getSimulationEnsembleSensitivity(props.simulationId, props.ensembleId),
        sensitivityArtifact
      )
    )
  }

  if (!loaders.length) {
    return
  }

  await Promise.all(loaders)
}

watch(
  () => [props.simulationId, props.runtimeMode, props.ensembleId, props.clusterId, props.runId, props.reportContext],
  () => {
    loadReportContext()
  },
  { immediate: true }
)

watch(
  () => [props.compareId, props.runtimeMode, props.ensembleId, props.clusterId, props.runId, embeddedReportContext.value],
  ([nextCompareId]) => {
    reconcileCompareSelection(nextCompareId)
  },
  { immediate: true }
)

const formatAnalyticsStatus = (status) => {
  const labels = {
    loading: 'Loading',
    error: 'Error',
    empty: 'Empty',
    partial: 'Partial',
    complete: 'Loaded'
  }
  return labels[status] || 'Observed'
}

const getAnalyticsTone = (status) => {
  if (status === 'error') {
    return 'error'
  }
  if (status === 'partial') {
    return 'warning'
  }
  if (status === 'complete') {
    return 'success'
  }
  return 'neutral'
}

const buildCompareScopeIdentityParts = (snapshot) => {
  const scope = snapshot?.scope && typeof snapshot.scope === 'object'
    ? snapshot.scope
    : {}
  const parts = [`Level ${scope.level || 'unknown'}`, `E ${scope.ensembleId || '-'}`]
  if (scope.clusterId) {
    parts.push(`C ${scope.clusterId}`)
  }
  if (scope.runId) {
    parts.push(`R ${scope.runId}`)
  }
  return parts
}

const selectCompareOption = (compareId) => {
  const requestedCompareId = compareId === localCompareId.value ? null : compareId
  emit('update:compareId', reconcileCompareSelection(requestedCompareId))
}

const handoffCompare = (compareId) => {
  const resolvedCompareId = reconcileCompareSelection(compareId || localCompareId.value)
  emit('update:compareId', resolvedCompareId)
  emit('handoff-compare', resolvedCompareId)
}
</script>

<style scoped>
.report-context-card {
  border: 1px solid #e8e1d6;
  background:
    radial-gradient(circle at top right, rgba(198, 134, 66, 0.12), transparent 36%),
    linear-gradient(180deg, #fffdf8 0%, #fffaf2 100%);
  border-radius: 20px;
  padding: 20px;
  margin-bottom: 20px;
}

.report-context-card.tone-error {
  border-color: #c44f34;
}

.report-context-card.tone-warning {
  border-color: #c69242;
}

.report-context-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.context-eyebrow {
  display: inline-block;
  font-size: 11px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: #9c6b2f;
  margin-bottom: 6px;
}

.context-title {
  margin: 0;
  font-size: 22px;
  line-height: 1.1;
  color: #1f1a16;
}

.context-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 12px;
  color: #5e5548;
}

.context-copy {
  margin: 12px 0 0;
  color: #544b40;
  line-height: 1.6;
}

.context-banner {
  margin-top: 16px;
  border-radius: 14px;
  padding: 12px 14px;
  font-size: 14px;
  line-height: 1.5;
}

.context-banner.neutral {
  background: rgba(36, 32, 28, 0.05);
  color: #3d352d;
}

.context-banner.warning {
  background: rgba(198, 146, 66, 0.12);
  color: #68471e;
}

.context-banner.error {
  background: rgba(196, 79, 52, 0.12);
  color: #7a2416;
}

.context-pill-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 16px;
}

.context-pill {
  background: rgba(36, 32, 28, 0.06);
  border-radius: 999px;
  padding: 7px 12px;
  font-size: 12px;
  color: #4a4137;
}

.context-pill.capability {
  background: rgba(58, 101, 75, 0.12);
  color: #224032;
}

.context-pill.epistemic {
  background: rgba(79, 67, 132, 0.12);
  color: #352a72;
}

.context-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-top: 16px;
}

.context-evidence-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: 16px;
}

.context-evidence-card {
  border-radius: 16px;
  padding: 16px;
  background: rgba(255, 255, 255, 0.84);
  border: 1px solid rgba(156, 107, 47, 0.14);
}

.context-evidence-label {
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #81613d;
}

.context-evidence-headline {
  margin-top: 10px;
  font-size: 18px;
  font-weight: 600;
  color: #1f1a16;
}

.context-evidence-body {
  margin: 8px 0 0;
  font-size: 14px;
  line-height: 1.55;
  color: #4a4137;
}

.context-compare-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.context-compare-chip {
  background: rgba(198, 146, 66, 0.14);
  border: 1px solid rgba(156, 107, 47, 0.2);
  border-radius: 999px;
  padding: 7px 12px;
  font-size: 12px;
  color: #6c4a23;
}

.context-analytics-card {
  border-radius: 16px;
  padding: 16px;
  background: #ffffff;
  border: 1px solid rgba(84, 75, 64, 0.1);
}

.context-analytics-card.tone-warning {
  border-color: rgba(198, 146, 66, 0.45);
}

.context-analytics-card.tone-error {
  border-color: rgba(196, 79, 52, 0.45);
}

.context-analytics-card.tone-success {
  border-color: rgba(68, 130, 90, 0.4);
}

.context-compare-workspace {
  margin-top: 16px;
  border-radius: 18px;
  padding: 18px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(156, 107, 47, 0.18);
}

.context-compare-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.context-compare-title {
  margin-top: 8px;
  font-size: 20px;
  font-weight: 600;
  color: #1f1a16;
}

.context-compare-boundary {
  max-width: 340px;
  font-size: 13px;
  line-height: 1.5;
  color: #5e5548;
}

.context-compare-picker {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 16px;
}

.context-compare-picker-btn {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 220px;
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid rgba(156, 107, 47, 0.16);
  background: rgba(255, 250, 242, 0.92);
  text-align: left;
  color: #32281d;
  cursor: pointer;
}

.context-compare-picker-btn.active {
  border-color: rgba(156, 107, 47, 0.5);
  background: linear-gradient(180deg, rgba(255, 245, 228, 0.98) 0%, rgba(255, 250, 242, 0.94) 100%);
  box-shadow: 0 10px 24px rgba(156, 107, 47, 0.12);
}

.context-compare-picker-label {
  font-size: 14px;
  font-weight: 600;
}

.context-compare-picker-reason {
  font-size: 12px;
  color: #6b5d4e;
}

.context-compare-detail {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: 16px;
}

.context-compare-scope-card,
.context-compare-summary {
  border-radius: 16px;
  padding: 16px;
  background: rgba(248, 242, 231, 0.58);
  border: 1px solid rgba(156, 107, 47, 0.12);
}

.context-compare-scope-headline {
  margin-top: 8px;
  font-size: 18px;
  font-weight: 600;
  color: #1f1a16;
}

.context-compare-scope-identity {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.context-compare-scope-part {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 5px 9px;
  background: rgba(36, 32, 28, 0.06);
  color: #5e5548;
  font-size: 12px;
}

.context-compare-summary {
  margin-top: 12px;
}

.context-compare-action {
  margin-top: 14px;
  border: 0;
  border-radius: 999px;
  padding: 10px 16px;
  background: #7d5530;
  color: #fffaf2;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.context-compare-empty {
  margin-top: 14px;
  font-size: 14px;
  color: #5e5548;
}

.context-analytics-header {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  align-items: baseline;
}

.context-analytics-label,
.context-analytics-status {
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #665a4d;
}

.context-analytics-headline {
  margin-top: 10px;
  font-size: 18px;
  font-weight: 600;
  color: #1f1a16;
}

.context-analytics-body {
  margin: 8px 0 0;
  font-size: 14px;
  line-height: 1.55;
  color: #4a4137;
}

.context-warning-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.context-warning-chip {
  background: rgba(36, 32, 28, 0.06);
  border-radius: 999px;
  padding: 6px 10px;
  font-size: 12px;
  color: #5e5548;
}

.mono {
  font-family: 'JetBrains Mono', monospace;
}

@media (max-width: 1100px) {
  .context-compare-detail,
  .context-evidence-grid,
  .context-grid {
    grid-template-columns: 1fr;
  }

  .context-compare-header {
    flex-direction: column;
  }
}
</style>
