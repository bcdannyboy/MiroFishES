import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

import {
  createLiveOperatorArtifactReader
} from '../../../tests/live/probabilistic-operator-local.helpers.mjs'

const writeJson = (filePath, payload) => {
  fs.mkdirSync(path.dirname(filePath), { recursive: true })
  fs.writeFileSync(filePath, JSON.stringify(payload, null, 2), 'utf-8')
}

const writeText = (filePath, contents) => {
  fs.mkdirSync(path.dirname(filePath), { recursive: true })
  fs.writeFileSync(filePath, contents, 'utf-8')
}

const writePreparedSimulation = (
  simulationsRoot,
  simulationId,
  {
    createdAt,
    configReasoning = 'Real prepared simulation',
    includeReadyRunScope = false
  } = {}
) => {
  const simulationDir = path.join(simulationsRoot, simulationId)
  writeJson(path.join(simulationDir, 'state.json'), {
    simulation_id: simulationId,
    created_at: createdAt,
    updated_at: createdAt,
    config_reasoning: configReasoning
  })
  writeJson(path.join(simulationDir, 'prepared_snapshot.json'), {
    probabilistic_mode: true
  })
  writeJson(path.join(simulationDir, 'grounding_bundle.json'), {
    status: 'ready',
    source_summary: {
      simulation_requirement: 'Real local probabilistic simulation'
    }
  })

  if (!includeReadyRunScope) {
    return
  }

  const runDir = path.join(
    simulationDir,
    'ensemble',
    'ensemble_0001',
    'runs',
    'run_0001'
  )
  writeJson(path.join(runDir, 'run_state.json'), {
    runner_status: 'completed',
    total_actions_count: 6,
    completed_at: createdAt
  })
  writeJson(path.join(runDir, 'run_manifest.json'), {
    status: 'completed',
    graph_id: 'graph-ready',
    completed_at: createdAt
  })
  writeJson(path.join(runDir, 'simulation_market_manifest.json'), {
    extraction_status: 'ready',
    forecast_workspace_linked: true,
    scope_linked_to_run: true,
    signal_counts: {
      agent_beliefs: 3,
      belief_updates: 6
    }
  })
  writeJson(path.join(runDir, 'market_snapshot.json'), {
    extraction_status: 'ready'
  })
  writeJson(path.join(runDir, 'metrics.json'), {
    metric_values: {
      'simulation.total_actions': {
        value: 6
      }
    },
    timeline_summaries: {
      total_actions: 6
    }
  })
  writeText(path.join(runDir, 'twitter', 'actions.jsonl'), '{"event_type":"action"}\n')
  writeText(path.join(runDir, 'reddit', 'actions.jsonl'), '{"event_type":"action"}\n')
}

test('resolveLiveStep45Selection prefers simulations with completed ready run scopes in mutation mode', () => {
  const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'mirofish-live-selection-'))
  const simulationsRoot = path.join(tempRoot, 'simulations')
  const reportsRoot = path.join(tempRoot, 'reports')

  writePreparedSimulation(simulationsRoot, 'sim_latest_report_only', {
    createdAt: '2026-03-31T19:00:00.000000'
  })
  writePreparedSimulation(simulationsRoot, 'sim_ready_history', {
    createdAt: '2026-03-30T19:00:00.000000',
    includeReadyRunScope: true
  })

  writeJson(path.join(reportsRoot, 'report_saved', 'meta.json'), {
    status: 'completed',
    simulation_id: 'sim_latest_report_only',
    ensemble_id: '0009',
    run_id: '0002',
    completed_at: '2026-03-31T19:30:00.000000',
    probabilistic_context: {
      simulation_market_summary: {
        status: 'ready'
      },
      signal_provenance_summary: {
        status: 'ready'
      },
      selected_run: {
        simulation_market: {
          market_snapshot: {
            status: 'ready'
          }
        }
      },
      forecast_workspace: {
        forecast_answer: {
          answer_payload: {
            best_estimate: 'cybersecurity'
          }
        }
      }
    }
  })

  const reader = createLiveOperatorArtifactReader({
    simulationsRoot,
    reportsRoot,
    processEnv: {
      PLAYWRIGHT_LIVE_ALLOW_MUTATION: 'true'
    }
  })

  const selection = reader.resolveLiveStep45Selection()

  assert.equal(selection.simulationId, 'sim_ready_history')
  assert.equal(selection.reportScopeSelection.source, 'completed-run')
  assert.equal(selection.reportScopeSelection.runId, '0001')
})

test('getLiveRunScopeTerminalIssue surfaces completed no-signal runs immediately', () => {
  const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'mirofish-live-evidence-'))
  const simulationsRoot = path.join(tempRoot, 'simulations')
  const reportsRoot = path.join(tempRoot, 'reports')
  const runDir = path.join(
    simulationsRoot,
    'sim_quiet',
    'ensemble',
    'ensemble_0001',
    'runs',
    'run_0001'
  )

  writeJson(path.join(runDir, 'run_state.json'), {
    runner_status: 'completed',
    total_actions_count: 0
  })
  writeJson(path.join(runDir, 'run_manifest.json'), {
    status: 'completed',
    graph_id: 'graph-quiet'
  })
  writeJson(path.join(runDir, 'simulation_market_manifest.json'), {
    extraction_status: 'no_signals',
    forecast_workspace_linked: true,
    scope_linked_to_run: true,
    signal_counts: {
      agent_beliefs: 0,
      belief_updates: 0
    }
  })
  writeJson(path.join(runDir, 'market_snapshot.json'), {
    extraction_status: 'no_signals'
  })
  writeJson(path.join(runDir, 'metrics.json'), {
    metric_values: {
      'simulation.total_actions': {
        value: 0
      }
    },
    timeline_summaries: {
      total_actions: 0
    }
  })
  writeText(path.join(runDir, 'twitter', 'actions.jsonl'), '{"event_type":"round_end","actions_count":0}\n')
  writeText(path.join(runDir, 'reddit', 'actions.jsonl'), '{"event_type":"round_end","actions_count":0}\n')

  const reader = createLiveOperatorArtifactReader({
    simulationsRoot,
    reportsRoot
  })

  const evidence = reader.readLiveRunScopeEvidence({
    simulationId: 'sim_quiet',
    ensembleId: '0001',
    runId: '0001'
  })
  const issue = reader.getLiveRunScopeTerminalIssue(evidence)

  assert.equal(reader.isLiveRunScopeReady(evidence), false)
  assert.match(issue, /no_signals/)
  assert.match(issue, /total_actions=0/)
})
