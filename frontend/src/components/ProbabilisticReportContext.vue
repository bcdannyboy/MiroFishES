<template>
  <section
    v-if="shouldRender"
    class="report-context-card"
    :class="`tone-${cardTone}`"
    data-testid="probabilistic-report-context"
  >
    <div class="report-context-header">
      <div>
        <span class="context-eyebrow">Probabilistic</span>
        <h3 class="context-title">Observed Forecast Context</h3>
      </div>
      <div class="context-meta mono">
        <span>E {{ ensembleId || '-' }}</span>
        <span>C {{ clusterId || '-' }}</span>
        <span>R {{ runId || '-' }}</span>
      </div>
    </div>

    <p class="context-copy">
      The report body remains the legacy simulation-scoped artifact. These cards add observed empirical or observational
      ensemble, scenario-family, or run context only and do not imply calibrated probabilities or causal claims.
    </p>

    <div v-if="contextError" class="context-banner error">
      {{ contextError }}
    </div>
    <div v-else-if="capabilitiesLoading" class="context-banner neutral">
      Loading probabilistic report capabilities...
    </div>
    <div v-else-if="isFlaggedOff" class="context-banner warning">
      Probabilistic report surfaces are disabled by the backend flag. The legacy report remains available without
      ensemble analytics cards.
    </div>
    <template v-else>
      <div v-if="historicalNotice" class="context-banner warning">
        {{ historicalNotice }}
      </div>
      <div class="context-pill-row">
        <span class="context-pill">Empirical report addendum</span>
        <span class="context-pill">{{ scopePillLabel }}</span>
        <span class="context-pill">No calibrated claims</span>
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

const normalizedRuntimeMode = computed(() => (
  props.runtimeMode === 'probabilistic' ? 'probabilistic' : 'legacy'
))

const embeddedReportContext = computed(() => (
  props.reportContext && typeof props.reportContext === 'object'
    ? props.reportContext
    : null
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

const isFlaggedOff = computed(() => (
  reportContextState.value.isFlaggedOff
))

const historicalNotice = computed(() => (
  reportContextState.value.historicalNotice
))

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
  compareId: props.compareId,
  reportContext: embeddedReportContext.value
}))

const contextError = computed(() => {
  if (!shouldRender.value) {
    return ''
  }
  if (!evidenceSummary.value.scope?.ensembleId) {
    return 'Probabilistic Step 4 requires at least an ensemble identifier from Step 3.'
  }
  return capabilitiesError.value
})

const scopePillLabel = computed(() => {
  const level = evidenceSummary.value.scope?.level || 'ensemble'
  if (level === 'run') {
    return 'Observed run scope'
  }
  if (level === 'cluster') {
    return 'Observed scenario-family scope'
  }
  return 'Observed ensemble scope'
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
        : `Grounding ${evidenceSummary.value.grounding.status}`,
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
    entries.push({
      key: 'selected-cluster',
      title: 'Selected Scenario Family',
      headline: evidenceSummary.value.selectedCluster.familyLabel || `Scenario family ${evidenceSummary.value.selectedCluster.clusterId || '-'}`,
      body: evidenceSummary.value.selectedCluster.familySummary || 'Scenario-family evidence is available for the selected cluster scope.',
      chips: [
        evidenceSummary.value.selectedCluster.clusterId
      ].filter(Boolean)
    })
  }

  if (evidenceSummary.value.selectedRun) {
    entries.push({
      key: 'selected-run',
      title: 'Selected Run Evidence',
      headline: `Run ${evidenceSummary.value.selectedRun.runId || '-'}`,
      body: `${evidenceSummary.value.selectedRun.supportLabel}. ${evidenceSummary.value.selectedRun.assumptionSummary}.`,
      chips: [
        evidenceSummary.value.selectedRun.qualityStatus
      ].filter(Boolean)
    })
  }

  if (evidenceSummary.value.confidenceStatus) {
    const confidenceStatus = evidenceSummary.value.confidenceStatus
    entries.push({
      key: 'confidence',
      title: 'Confidence Status',
      headline: confidenceStatus.status === 'ready'
        ? `Calibration ready for ${confidenceStatus.readyMetricIds.join(', ') || 'named metrics'}`
        : (confidenceStatus.status === 'not_ready'
          ? `Calibration artifacts present but not ready`
          : 'No calibration artifacts attached'),
      body: confidenceStatus.boundaryNote,
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
      headline: `Backtested calibration for ${evidenceSummary.value.calibration.readyMetricIds.join(', ') || 'supported metrics'}`,
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
      headline: 'Bounded compare workflow ready',
      body: 'Carry these prompts into Step 5 Report Agent chat to compare runs or scenario families without dropping provenance.',
      chips: []
    })
  }

  return entries
})

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

const formatAnalyticsStatus = (status) => {
  const labels = {
    loading: 'Loading',
    error: 'Error',
    empty: 'Empty',
    partial: 'Partial',
    complete: 'Complete'
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
  emit('update:compareId', compareId === props.compareId ? null : compareId)
}

const handoffCompare = (compareId) => {
  emit('update:compareId', compareId || null)
  emit('handoff-compare', compareId || null)
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
