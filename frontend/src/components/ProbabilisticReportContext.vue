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
        <h3 class="context-title">Observed Ensemble Context</h3>
      </div>
      <div class="context-meta mono">
        <span>E {{ ensembleId || '-' }}</span>
        <span>R {{ runId || '-' }}</span>
      </div>
    </div>

    <p class="context-copy">
      The report body remains the legacy simulation-scoped artifact. These cards add observed empirical or observational
      ensemble context only and do not imply calibrated probabilities or Step 5 ensemble-aware chat support.
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
        <span class="context-pill">Observed run family only</span>
        <span class="context-pill">No calibrated claims</span>
      </div>

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
  runId: {
    type: String,
    default: null
  },
  reportContext: {
    type: Object,
    default: null
  }
})

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

const contextError = computed(() => {
  if (!shouldRender.value) {
    return ''
  }
  if (!props.ensembleId || !props.runId) {
    return 'Probabilistic Step 4 requires explicit ensemble and run identifiers from Step 3.'
  }
  return capabilitiesError.value
})

const analyticsCards = computed(() => deriveProbabilisticAnalyticsCards({
  summaryArtifact: effectiveSummaryArtifact.value,
  clustersArtifact: effectiveClustersArtifact.value,
  sensitivityArtifact: effectiveSensitivityArtifact.value,
  loadingByKey: loadingByKey.value,
  errorByKey: errorByKey.value
}))

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
  () => [props.simulationId, props.runtimeMode, props.ensembleId, props.runId, props.reportContext],
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
  .context-grid {
    grid-template-columns: 1fr;
  }
}
</style>
