import test from 'node:test'
import assert from 'node:assert/strict'
import * as runtimeUtils from '../../src/utils/probabilisticRuntime.js'

import {
  buildSimulationRunRouteQuery,
  buildReportGenerationRequest,
  buildReportAgentChatRequest,
  buildProbabilisticEnsembleRequest,
  buildProbabilisticRunStartRequest,
  deriveGraphPanelState,
  deriveStep3GraphRequest,
  mergeGraphDataPayloads,
  isStep2PrepareInFlight,
  shouldPromoteStep2ReadyState,
  sortSimulationHistory,
  getHistoryCardZIndex,
  buildHistoryCardTestId,
  buildHistoryActionTestId,
  deriveHistoryStep3ReplayState,
  deriveProbabilisticReportRouteState,
  normalizeSimulationRunRouteQuery,
  resolveStep3GraphScope,
  shouldLaunchProbabilisticRuntime,
  getProbabilisticRuntimeShellErrorMessage,
  getStep3ReportState,
  getStep5InteractionState,
  getStep2HandoffState,
  deriveProbabilisticStep3Runtime,
  deriveProbabilisticOperatorActions,
  deriveProbabilisticProgressSummary,
  deriveProbabilisticActionRoundsMeta,
  deriveProbabilisticPlatformSkewCopy,
  deriveProbabilisticCapabilityState,
  deriveProbabilisticAnalyticsCards,
  deriveProbabilisticReportContextState,
  resolveProbabilisticRunSelection
} from '../../src/utils/probabilisticRuntime.js'

test('buildSimulationRunRouteQuery omits empty fields and stringifies supported values', () => {
  assert.deepEqual(
    buildSimulationRunRouteQuery({
      maxRounds: 24,
      runtimeMode: 'probabilistic',
      ensembleId: '0001',
      runId: '0002'
    }),
    {
      maxRounds: '24',
      mode: 'probabilistic',
      ensembleId: '0001',
      runId: '0002'
    }
  )

  assert.deepEqual(
    buildSimulationRunRouteQuery({
      maxRounds: 0,
      runtimeMode: 'legacy',
      ensembleId: '',
      runId: null
    }),
    {}
  )
})

test('normalizeSimulationRunRouteQuery normalizes maxRounds and runtime mode', () => {
  assert.deepEqual(
    normalizeSimulationRunRouteQuery({
      maxRounds: '18',
      mode: 'probabilistic',
      ensembleId: '0007',
      runId: '0003'
    }),
    {
      maxRounds: 18,
      runtimeMode: 'probabilistic',
      ensembleId: '0007',
      runId: '0003',
      probabilisticRuntimeActive: true
    }
  )

  assert.deepEqual(
    normalizeSimulationRunRouteQuery({
      maxRounds: '-4',
      mode: 'unsupported',
      ensembleId: '0007'
    }),
    {
      maxRounds: null,
      runtimeMode: 'legacy',
      ensembleId: '0007',
      runId: null,
      probabilisticRuntimeActive: false
    }
  )
})

test('buildReportGenerationRequest carries probabilistic scope only when the runtime is probabilistic', () => {
  assert.deepEqual(
    buildReportGenerationRequest({
      simulationId: 'sim-1',
      runtimeMode: 'legacy',
      ensembleId: '0001',
      runId: '0002'
    }),
    {
      simulation_id: 'sim-1',
      force_regenerate: true
    }
  )

  assert.deepEqual(
    buildReportGenerationRequest({
      simulationId: 'sim-1',
      runtimeMode: 'probabilistic',
      ensembleId: '0001',
      runId: '0002',
      forceRegenerate: false
    }),
    {
      simulation_id: 'sim-1',
      force_regenerate: false,
      ensemble_id: '0001',
      run_id: '0002'
    }
  )
})

test('deriveProbabilisticReportRouteState rebuilds Step 4 scope from saved report metadata', () => {
  assert.deepEqual(
    deriveProbabilisticReportRouteState({
      routeQuery: {},
      reportRecord: {
        ensemble_id: '0004',
        run_id: '0002',
        probabilistic_context: {
          artifact_type: 'probabilistic_report_context'
        }
      }
    }),
    {
      runtimeMode: 'probabilistic',
      ensembleId: '0004',
      runId: '0002',
      probabilisticReportActive: true
    }
  )

  assert.deepEqual(
    deriveProbabilisticReportRouteState({
      routeQuery: {
        mode: 'probabilistic',
        ensembleId: '0099',
        runId: '0098'
      },
      reportRecord: {
        ensemble_id: '0004',
        run_id: '0002'
      }
    }),
    {
      runtimeMode: 'probabilistic',
      ensembleId: '0004',
      runId: '0002',
      probabilisticReportActive: true
    }
  )
})

test('deriveProbabilisticReportRouteState treats route query as bootstrap-only after report load', () => {
  assert.deepEqual(
    deriveProbabilisticReportRouteState({
      routeQuery: {
        mode: 'probabilistic',
        ensembleId: '0099',
        runId: '0098'
      },
      reportRecord: null
    }),
    {
      runtimeMode: 'probabilistic',
      ensembleId: '0099',
      runId: '0098',
      probabilisticReportActive: true
    }
  )

  assert.deepEqual(
    deriveProbabilisticReportRouteState({
      routeQuery: {
        mode: 'probabilistic',
        ensembleId: '0099',
        runId: '0098'
      },
      reportRecord: {
        simulation_id: 'sim-legacy-report'
      }
    }),
    {
      runtimeMode: 'legacy',
      ensembleId: null,
      runId: null,
      probabilisticReportActive: false
    }
  )
})

test('sortSimulationHistory keeps newest saved reports first with deterministic ties', () => {
  const input = [
    {
      simulation_id: 'sim-older',
      report_id: 'report-older',
      created_at: '2026-03-08T08:00:00Z'
    },
    {
      simulation_id: 'sim-newer-a',
      report_id: 'report-a',
      created_at: '2026-03-09T09:00:00Z'
    },
    {
      simulation_id: 'sim-newer-b',
      report_id: 'report-b',
      created_at: '2026-03-09T09:00:00Z'
    }
  ]

  const sorted = sortSimulationHistory(input)

  assert.deepEqual(
    sorted.map((project) => [project.simulation_id, project.report_id]),
    [
      ['sim-newer-b', 'report-b'],
      ['sim-newer-a', 'report-a'],
      ['sim-older', 'report-older']
    ]
  )
  assert.deepEqual(
    input.map((project) => [project.simulation_id, project.report_id]),
    [
      ['sim-older', 'report-older'],
      ['sim-newer-a', 'report-a'],
      ['sim-newer-b', 'report-b']
    ]
  )
})

test('getHistoryCardZIndex keeps newest collapsed cards on top and expanded cards in render order', () => {
  assert.ok(
    getHistoryCardZIndex({ index: 0, total: 4, isExpanded: false })
    > getHistoryCardZIndex({ index: 3, total: 4, isExpanded: false })
  )

  assert.equal(
    getHistoryCardZIndex({ index: 0, total: 4, isExpanded: true }),
    100
  )
  assert.equal(
    getHistoryCardZIndex({ index: 3, total: 4, isExpanded: true }),
    103
  )
})

test('history expansion toggle label reflects the current stack mode', () => {
  assert.equal(typeof runtimeUtils.getHistoryExpansionToggleLabel, 'function')
  assert.equal(
    runtimeUtils.getHistoryExpansionToggleLabel({ isExpanded: false }),
    'Expand history'
  )
  assert.equal(
    runtimeUtils.getHistoryExpansionToggleLabel({ isExpanded: true }),
    'Collapse history'
  )
})

test('collapsed history keeps only the top card interactive until the stack is expanded', () => {
  assert.equal(typeof runtimeUtils.isHistoryCardInteractive, 'function')

  assert.equal(
    runtimeUtils.isHistoryCardInteractive({ index: 0, isExpanded: false }),
    true
  )
  assert.equal(
    runtimeUtils.isHistoryCardInteractive({ index: 1, isExpanded: false }),
    false
  )
  assert.equal(
    runtimeUtils.isHistoryCardInteractive({ index: 4, isExpanded: false }),
    false
  )
  assert.equal(
    runtimeUtils.isHistoryCardInteractive({ index: 2, isExpanded: true }),
    true
  )
})

test('history test ids stay keyed to simulation and report identity', () => {
  const project = {
    simulation_id: 'sim_1234',
    report_id: 'report_5678'
  }

  assert.equal(
    buildHistoryCardTestId(project),
    'history-card--sim_1234--report_5678'
  )
  assert.equal(
    buildHistoryActionTestId(project, 'step5'),
    'history-action-step5--sim_1234--report_5678'
  )
  assert.equal(
    buildHistoryActionTestId(project, 'step3'),
    'history-action-step3--sim_1234--report_5678'
  )
})

test('deriveHistoryStep3ReplayState enables Step 3 replay only for saved probabilistic scope', () => {
  assert.deepEqual(
    deriveHistoryStep3ReplayState({
      simulation_id: 'sim_1234',
      latest_report: {
        report_id: 'report_5678',
        ensemble_id: '0007',
        run_id: '0003'
      }
    }),
    {
      enabled: true,
      simulationId: 'sim_1234',
      ensembleId: '0007',
      runId: '0003',
      routeTarget: {
        name: 'SimulationRun',
        params: {
          simulationId: 'sim_1234'
        },
        query: {
          mode: 'probabilistic',
          ensembleId: '0007',
          runId: '0003'
        }
      },
      helperText: 'Reopen the saved probabilistic Step 3 shell for this report-scoped run.'
    }
  )

  assert.deepEqual(
    deriveHistoryStep3ReplayState({
      simulation_id: 'sim_storage',
      latest_probabilistic_runtime: {
        source: 'storage',
        ensemble_id: '0008',
        run_id: '0004'
      }
    }),
    {
      enabled: true,
      simulationId: 'sim_storage',
      ensembleId: '0008',
      runId: '0004',
      routeTarget: {
        name: 'SimulationRun',
        params: {
          simulationId: 'sim_storage'
        },
        query: {
          mode: 'probabilistic',
          ensembleId: '0008',
          runId: '0004'
        }
      },
      helperText: 'Reopen the latest stored probabilistic Step 3 shell for this simulation.'
    }
  )

  assert.deepEqual(
    deriveHistoryStep3ReplayState({
      simulation_id: 'sim_legacy',
      latest_report: {
        report_id: 'report_legacy'
      }
    }),
    {
      enabled: false,
      simulationId: 'sim_legacy',
      ensembleId: null,
      runId: null,
      routeTarget: null,
      helperText: 'Step 3 replay is available only when history includes probabilistic runtime scope for one ensemble and run.'
    }
  )
})

test('buildProbabilisticEnsembleRequest normalizes ensemble sizing and rejects invalid counts', () => {
  assert.deepEqual(
    buildProbabilisticEnsembleRequest(),
    {
      run_count: 8,
      max_concurrency: 1
    }
  )

  assert.deepEqual(
    buildProbabilisticEnsembleRequest({
      runCount: '12',
      maxConcurrency: '3'
    }),
    {
      run_count: 12,
      max_concurrency: 3
    }
  )

  assert.throws(
    () => buildProbabilisticEnsembleRequest({ runCount: 0 }),
    /positive integer/i
  )

  assert.throws(
    () => buildProbabilisticEnsembleRequest({ runCount: 2, maxConcurrency: 3 }),
    /cannot exceed run count/i
  )
})

test('buildProbabilisticRunStartRequest defaults probabilistic Step 3 starts to graph-memory on', () => {
  assert.deepEqual(
    buildProbabilisticRunStartRequest(),
    {
      platform: 'parallel',
      force: true,
      enable_graph_memory_update: true,
      close_environment_on_complete: true
    }
  )

  assert.deepEqual(
    buildProbabilisticRunStartRequest({
      maxRounds: '18',
      enableGraphMemoryUpdate: true,
      closeEnvironmentOnComplete: false,
      force: false
    }),
    {
      platform: 'parallel',
      force: false,
      enable_graph_memory_update: true,
      close_environment_on_complete: false,
      max_rounds: 18
    }
  )
})

test('deriveStep3GraphRequest uses preview polling while Step 3 is active and full mode otherwise', () => {
  assert.deepEqual(
    deriveStep3GraphRequest({
      currentStatus: 'processing',
      manual: false
    }),
    {
      mode: 'preview',
      maxNodes: 180,
      maxEdges: 320,
      allowAutoRefresh: true,
      manualOnlyAfterCompletion: false
    }
  )

  assert.deepEqual(
    deriveStep3GraphRequest({
      currentStatus: 'completed',
      manual: true
    }),
    {
      mode: 'full',
      maxNodes: null,
      maxEdges: null,
      allowAutoRefresh: false,
      manualOnlyAfterCompletion: true
    }
  )
})

test('resolveStep3GraphScope prefers runtime graph ids for probabilistic runs and falls back safely', () => {
  assert.deepEqual(
    resolveStep3GraphScope({
      runtimeMode: 'probabilistic',
      projectGraphId: 'graph-base',
      runStatus: {
        base_graph_id: 'graph-base',
        runtime_graph_id: 'graph-runtime'
      }
    }),
    {
      graphId: 'graph-runtime',
      baseGraphId: 'graph-base',
      runtimeGraphId: 'graph-runtime',
      usesRuntimeGraph: true
    }
  )

  assert.deepEqual(
    resolveStep3GraphScope({
      runtimeMode: 'probabilistic',
      projectGraphId: 'graph-project',
      runStatus: {
        graph_id: 'graph-base'
      }
    }),
    {
      graphId: 'graph-base',
      baseGraphId: 'graph-base',
      runtimeGraphId: null,
      usesRuntimeGraph: false
    }
  )

  assert.deepEqual(
    resolveStep3GraphScope({
      runtimeMode: 'legacy',
      projectGraphId: 'graph-project',
      runStatus: {
        runtime_graph_id: 'graph-runtime'
      }
    }),
    {
      graphId: 'graph-project',
      baseGraphId: 'graph-project',
      runtimeGraphId: null,
      usesRuntimeGraph: false
    }
  )
})

test('mergeGraphDataPayloads keeps the base graph visible while runtime graph memory warms up', () => {
  const merged = mergeGraphDataPayloads({
    mode: 'preview',
    maxNodes: 180,
    maxEdges: 320,
    payloads: [
      {
        mode: 'preview',
        truncated: true,
        returned_nodes: 2,
        returned_edges: 1,
        total_nodes: 24,
        total_edges: 40,
        nodes: [
          { uuid: 'base-1', name: 'Plaza', labels: ['Entity', 'Place'] },
          { uuid: 'base-2', name: 'Community', labels: ['Entity', 'Community'] }
        ],
        edges: [
          {
            uuid: 'edge-1',
            name: 'CONNECTED_TO',
            source_node_uuid: 'base-1',
            target_node_uuid: 'base-2'
          }
        ]
      },
      {
        mode: 'preview',
        truncated: false,
        returned_nodes: 0,
        returned_edges: 0,
        total_nodes: 0,
        total_edges: 0,
        nodes: [],
        edges: []
      }
    ]
  })

  assert.equal(merged.mode, 'preview')
  assert.equal(merged.truncated, true)
  assert.equal(merged.returned_nodes, 2)
  assert.equal(merged.returned_edges, 1)
  assert.equal(merged.total_nodes, 24)
  assert.equal(merged.total_edges, 40)
  assert.deepEqual(
    merged.nodes.map((node) => node.uuid),
    ['base-1', 'base-2']
  )
})

test('mergeGraphDataPayloads dedupes shared entities and respects preview caps', () => {
  const merged = mergeGraphDataPayloads({
    mode: 'preview',
    maxNodes: 2,
    maxEdges: 1,
    payloads: [
      {
        mode: 'preview',
        truncated: false,
        returned_nodes: 2,
        returned_edges: 1,
        total_nodes: 2,
        total_edges: 1,
        nodes: [
          { uuid: 'base-1', name: 'Plaza', labels: ['Entity', 'Place'] },
          { uuid: 'base-2', name: 'Community', labels: ['Entity', 'Community'] }
        ],
        edges: [
          {
            uuid: 'edge-1',
            name: 'CONNECTED_TO',
            source_node_uuid: 'base-1',
            target_node_uuid: 'base-2'
          }
        ]
      },
      {
        mode: 'preview',
        truncated: false,
        returned_nodes: 2,
        returned_edges: 1,
        total_nodes: 2,
        total_edges: 1,
        nodes: [
          { uuid: 'base-2', name: 'Community', labels: ['Entity', 'Community'] },
          { uuid: 'runtime-1', name: 'New Memory', labels: ['Entity', 'Memory'] }
        ],
        edges: [
          {
            uuid: 'edge-2',
            name: 'MENTIONS',
            source_node_uuid: 'runtime-1',
            target_node_uuid: 'base-2'
          }
        ]
      }
    ]
  })

  assert.equal(merged.truncated, true)
  assert.equal(merged.returned_nodes, 2)
  assert.equal(merged.returned_edges, 1)
  assert.equal(merged.total_nodes, 4)
  assert.equal(merged.total_edges, 2)
  assert.deepEqual(
    merged.nodes.map((node) => node.uuid),
    ['base-1', 'base-2']
  )
})

test('deriveGraphPanelState keeps preview and oversized graphs out of the heavy renderer', () => {
  assert.deepEqual(
    deriveGraphPanelState({
      graphData: {
        mode: 'preview',
        truncated: true,
        returned_nodes: 180,
        returned_edges: 320,
        total_nodes: 412,
        total_edges: 998,
        nodes: [],
        edges: []
      }
    }),
    {
      mode: 'preview',
      isInteractive: false,
      isPreview: true,
      isTruncated: true,
      returnedNodes: 180,
      returnedEdges: 320,
      totalNodes: 412,
      totalEdges: 998,
      reason: 'preview',
      summaryTitle: 'Live graph preview',
      summaryBody: 'Showing a capped sample while the simulation is active. Load the full graph manually after completion.',
      summaryDetail: 'Sampled 180 nodes and 320 edges from 412 nodes and 998 edges.'
    }
  )

  assert.equal(
    deriveGraphPanelState({
      graphData: {
        mode: 'full',
        truncated: false,
        returned_nodes: 175,
        returned_edges: 280,
        total_nodes: 175,
        total_edges: 280,
        nodes: new Array(175).fill({}),
        edges: new Array(280).fill({})
      }
    }).isInteractive,
    false
  )

  assert.equal(
    deriveGraphPanelState({
      graphData: {
        mode: 'full',
        truncated: false,
        returned_nodes: 32,
        returned_edges: 44,
        total_nodes: 32,
        total_edges: 44,
        nodes: new Array(32).fill({}),
        edges: new Array(44).fill({})
      }
    }).isInteractive,
    true
  )
})

test('Step 2 keeps probabilistic prepare in flight until the active prepare task clears', () => {
  assert.equal(
    isStep2PrepareInFlight({
      hasStartedPrepare: true,
      phase: 1,
      activePrepareTaskId: 'task-probabilistic'
    }),
    true
  )

  assert.equal(
    shouldPromoteStep2ReadyState({
      configGenerated: true,
      config: {
        simulation_id: 'sim-probabilistic'
      },
      activePrepareTaskId: 'task-probabilistic'
    }),
    false
  )

  assert.equal(
    shouldPromoteStep2ReadyState({
      configGenerated: true,
      config: {
        simulation_id: 'sim-probabilistic'
      },
      activePrepareTaskId: null
    }),
    true
  )
})

test('resolveProbabilisticRunSelection preserves explicit selection and recovers deterministically', () => {
  const runs = [
    { run_id: '0004', status: 'completed' },
    { run_id: '0002', status: 'running' },
    { run_id: '0003', status: 'prepared' }
  ]

  assert.deepEqual(
    resolveProbabilisticRunSelection({
      requestedRunId: '0003',
      runs
    }),
    {
      selectedRunId: '0003',
      selectedRun: runs[2],
      selectionMode: 'requested',
      requestedRunMissing: false
    }
  )

  assert.deepEqual(
    resolveProbabilisticRunSelection({
      requestedRunId: '9999',
      runs
    }),
    {
      selectedRunId: '0002',
      selectedRun: runs[1],
      selectionMode: 'fallback',
      requestedRunMissing: true
    }
  )
})

test('resolveProbabilisticRunSelection does not silently guess when Step 2 never provided a run id', () => {
  const runs = [
    { run_id: '0001', status: 'prepared' }
  ]

  assert.deepEqual(
    resolveProbabilisticRunSelection({
      requestedRunId: '',
      runs
    }),
    {
      selectedRunId: null,
      selectedRun: null,
      selectionMode: 'missing-request',
      requestedRunMissing: false
    }
  )

  assert.deepEqual(
    resolveProbabilisticRunSelection({
      requestedRunId: '0007',
      runs: []
    }),
    {
      selectedRunId: null,
      selectedRun: null,
      selectionMode: 'empty',
      requestedRunMissing: true
    }
  )
})

test('resolveProbabilisticRunSelection falls back using runner and storage status when manifest status is absent', () => {
  const runs = [
    { run_id: '0003', storage_status: 'prepared' },
    { run_id: '0002', runner_status: 'running' },
    { run_id: '0001', storage_status: 'completed' }
  ]

  assert.deepEqual(
    resolveProbabilisticRunSelection({
      requestedRunId: '9999',
      runs
    }),
    {
      selectedRunId: '0002',
      selectedRun: runs[1],
      selectionMode: 'fallback',
      requestedRunMissing: true
    }
  )
})

test('shouldLaunchProbabilisticRuntime requires prepared probabilistic artifacts', () => {
  assert.equal(
    shouldLaunchProbabilisticRuntime({
      selectedPrepareMode: 'probabilistic',
      preparedArtifactSummary: null
    }),
    false
  )

  assert.equal(
    shouldLaunchProbabilisticRuntime({
      selectedPrepareMode: 'probabilistic',
      preparedArtifactSummary: {
        mode: 'legacy'
      }
    }),
    false
  )

  assert.equal(
    shouldLaunchProbabilisticRuntime({
      selectedPrepareMode: 'legacy',
      preparedArtifactSummary: {
        probabilistic_mode: true
      }
    }),
    true
  )

  assert.equal(
    shouldLaunchProbabilisticRuntime({
      selectedPrepareMode: 'legacy',
      preparedArtifactSummary: {
        mode: 'probabilistic'
      }
    }),
    true
  )

  assert.equal(
    shouldLaunchProbabilisticRuntime({
      selectedPrepareMode: 'legacy',
      preparedArtifactSummary: {
        mode: 'legacy'
      }
    }),
    false
  )
})

test('getStep2HandoffState blocks probabilistic handoff until prepare artifacts exist', () => {
  assert.deepEqual(
    getStep2HandoffState({
      simulationId: 'sim-1',
      phase: 4,
      selectedPrepareMode: 'probabilistic',
      capabilitiesKnown: true,
      capabilities: {
        probabilistic_ensemble_storage_enabled: true
      }
    }),
    {
      disabled: true,
      helperText:
        'Probabilistic Step 3 requires probabilistic prepare artifacts. Run probabilistic prepare first or return to the legacy path.',
      runtimeBlocked: true
    }
  )

  assert.deepEqual(
    getStep2HandoffState({
      simulationId: 'sim-1',
      phase: 4,
      selectedPrepareMode: 'legacy',
      preparedArtifactSummary: {
        mode: 'legacy'
      },
      capabilitiesKnown: false,
      capabilities: null
    }),
    {
      disabled: false,
      helperText: '',
      runtimeBlocked: false
    }
  )
})

test('getStep2HandoffState blocks probabilistic handoff when runtime support is disabled after prepare succeeds', () => {
  assert.deepEqual(
    getStep2HandoffState({
      simulationId: 'sim-1',
      phase: 4,
      selectedPrepareMode: 'probabilistic',
      preparedArtifactSummary: {
        probabilistic_mode: true
      },
      capabilitiesKnown: true,
      capabilities: {
        probabilistic_ensemble_storage_enabled: false
      }
    }),
    {
      disabled: true,
      helperText: 'Probabilistic Step 3 runtime shells are disabled by backend capabilities. Re-enable probabilistic runtime support or return to the legacy path.',
      runtimeBlocked: true
    }
  )

  assert.deepEqual(
    getStep2HandoffState({
      simulationId: 'sim-1',
      phase: 4,
      selectedPrepareMode: 'probabilistic',
      capabilitiesKnown: false,
      capabilities: null
    }),
    {
      disabled: true,
      helperText:
        'Probabilistic Step 3 requires probabilistic prepare artifacts. Run probabilistic prepare first or return to the legacy path.',
      runtimeBlocked: true
    }
  )
})

test('getProbabilisticRuntimeShellErrorMessage prefers backend error payloads over generic request text', () => {
  assert.equal(
    getProbabilisticRuntimeShellErrorMessage({
      message: 'Request failed with status code 400',
      response: {
        data: {
          error: 'Missing probabilistic prepare artifacts: uncertainty_spec.json'
        }
      }
    }),
    'Missing probabilistic prepare artifacts: uncertainty_spec.json'
  )

  assert.equal(
    getProbabilisticRuntimeShellErrorMessage(new Error('Stored run shell creation failed')),
    'Stored run shell creation failed'
  )

  assert.equal(
    getProbabilisticRuntimeShellErrorMessage({}),
    'Stored run shell creation failed'
  )
})

test('getStep3ReportState disables Step 4 for probabilistic runtime mode', () => {
  assert.deepEqual(getStep3ReportState('legacy'), {
    enabled: true,
    buttonLabel: 'Start generating the result report',
    helperText: ''
  })

  assert.deepEqual(getStep3ReportState('probabilistic'), {
    enabled: false,
    buttonLabel: 'Report generation unavailable',
    helperText: 'Step 4 report generation remains legacy-only for probabilistic Step 3 runs.'
  })

  assert.deepEqual(
    getStep3ReportState('probabilistic', {
      probabilistic_report_enabled: true
    }),
    {
      enabled: true,
      buttonLabel: 'Start generating the result report',
      helperText: 'Step 4 will keep the legacy report body and add observed empirical ensemble context for this probabilistic run family.'
    }
  )
})

test('getStep5InteractionState keeps probabilistic Step 5 honest about missing ensemble-aware chat context', () => {
  assert.deepEqual(getStep5InteractionState('legacy'), {
    showNotice: false,
    title: '',
    body: ''
  })

  assert.deepEqual(getStep5InteractionState('probabilistic'), {
    showNotice: true,
    title: 'Probabilistic interaction context unavailable',
    body: 'Step 5 still uses the legacy report and simulation context. Ensemble, run, and scenario-family grounding are not yet wired into chat or survey flows.'
  })

  assert.deepEqual(
    getStep5InteractionState('probabilistic', {
      hasSavedProbabilisticContext: true
    }),
    {
      showNotice: true,
      title: 'Saved probabilistic context detected',
      body: 'Report Agent chat can use this saved ensemble and run context from the current report. Interviews with simulated individuals and surveys still use the legacy interaction path, so treat only the report-agent lane as probabilistic-context-aware.'
    }
  )
})

test('buildReportAgentChatRequest prefers explicit report scope while preserving legacy fallback', () => {
  assert.deepEqual(
    buildReportAgentChatRequest({
      simulationId: 'sim-123',
      reportId: 'report-456',
      message: 'What does the ensemble show?',
      chatHistory: [
        { role: 'user', content: 'Earlier question' }
      ]
    }),
    {
      simulation_id: 'sim-123',
      report_id: 'report-456',
      message: 'What does the ensemble show?',
      chat_history: [
        { role: 'user', content: 'Earlier question' }
      ]
    }
  )

  assert.deepEqual(
    buildReportAgentChatRequest({
      simulationId: 'sim-legacy',
      message: 'Fallback path'
    }),
    {
      simulation_id: 'sim-legacy',
      message: 'Fallback path',
      chat_history: []
    }
  )
})

test('deriveProbabilisticStep3Runtime reports a hard error when probabilistic ids are missing', () => {
  assert.deepEqual(
    deriveProbabilisticStep3Runtime({
      runtimeMode: 'probabilistic',
      ensembleId: '',
      runId: null
    }),
    {
      requestedProbabilisticMode: true,
      isProbabilisticMode: false,
      normalizedEnsembleId: null,
      normalizedRunId: null,
      lifecycleStatus: 'prepared',
      storageStatus: 'prepared',
      selectedRunSeed: '-',
      waitingText: 'Probabilistic Step 3 is waiting for a stored run shell from Step 2.',
      runtimeError: 'Probabilistic Step 3 requires both ensemble and run identifiers from Step 2. Return to Step 2 and recreate the stored run shell.'
    }
  )
})

test('deriveProbabilisticStep3Runtime prefers runtime-backed status and seed metadata', () => {
  assert.deepEqual(
    deriveProbabilisticStep3Runtime({
      runtimeMode: 'probabilistic',
      ensembleId: 'ens-01',
      runId: 'run-09',
      runDetail: {
        status: 'prepared',
        run_manifest: {
          seed_metadata: {
            resolution_seed: 77,
            root_seed: 71
          }
        }
      },
      runStatus: {
        runner_status: 'running',
        storage_status: 'prepared',
        root_seed: 71
      }
    }),
    {
      requestedProbabilisticMode: true,
      isProbabilisticMode: true,
      normalizedEnsembleId: 'ens-01',
      normalizedRunId: 'run-09',
      lifecycleStatus: 'running',
      storageStatus: 'prepared',
      selectedRunSeed: 77,
      waitingText: 'Waiting for actions from stored run run-09 (running).',
      runtimeError: ''
    }
  )
})

test('deriveProbabilisticStep3Runtime preserves seed 0 as valid metadata', () => {
  assert.deepEqual(
    deriveProbabilisticStep3Runtime({
      runtimeMode: 'probabilistic',
      ensembleId: 'ens-00',
      runId: 'run-00',
      runDetail: {
        run_manifest: {
          seed_metadata: {
            resolution_seed: 0,
            root_seed: 0
          },
          root_seed: 0
        }
      },
      runStatus: {
        runner_status: 'running',
        storage_status: 'prepared',
        root_seed: 0
      }
    }),
    {
      requestedProbabilisticMode: true,
      isProbabilisticMode: true,
      normalizedEnsembleId: 'ens-00',
      normalizedRunId: 'run-00',
      lifecycleStatus: 'running',
      storageStatus: 'prepared',
      selectedRunSeed: 0,
      waitingText: 'Waiting for actions from stored run run-00 (running).',
      runtimeError: ''
    }
  )
})

test('deriveProbabilisticProgressSummary uses run progress instead of populated action rounds', () => {
  assert.equal(
    deriveProbabilisticProgressSummary({
      runStatus: {
        current_round: 43,
        total_rounds: 120
      },
      latestTimelineRound: 28,
      maxRounds: 120
    }),
    'R43/120'
  )
})

test('deriveProbabilisticActionRoundsMeta labels sparse timeline rows as populated rounds', () => {
  assert.equal(
    deriveProbabilisticActionRoundsMeta({
      timeline: [
        { round_num: 35 },
        { round_num: 36 },
        { round_num: 37 }
      ]
    }),
    '3 populated rounds'
  )
})

test('deriveProbabilisticPlatformSkewCopy explains a trailing community platform with an inflight round', () => {
  assert.equal(
    deriveProbabilisticPlatformSkewCopy({
      runStatus: {
        twitter_current_round: 43,
        reddit_current_round: 35,
        reddit_inflight_round: 36
      }
    }),
    'Info Plaza is ahead by 8 rounds; Topic Community is working on R36.'
  )
})

test('deriveProbabilisticStep3Runtime surfaces stopped runs without inventing report support', () => {
  assert.deepEqual(
    deriveProbabilisticStep3Runtime({
      runtimeMode: 'probabilistic',
      ensembleId: 'ens-03',
      runId: 'run-02',
      runDetail: {
        status: 'stopped',
        run_manifest: {
          root_seed: 41
        }
      },
      runStatus: {
        runner_status: 'stopped',
        storage_status: 'stored',
        root_seed: 41
      }
    }),
    {
      requestedProbabilisticMode: true,
      isProbabilisticMode: true,
      normalizedEnsembleId: 'ens-03',
      normalizedRunId: 'run-02',
      lifecycleStatus: 'stopped',
      storageStatus: 'stored',
      selectedRunSeed: 41,
      waitingText: 'Stored run run-02 stopped before completion. Step 3 remains monitor-only.',
      runtimeError: ''
    }
  )
})

test('deriveProbabilisticStep3Runtime keeps completed storage shells inactive when runtime status is idle', () => {
  assert.deepEqual(
    deriveProbabilisticStep3Runtime({
      runtimeMode: 'probabilistic',
      ensembleId: 'ens-04',
      runId: 'run-01',
      runDetail: {
        run_manifest: {
          root_seed: 101
        }
      },
      runStatus: {
        runner_status: 'idle',
        storage_status: 'completed',
        root_seed: 101
      }
    }),
    {
      requestedProbabilisticMode: true,
      isProbabilisticMode: true,
      normalizedEnsembleId: 'ens-04',
      normalizedRunId: 'run-01',
      lifecycleStatus: 'completed',
      storageStatus: 'completed',
      selectedRunSeed: 101,
      waitingText: 'Stored run run-01 completed. Raw actions remain available for review.',
      runtimeError: ''
    }
  )
})

test('deriveProbabilisticOperatorActions keeps active runs stop-only until they are inactive', () => {
  assert.deepEqual(
    deriveProbabilisticOperatorActions({
      lifecycleStatus: 'running'
    }),
    {
      start: {
        enabled: false,
        label: 'Launch selected run',
        intent: 'launch'
      },
      stop: {
        enabled: true,
        label: 'Stop selected run'
      },
      cleanup: {
        enabled: false,
        label: 'Clean selected run'
      },
      rerun: {
        enabled: false,
        label: 'Create child rerun'
      },
      guidance:
        'Stop the active run before cleanup or child rerun. Retry of the same run ID stays unavailable while the process is still active.'
    }
  )
})

test('deriveProbabilisticOperatorActions exposes retry, cleanup, and child rerun for inactive runs', () => {
  assert.deepEqual(
    deriveProbabilisticOperatorActions({
      lifecycleStatus: 'completed'
    }),
    {
      start: {
        enabled: true,
        label: 'Retry selected run',
        intent: 'retry'
      },
      stop: {
        enabled: false,
        label: 'Stop selected run'
      },
      cleanup: {
        enabled: true,
        label: 'Clean selected run'
      },
      rerun: {
        enabled: true,
        label: 'Create child rerun'
      },
      guidance:
        'Retry selected run restarts the same run ID and clears transient runtime traces first. Clean selected run resets transient runtime artifacts while preserving resolved inputs. Create child rerun keeps this run as evidence and prepares a new run ID with lineage back to it.'
    }
  )
})

test('deriveProbabilisticOperatorActions surfaces busy labels and blocks overlapping operator actions', () => {
  assert.deepEqual(
    deriveProbabilisticOperatorActions({
      lifecycleStatus: 'failed',
      isCleaning: true
    }),
    {
      start: {
        enabled: false,
        label: 'Retry selected run',
        intent: 'retry'
      },
      stop: {
        enabled: false,
        label: 'Stop selected run'
      },
      cleanup: {
        enabled: false,
        label: 'Cleaning selected run...'
      },
      rerun: {
        enabled: false,
        label: 'Create child rerun'
      },
      guidance:
        'Retry selected run restarts the same run ID and clears transient runtime traces first. Clean selected run resets transient runtime artifacts while preserving resolved inputs. Create child rerun keeps this run as evidence and prepares a new run ID with lineage back to it.'
    }
  )
})

test('deriveProbabilisticCapabilityState normalizes downstream rollout flags', () => {
  assert.deepEqual(
    deriveProbabilisticCapabilityState({
      probabilistic_prepare_enabled: true,
      probabilistic_ensemble_storage_enabled: true,
      probabilistic_report_enabled: false,
      probabilistic_interaction_enabled: false,
      calibrated_probability_enabled: false
    }),
    {
      prepareEnabled: true,
      runtimeEnabled: true,
      reportEnabled: false,
      interactionEnabled: false,
      calibratedEnabled: false,
      reportModeLabel: 'legacy-only',
      interactionModeLabel: 'legacy-only',
      calibrationModeLabel: 'empirical-only'
    }
  )
})

test('deriveProbabilisticCapabilityState falls back to legacy aliases and disabled defaults', () => {
  assert.deepEqual(
    deriveProbabilisticCapabilityState({
      ensemble_runtime_enabled: true,
      calibrated_probability_enabled: true
    }),
    {
      prepareEnabled: false,
      runtimeEnabled: true,
      reportEnabled: false,
      interactionEnabled: false,
      calibratedEnabled: true,
      reportModeLabel: 'legacy-only',
      interactionModeLabel: 'legacy-only',
      calibrationModeLabel: 'calibrated'
    }
  )
})

test('deriveProbabilisticReportContextState preserves embedded saved analytics when current flags are off', () => {
  assert.deepEqual(
    deriveProbabilisticReportContextState({
      simulationId: 'sim-1',
      runtimeMode: 'probabilistic',
      ensembleId: '0001',
      runId: '0002',
      reportContext: {
        aggregate_summary: {
          artifact_type: 'aggregate_summary'
        }
      },
      capabilitiesKnown: true,
      capabilities: {
        probabilistic_report_enabled: false
      }
    }),
    {
      shouldRender: true,
      hasEmbeddedArtifacts: true,
      isFlaggedOff: false,
      historicalNotice:
        'Saved probabilistic report context is shown from report metadata even though live probabilistic report surfaces are currently disabled by the backend flag.',
      fetchPlan: {
        summary: false,
        clusters: false,
        sensitivity: false
      }
    }
  )
})

test('deriveProbabilisticReportContextState fetches only missing saved-report artifacts when report surfaces are enabled', () => {
  assert.deepEqual(
    deriveProbabilisticReportContextState({
      simulationId: 'sim-1',
      runtimeMode: 'probabilistic',
      ensembleId: '0001',
      runId: '0002',
      reportContext: {
        aggregate_summary: {
          artifact_type: 'aggregate_summary'
        }
      },
      capabilitiesKnown: true,
      capabilities: {
        probabilistic_report_enabled: true
      }
    }),
    {
      shouldRender: true,
      hasEmbeddedArtifacts: true,
      isFlaggedOff: false,
      historicalNotice: '',
      fetchPlan: {
        summary: false,
        clusters: true,
        sensitivity: true
      }
    }
  )
})

test('deriveProbabilisticAnalyticsCards summarizes partial empirical artifacts truthfully', () => {
  const cards = deriveProbabilisticAnalyticsCards({
    summaryArtifact: {
      quality_summary: {
        status: 'partial',
        warnings: ['thin_sample', 'degraded_runs_present']
      },
      metric_summaries: {
        'simulation.total_actions': {
          label: 'Simulation Total Actions',
          mean: 12.5,
          sample_count: 4,
          distribution_kind: 'continuous',
          min: 3,
          max: 19,
          warnings: ['thin_sample']
        }
      }
    },
    clustersArtifact: {
      quality_summary: {
        status: 'partial',
        warnings: ['low_confidence']
      },
      cluster_count: 2,
      clusters: [
        {
          probability_mass: 0.75,
          prototype_run_id: '0004'
        }
      ]
    },
    sensitivityArtifact: {
      methodology: {
        analysis_mode: 'observational_resolved_values'
      },
      quality_summary: {
        status: 'complete',
        warnings: ['observational_only', 'thin_sample']
      },
      driver_count: 1,
      driver_rankings: [
        {
          field_path: 'twitter_config.echo_chamber_strength',
          metric_impacts: [
            {
              metric_id: 'simulation.total_actions',
              effect_size: 9
            }
          ]
        }
      ]
    }
  })

  assert.equal(cards.summary.status, 'partial')
  assert.match(cards.summary.headline, /Simulation Total Actions/i)
  assert.match(cards.summary.body, /mean 12\.5/i)
  assert.deepEqual(cards.summary.warnings, ['Thin sample', 'Degraded runs present'])

  assert.equal(cards.clusters.status, 'partial')
  assert.match(cards.clusters.headline, /2 observed clusters/i)
  assert.match(cards.clusters.body, /largest observed cluster/i)
  assert.deepEqual(cards.clusters.warnings, ['Low confidence'])

  assert.equal(cards.sensitivity.status, 'complete')
  assert.match(cards.sensitivity.headline, /twitter_config\.echo_chamber_strength/)
  assert.match(cards.sensitivity.body, /observational/i)
  assert.deepEqual(cards.sensitivity.warnings, ['Observational only', 'Thin sample'])
})

test('deriveProbabilisticAnalyticsCards explains binary and categorical aggregate summaries generically', () => {
  const binaryCards = deriveProbabilisticAnalyticsCards({
    summaryArtifact: {
      quality_summary: {
        status: 'complete',
        warnings: []
      },
      metric_summaries: {
        'simulation.completed': {
          label: 'Simulation Completed',
          distribution_kind: 'binary',
          sample_count: 6,
          empirical_probability: 2 / 3,
          counts: {
            true: 4,
            false: 2
          }
        }
      }
    }
  })

  assert.match(binaryCards.summary.headline, /Simulation Completed/i)
  assert.match(binaryCards.summary.body, /4 true and 2 false/i)

  const categoricalCards = deriveProbabilisticAnalyticsCards({
    summaryArtifact: {
      quality_summary: {
        status: 'complete',
        warnings: []
      },
      metric_summaries: {
        'platform.leading_platform': {
          label: 'Leading Platform',
          distribution_kind: 'categorical',
          sample_count: 5,
          category_counts: {
            twitter: 3,
            reddit: 2
          },
          category_probabilities: {
            twitter: 0.6,
            reddit: 0.4
          }
        }
      }
    }
  })

  assert.match(categoricalCards.summary.headline, /Leading Platform/i)
  assert.match(categoricalCards.summary.body, /twitter/i)
  assert.match(categoricalCards.summary.body, /60%/i)
})

test('deriveProbabilisticAnalyticsCards exposes loading, error, and empty states', () => {
  const cards = deriveProbabilisticAnalyticsCards({
    loadingByKey: {
      summary: true
    },
    errorByKey: {
      clusters: 'Cluster artifact unavailable'
    },
    sensitivityArtifact: {
      methodology: {
        analysis_mode: 'observational_resolved_values'
      },
      quality_summary: {
        status: 'partial',
        warnings: ['observational_only', 'no_varying_drivers']
      },
      driver_count: 0,
      driver_rankings: []
    }
  })

  assert.equal(cards.summary.status, 'loading')
  assert.match(cards.summary.body, /loading/i)

  assert.equal(cards.clusters.status, 'error')
  assert.match(cards.clusters.body, /Cluster artifact unavailable/)

  assert.equal(cards.sensitivity.status, 'empty')
  assert.match(cards.sensitivity.body, /No varying drivers/i)
  assert.deepEqual(cards.sensitivity.warnings, ['Observational only', 'No varying drivers'])
})

test('Step 2 blocks probabilistic Step 3 handoff when runtime shells are disabled', () => {
  assert.equal(typeof runtimeUtils.getStep2StartSimulationState, 'function')

  assert.deepEqual(
    runtimeUtils.getStep2StartSimulationState({
      simulationId: 'sim-1',
      phase: 4,
      selectedPrepareMode: 'probabilistic',
      preparedArtifactSummary: {
        probabilistic_mode: true
      },
      capabilities: {
        probabilistic_prepare_enabled: true,
        probabilistic_ensemble_storage_enabled: false
      }
    }),
    {
      enabled: false,
      helperText:
        'Probabilistic Step 3 runtime shells are disabled by backend capabilities. Re-enable probabilistic runtime support or return to the legacy path.'
    }
  )
})

test('Step 2 blocks probabilistic Step 3 handoff when probabilistic artifacts are missing', () => {
  assert.equal(typeof runtimeUtils.getStep2StartSimulationState, 'function')

  assert.deepEqual(
    runtimeUtils.getStep2StartSimulationState({
      simulationId: 'sim-1',
      phase: 4,
      selectedPrepareMode: 'probabilistic',
      preparedArtifactSummary: {
        mode: 'legacy'
      },
      capabilities: {
        probabilistic_prepare_enabled: true,
        probabilistic_ensemble_storage_enabled: true
      }
    }),
    {
      enabled: false,
      helperText:
        'Probabilistic Step 3 requires probabilistic prepare artifacts. Run probabilistic prepare first or return to the legacy path.'
    }
  )

  assert.deepEqual(
    runtimeUtils.getStep2StartSimulationState({
      simulationId: 'sim-1',
      phase: 4,
      selectedPrepareMode: 'legacy',
      preparedArtifactSummary: {
        mode: 'legacy'
      },
      capabilities: {
        probabilistic_prepare_enabled: true,
        probabilistic_ensemble_storage_enabled: true
      }
    }),
    {
      enabled: true,
      helperText: ''
    }
  )
})


test('resolveProbabilisticRunSelection falls back using runner and storage status when status is absent', () => {
  assert.deepEqual(
    resolveProbabilisticRunSelection({
      requestedRunId: 'missing-run',
      runs: [
        {
          run_id: '0001'
        },
        {
          run_id: '0009',
          runner_status: 'running'
        },
        {
          run_id: '0005',
          storage_status: 'completed'
        }
      ]
    }),
    {
      selectedRunId: '0009',
      selectedRun: {
        run_id: '0009',
        runner_status: 'running'
      },
      selectionMode: 'fallback',
      requestedRunMissing: true
    }
  )
})

test('saved probabilistic report context remains visible when current report flags are off', () => {
  assert.equal(typeof runtimeUtils.deriveProbabilisticReportContextState, 'function')

  assert.deepEqual(
    runtimeUtils.deriveProbabilisticReportContextState({
      runtimeMode: 'probabilistic',
      capabilities: {
        probabilistic_report_enabled: false
      },
      reportContext: {
        aggregate_summary: {
          artifact_type: 'aggregate_summary'
        }
      }
    }),
    {
      shouldRender: true,
      hasEmbeddedArtifacts: true,
      isFlaggedOff: false,
      historicalNotice:
        'Saved probabilistic report context is shown from report metadata even though live probabilistic report surfaces are currently disabled by the backend flag.',
      fetchPlan: {
        summary: false,
        clusters: false,
        sensitivity: false
      }
    }
  )
})
