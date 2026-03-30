import test from 'node:test'
import assert from 'node:assert/strict'

import {
  FORECAST_REQUIRED_PRIMITIVES,
  formatForecastBestEstimate,
  normalizeForecastCapabilities,
  summarizeForecastWorkspace
} from '../../src/utils/forecastRuntime.js'

test('normalizeForecastCapabilities preserves simulation as one worker in a hybrid system', () => {
  const normalized = normalizeForecastCapabilities({
    capabilities: {
      required_primitives: FORECAST_REQUIRED_PRIMITIVES,
      supported_worker_kinds: ['simulation', 'analytical', 'retrieval'],
      simulation: {
        role: 'scenario_worker',
        probability_interpretation: 'do_not_treat_as_real_world_probability',
        notes: ['Observed run shares are descriptive, not calibrated forecast probabilities.']
      }
    }
  })

  assert.deepEqual(normalized.requiredPrimitives, FORECAST_REQUIRED_PRIMITIVES)
  assert.equal(normalized.supportsHybridWorkers, true)
  assert.equal(normalized.simulationRole, 'scenario_worker')
  assert.equal(
    normalized.simulationProbabilityInterpretation,
    'do_not_treat_as_real_world_probability'
  )
})

test('summarizeForecastWorkspace distinguishes simulation-only from hybrid worker layouts', () => {
  const simulationOnly = summarizeForecastWorkspace({
    forecast_question: {
      forecast_id: 'forecast-001',
      title: 'Simulation only',
      question_text: 'Will the simulation-only scaffold stay additive?',
      issued_at: '2026-03-30T09:00:00'
    },
    evidence_bundle: {
      status: 'partial',
      source_entries: [{ source_id: 'source-1' }, { source_id: 'source-2' }],
      retrieval_quality: {
        status: 'local_only_external_unavailable'
      },
      uncertainty_summary: {
        causes: ['provider_unavailable', 'relevance_uncertain']
      }
    },
    forecast_workers: [
      { worker_id: 'worker-sim', kind: 'simulation' }
    ],
    prediction_ledger: {
      entries: [{ entry_id: 'entry-1' }],
      final_resolution_state: 'pending'
    },
    forecast_answers: [],
    simulation_worker_contract: {
      worker_id: 'worker-sim'
    }
  })

  const hybrid = summarizeForecastWorkspace({
    forecast_question: {
      forecast_id: 'forecast-002',
      title: 'Hybrid'
    },
    evidence_bundle: {
      bundle_id: 'bundle-002',
      status: 'ready',
      source_entries: [
        { source_id: 'source-1' },
        { source_id: 'source-2' }
      ],
      freshness_status: 'fresh',
      relevance_status: 'high',
      quality_score: 0.88,
      conflict_markers: [],
      missing_evidence_markers: []
    },
    forecast_workers: [
      { worker_id: 'worker-sim', kind: 'simulation' },
      { worker_id: 'worker-analytical', kind: 'analytical' }
    ],
    prediction_ledger: {
      entries: [{ entry_id: 'entry-1' }]
    },
    forecast_answers: [{
      confidence_semantics: 'uncalibrated',
      calibration_summary: {
        status: 'not_applicable'
      },
      answer_type: 'hybrid_forecast',
      answer_payload: {
        abstain: false,
        best_estimate: {
          value: 0.63,
          value_semantics: 'forecast_probability',
          why: 'Base rate and retrieval aligned.'
        },
        counterevidence: ['One worker remained cautious.'],
        assumption_summary: {
          items: ['Evidence is fresh', 'Reference class is comparable']
        },
        uncertainty_decomposition: {
          components: [{ code: 'evidence_spread', summary: 'Evidence spread remains bounded.' }]
        },
        worker_contribution_trace: [{ summary: 'Simulation contributed supporting scenario analysis only.' }],
        evaluation_summary: { status: 'available', case_count: 2 },
        confidence_basis: {
          status: 'available',
          benchmark_status: 'available',
          calibration_status: 'not_applicable',
          note: 'Evaluation is available, but no workspace calibration claim is made.'
        },
        simulation_context: {
          observed_run_share: 0.81
        }
      }
    }],
    evaluation_cases: [
      { case_id: 'case-1', status: 'resolved' }
    ],
    simulation_worker_contract: {
      worker_id: 'worker-sim'
    }
  })

  assert.equal(simulationOnly.simulationIsOnlyWorker, true)
  assert.equal(simulationOnly.hasHybridWorkers, false)
  assert.equal(simulationOnly.predictionEntryCount, 1)
  assert.equal(simulationOnly.questionText, 'Will the simulation-only scaffold stay additive?')
  assert.equal(simulationOnly.issuedAt, '2026-03-30T09:00:00')
  assert.equal(simulationOnly.finalResolutionState, 'pending')
  assert.equal(simulationOnly.evidenceBundleStatus, 'partial')
  assert.equal(simulationOnly.evidenceEntryCount, 2)
  assert.equal(simulationOnly.retrievalQualityStatus, 'local_only_external_unavailable')
  assert.deepEqual(simulationOnly.evidenceUncertaintyCauses, ['provider_unavailable', 'relevance_uncertain'])
  assert.equal(hybrid.simulationIsOnlyWorker, false)
  assert.equal(hybrid.hasHybridWorkers, true)
  assert.equal(hybrid.latestAnswerType, 'hybrid_forecast')
  assert.equal(hybrid.latestAnswerAbstained, false)
  assert.equal(hybrid.latestBestEstimate, 0.63)
  assert.equal(hybrid.latestBestEstimateSemantics, 'forecast_probability')
  assert.equal(hybrid.latestBestEstimateWhy, 'Base rate and retrieval aligned.')
  assert.deepEqual(hybrid.latestCounterevidence, ['One worker remained cautious.'])
  assert.deepEqual(hybrid.latestAssumptionItems, ['Evidence is fresh', 'Reference class is comparable'])
  assert.deepEqual(hybrid.latestUncertaintyComponents, ['Evidence spread remains bounded.'])
  assert.deepEqual(hybrid.latestWorkerComparison, ['Simulation contributed supporting scenario analysis only.'])
  assert.equal(hybrid.latestSimulationObservedRunShare, 0.81)
  assert.equal(hybrid.statusSurface.evidenceAvailable, true)
  assert.equal(hybrid.statusSurface.evaluationAvailable, true)
  assert.equal(hybrid.statusSurface.calibratedConfidenceEarned, false)
  assert.equal(hybrid.statusSurface.simulationOnlyScenarioExploration, false)
})

test('summarizeForecastWorkspace requires explicit calibrated semantics before surfacing earned calibration', () => {
  const summary = summarizeForecastWorkspace({
    forecast_question: {
      forecast_id: 'forecast-003',
      title: 'Uncalibrated binary workspace'
    },
    evidence_bundle: {
      status: 'ready',
      source_entries: [{ source_id: 'source-1' }]
    },
    forecast_workers: [
      { worker_id: 'worker-sim', kind: 'simulation' },
      { worker_id: 'worker-base', kind: 'base_rate' }
    ],
    prediction_ledger: {
      entries: [{ entry_id: 'entry-1' }]
    },
    forecast_answers: [{
      confidence_semantics: 'uncalibrated',
      answer_payload: {
        abstain: false,
        best_estimate: {
          value: 0.58,
          value_semantics: 'forecast_probability'
        },
        evaluation_summary: {
          status: 'available',
          case_count: 2,
          resolved_case_count: 1
        },
        confidence_basis: {
          status: 'available',
          benchmark_status: 'available',
          calibration_status: 'available',
          note: 'Calibration artifacts exist, but no workspace calibration claim is made.'
        }
      }
    }],
    evaluation_cases: [
      { case_id: 'case-1', status: 'resolved' }
    ]
  })

  assert.equal(summary.statusSurface.evaluationAvailable, true)
  assert.equal(summary.statusSurface.calibratedConfidenceEarned, false)
})

test('summarizeForecastWorkspace can surface earned calibration only for explicit calibrated answers', () => {
  const summary = summarizeForecastWorkspace({
    forecast_question: {
      forecast_id: 'forecast-004',
      title: 'Explicit calibrated workspace'
    },
    evidence_bundle: {
      status: 'ready',
      source_entries: [{ source_id: 'source-1' }]
    },
    forecast_workers: [
      { worker_id: 'worker-sim', kind: 'simulation' },
      { worker_id: 'worker-base', kind: 'base_rate' }
    ],
    prediction_ledger: {
      entries: [{ entry_id: 'entry-1' }]
    },
    forecast_answers: [{
      confidence_semantics: 'calibrated',
      calibration_summary: {
        status: 'ready'
      },
      answer_payload: {
        abstain: false,
        best_estimate: {
          value: 0.54,
          value_semantics: 'forecast_probability'
        },
        evaluation_summary: {
          status: 'available',
          case_count: 12,
          resolved_case_count: 12
        },
        confidence_basis: {
          status: 'available',
          resolved_case_count: 12,
          benchmark_status: 'available',
          backtest_status: 'ready',
          calibration_status: 'ready',
          note: 'Binary evaluation and calibration are both ready.'
        }
      }
    }],
    evaluation_cases: [
      { case_id: 'case-1', status: 'resolved' }
    ]
  })

  assert.equal(summary.statusSurface.calibratedConfidenceEarned, true)
})

test('summarizeForecastWorkspace still blocks earned calibration without resolved backtest basis', () => {
  const summary = summarizeForecastWorkspace({
    forecast_question: {
      forecast_id: 'forecast-005',
      title: 'Calibrated label without basis'
    },
    evidence_bundle: {
      status: 'ready',
      source_entries: [{ source_id: 'source-1' }]
    },
    forecast_workers: [
      { worker_id: 'worker-sim', kind: 'simulation' },
      { worker_id: 'worker-base', kind: 'base_rate' }
    ],
    prediction_ledger: {
      entries: [{ entry_id: 'entry-1' }]
    },
    forecast_answers: [{
      confidence_semantics: 'calibrated',
      calibration_summary: {
        status: 'ready'
      },
      answer_payload: {
        abstain: false,
        best_estimate: {
          value: 0.54,
          value_semantics: 'forecast_probability'
        },
        evaluation_summary: {
          status: 'available',
          case_count: 12,
          resolved_case_count: 0
        },
        confidence_basis: {
          status: 'available',
          resolved_case_count: 0,
          benchmark_status: 'available',
          backtest_status: 'not_run',
          calibration_status: 'ready',
          note: 'Calibration metadata exists, but the answer lacks resolved backtest basis.'
        }
      }
    }]
  })

  assert.equal(summary.statusSurface.calibratedConfidenceEarned, false)
})

test('formatForecastBestEstimate keeps non-probability semantics literal', () => {
  assert.equal(formatForecastBestEstimate(0.63, 'forecast_probability'), '63%')
  assert.equal(formatForecastBestEstimate(12.5, 'index_score'), '12.5 (index score)')
})

test('formatForecastBestEstimate renders categorical and numeric answer-native shapes', () => {
  assert.equal(
    formatForecastBestEstimate(
      {
        value_type: 'categorical_distribution',
        top_label: 'win',
        top_label_share: 0.62
      },
      'forecast_distribution'
    ),
    'win (62%)'
  )
  assert.equal(
    formatForecastBestEstimate(
      {
        value_type: 'numeric_interval',
        point_estimate: 42,
        unit: 'usd_millions',
        intervals: {
          '80': { low: 36, high: 50 }
        }
      },
      'numeric_interval_estimate'
    ),
    '42 usd_millions (80% interval 36 to 50)'
  )
})

test('summarizeForecastWorkspace preserves categorical and numeric best-estimate details', () => {
  const categorical = summarizeForecastWorkspace({
    forecast_question: {
      forecast_id: 'forecast-cat',
      title: 'Launch posture',
      question_type: 'categorical',
      question_text: 'Which launch posture will be observed?'
    },
    evidence_bundle: {
      status: 'ready',
      source_entries: [{ source_id: 'source-1' }]
    },
    forecast_workers: [
      { worker_id: 'worker-sim', kind: 'simulation' },
      { worker_id: 'worker-base', kind: 'base_rate' }
    ],
    prediction_ledger: {
      entries: [{ entry_id: 'entry-1' }]
    },
    forecast_answers: [{
      confidence_semantics: 'calibrated',
      calibration_summary: {
        status: 'ready'
      },
      answer_type: 'hybrid_forecast',
      answer_payload: {
        abstain: false,
        best_estimate: {
          value_type: 'categorical_distribution',
          value_semantics: 'forecast_distribution',
          top_label: 'win',
          top_label_share: 0.62,
          distribution: {
            win: 0.62,
            stretch: 0.24,
            miss: 0.14
          }
        },
        evaluation_summary: {
          status: 'available',
          resolved_case_count: 12
        },
        confidence_basis: {
          status: 'available',
          resolved_case_count: 12,
          benchmark_status: 'available',
          backtest_status: 'available',
          calibration_status: 'ready'
        }
      }
    }]
  })

  const numeric = summarizeForecastWorkspace({
    forecast_question: {
      forecast_id: 'forecast-num',
      title: 'ARR outlook',
      question_type: 'numeric',
      question_text: 'What ARR will be observed?'
    },
    evidence_bundle: {
      status: 'ready',
      source_entries: [{ source_id: 'source-1' }]
    },
    forecast_workers: [
      { worker_id: 'worker-sim', kind: 'simulation' },
      { worker_id: 'worker-base', kind: 'base_rate' }
    ],
    prediction_ledger: {
      entries: [{ entry_id: 'entry-1' }]
    },
    forecast_answers: [{
      confidence_semantics: 'calibrated',
      calibration_summary: {
        status: 'ready'
      },
      answer_type: 'hybrid_forecast',
      answer_payload: {
        abstain: false,
        best_estimate: {
          value_type: 'numeric_interval',
          value_semantics: 'numeric_interval_estimate',
          point_estimate: 42,
          unit: 'usd_millions',
          intervals: {
            '80': { low: 36, high: 50 }
          }
        },
        evaluation_summary: {
          status: 'available',
          resolved_case_count: 12
        },
        confidence_basis: {
          status: 'available',
          resolved_case_count: 12,
          benchmark_status: 'available',
          backtest_status: 'available',
          calibration_status: 'ready'
        }
      }
    }]
  })

  assert.equal(categorical.latestBestEstimateValueType, 'categorical_distribution')
  assert.deepEqual(categorical.latestBestEstimateDistribution, {
    win: 0.62,
    stretch: 0.24,
    miss: 0.14
  })
  assert.equal(categorical.latestBestEstimateDisplay, 'win (62%)')
  assert.equal(categorical.statusSurface.calibratedConfidenceEarned, true)

  assert.equal(numeric.latestBestEstimateValueType, 'numeric_interval')
  assert.equal(numeric.latestBestEstimateUnit, 'usd_millions')
  assert.deepEqual(numeric.latestBestEstimateIntervals, {
    '80': { low: 36, high: 50 }
  })
  assert.equal(numeric.latestBestEstimateDisplay, '42 usd_millions (80% interval 36 to 50)')
  assert.equal(numeric.statusSurface.calibratedConfidenceEarned, true)
})

test('formatForecastBestEstimate accepts numeric interval arrays from smoke fixtures', () => {
  assert.equal(
    formatForecastBestEstimate(
      {
        value_type: 'numeric_interval',
        value_semantics: 'numeric_interval_estimate',
        point_estimate: 42,
        unit: 'usd_millions',
        intervals: [
          { level: 50, low: 39, high: 45 },
          { level: 80, low: 36, high: 50 },
          { level: 90, low: 33, high: 54 }
        ]
      },
      'numeric_interval_estimate'
    ),
    '42 usd_millions (80% interval 36 to 50)'
  )
})
