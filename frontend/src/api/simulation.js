import service, { requestWithRetry } from './index'

/**
 * Create a simulation.
 * @param {Object} data - { project_id, graph_id?, enable_twitter?, enable_reddit? }
 */
export const createSimulation = (data) => {
  return requestWithRetry(() => service.post('/api/simulation/create', data), 3, 1000)
}

/**
 * Prepare the simulation environment asynchronously.
 * @param {Object} data - { simulation_id, entity_types?, use_llm_for_profiles?, parallel_profile_count?, force_regenerate? }
 */
export const prepareSimulation = (data) => {
  return requestWithRetry(() => service.post('/api/simulation/prepare', data), 3, 1000)
}

/**
 * Fetch the current prepare capability surface for Step 2.
 */
export const getPrepareCapabilities = () => {
  return service.get('/api/simulation/prepare/capabilities')
}

/**
 * Query preparation task progress.
 * @param {Object} data - { task_id?, simulation_id?, probabilistic_mode? }
 */
export const getPrepareStatus = (data) => {
  return service.post('/api/simulation/prepare/status', data)
}

/**
 * Fetch simulation status.
 * @param {string} simulationId
 */
export const getSimulation = (simulationId) => {
  return service.get(`/api/simulation/${simulationId}`)
}

/**
 * Create a probabilistic ensemble under one prepared simulation.
 * @param {string} simulationId
 * @param {Object} data - { run_count, max_concurrency?, root_seed?, sampling_mode? }
 */
export const createSimulationEnsemble = (simulationId, data) => {
  return service.post(`/api/simulation/${simulationId}/ensembles`, data)
}

/**
 * List stored ensembles for one simulation.
 * @param {string} simulationId
 */
export const listSimulationEnsembles = (simulationId) => {
  return service.get(`/api/simulation/${simulationId}/ensembles`)
}

/**
 * Load one stored ensemble with lightweight run summaries.
 * @param {string} simulationId
 * @param {string} ensembleId
 */
export const getSimulationEnsemble = (simulationId, ensembleId) => {
  return service.get(`/api/simulation/${simulationId}/ensembles/${ensembleId}`)
}

/**
 * Fetch the persisted-on-demand aggregate summary for one ensemble.
 * @param {string} simulationId
 * @param {string} ensembleId
 */
export const getSimulationEnsembleSummary = (simulationId, ensembleId) => {
  return service.get(`/api/simulation/${simulationId}/ensembles/${ensembleId}/summary`)
}

/**
 * Fetch the persisted-on-demand scenario clusters for one ensemble.
 * @param {string} simulationId
 * @param {string} ensembleId
 */
export const getSimulationEnsembleClusters = (simulationId, ensembleId) => {
  return service.get(`/api/simulation/${simulationId}/ensembles/${ensembleId}/clusters`)
}

/**
 * Fetch the persisted-on-demand observational sensitivity artifact for one ensemble.
 * @param {string} simulationId
 * @param {string} ensembleId
 */
export const getSimulationEnsembleSensitivity = (simulationId, ensembleId) => {
  return service.get(`/api/simulation/${simulationId}/ensembles/${ensembleId}/sensitivity`)
}

/**
 * Launch an explicit batch of stored runs for one ensemble.
 * @param {string} simulationId
 * @param {string} ensembleId
 * @param {Object} data - { run_ids?, platform?, max_rounds?, enable_graph_memory_update?, force?, close_environment_on_complete? }
 */
export const startSimulationEnsemble = (simulationId, ensembleId, data = {}) => {
  return service.post(`/api/simulation/${simulationId}/ensembles/${ensembleId}/start`, data)
}

/**
 * Fetch poll-safe ensemble runtime status.
 * @param {string} simulationId
 * @param {string} ensembleId
 * @param {Object} params - { limit?, run_id? }
 */
export const getSimulationEnsembleStatus = (simulationId, ensembleId, params = {}) => {
  return service.get(`/api/simulation/${simulationId}/ensembles/${ensembleId}/status`, { params })
}

/**
 * List stored runs for one ensemble.
 * @param {string} simulationId
 * @param {string} ensembleId
 * @param {Object} params - { limit? }
 */
export const listSimulationEnsembleRuns = (simulationId, ensembleId, params = {}) => {
  return service.get(`/api/simulation/${simulationId}/ensembles/${ensembleId}/runs`, { params })
}

/**
 * Load one stored run, including its runtime status summary.
 * @param {string} simulationId
 * @param {string} ensembleId
 * @param {string} runId
 */
export const getSimulationEnsembleRun = (simulationId, ensembleId, runId) => {
  return service.get(`/api/simulation/${simulationId}/ensembles/${ensembleId}/runs/${runId}`)
}

/**
 * Create one fresh child run from an existing stored run.
 * @param {string} simulationId
 * @param {string} ensembleId
 * @param {string} runId
 */
export const rerunSimulationEnsembleRun = (simulationId, ensembleId, runId) => {
  return service.post(
    `/api/simulation/${simulationId}/ensembles/${ensembleId}/runs/${runId}/rerun`
  )
}

/**
 * Reset one explicit subset of stored runs back to the prepared state.
 * @param {string} simulationId
 * @param {string} ensembleId
 * @param {Object} data - { run_ids? }
 */
export const cleanupSimulationEnsembleRuns = (simulationId, ensembleId, data = {}) => {
  return service.post(`/api/simulation/${simulationId}/ensembles/${ensembleId}/cleanup`, data)
}

/**
 * Start one stored run under an ensemble.
 * @param {string} simulationId
 * @param {string} ensembleId
 * @param {string} runId
 * @param {Object} data - { platform?, max_rounds?, enable_graph_memory_update?, force?, close_environment_on_complete? }
 */
export const startSimulationEnsembleRun = (simulationId, ensembleId, runId, data = {}) => {
  return service.post(
    `/api/simulation/${simulationId}/ensembles/${ensembleId}/runs/${runId}/start`,
    data
  )
}

/**
 * Stop one stored run under an ensemble.
 * @param {string} simulationId
 * @param {string} ensembleId
 * @param {string} runId
 */
export const stopSimulationEnsembleRun = (simulationId, ensembleId, runId) => {
  return service.post(`/api/simulation/${simulationId}/ensembles/${ensembleId}/runs/${runId}/stop`)
}

/**
 * Fetch run-scoped runtime status for one stored ensemble member.
 * @param {string} simulationId
 * @param {string} ensembleId
 * @param {string} runId
 */
export const getSimulationEnsembleRunStatus = (simulationId, ensembleId, runId) => {
  return service.get(`/api/simulation/${simulationId}/ensembles/${ensembleId}/runs/${runId}/run-status`)
}

/**
 * Fetch run-scoped action history under the ensemble namespace.
 * @param {string} simulationId
 * @param {string} ensembleId
 * @param {string} runId
 * @param {Object} params - { limit, offset, platform, agent_id, round_num }
 */
export const getSimulationEnsembleRunActions = (
  simulationId,
  ensembleId,
  runId,
  params = {}
) => {
  return service.get(
    `/api/simulation/${simulationId}/ensembles/${ensembleId}/runs/${runId}/actions`,
    { params }
  )
}

/**
 * Fetch the run-scoped round timeline under the ensemble namespace.
 * @param {string} simulationId
 * @param {string} ensembleId
 * @param {string} runId
 * @param {Object} params - { start_round?, end_round? }
 */
export const getSimulationEnsembleRunTimeline = (
  simulationId,
  ensembleId,
  runId,
  params = {}
) => {
  return service.get(
    `/api/simulation/${simulationId}/ensembles/${ensembleId}/runs/${runId}/timeline`,
    { params }
  )
}

/**
 * Fetch the simulation's agent profiles.
 * @param {string} simulationId
 * @param {string} platform - 'reddit' | 'twitter'
 */
export const getSimulationProfiles = (simulationId, platform = 'reddit') => {
  return service.get(`/api/simulation/${simulationId}/profiles`, { params: { platform } })
}

/**
 * Fetch agent profiles while generation is still in progress.
 * @param {string} simulationId
 * @param {string} platform - 'reddit' | 'twitter'
 */
export const getSimulationProfilesRealtime = (simulationId, platform = 'reddit') => {
  return service.get(`/api/simulation/${simulationId}/profiles/realtime`, { params: { platform } })
}

/**
 * Fetch the simulation configuration.
 * @param {string} simulationId
 */
export const getSimulationConfig = (simulationId) => {
  return service.get(`/api/simulation/${simulationId}/config`)
}

/**
 * Fetch a simulation configuration while it is still being generated.
 * @param {string} simulationId
 * @returns {Promise} Returns config data with metadata and content.
 */
export const getSimulationConfigRealtime = (simulationId) => {
  return service.get(`/api/simulation/${simulationId}/config/realtime`)
}

/**
 * List simulations.
 * @param {string} projectId - Optional project ID filter
 */
export const listSimulations = (projectId) => {
  const params = projectId ? { project_id: projectId } : {}
  return service.get('/api/simulation/list', { params })
}

/**
 * Start a simulation.
 * @param {Object} data - { simulation_id, platform?, max_rounds?, enable_graph_memory_update? }
 */
export const startSimulation = (data) => {
  return requestWithRetry(() => service.post('/api/simulation/start', data), 3, 1000)
}

/**
 * Stop a simulation.
 * @param {Object} data - { simulation_id }
 */
export const stopSimulation = (data) => {
  return service.post('/api/simulation/stop', data)
}

/**
 * Fetch live simulation run status.
 * @param {string} simulationId
 */
export const getRunStatus = (simulationId) => {
  return service.get(`/api/simulation/${simulationId}/run-status`)
}

/**
 * Fetch detailed simulation run status, including recent actions.
 * @param {string} simulationId
 */
export const getRunStatusDetail = (simulationId) => {
  return service.get(`/api/simulation/${simulationId}/run-status/detail`)
}

/**
 * Fetch posts generated during a simulation.
 * @param {string} simulationId
 * @param {string} platform - 'reddit' | 'twitter'
 * @param {number} limit - Number of items to return
 * @param {number} offset - Offset
 */
export const getSimulationPosts = (simulationId, platform = 'reddit', limit = 50, offset = 0) => {
  return service.get(`/api/simulation/${simulationId}/posts`, {
    params: { platform, limit, offset }
  })
}

/**
 * Fetch the simulation timeline aggregated by round.
 * @param {string} simulationId
 * @param {number} startRound - Start round
 * @param {number} endRound - End round
 */
export const getSimulationTimeline = (simulationId, startRound = 0, endRound = null) => {
  const params = { start_round: startRound }
  if (endRound !== null) {
    params.end_round = endRound
  }
  return service.get(`/api/simulation/${simulationId}/timeline`, { params })
}

/**
 * Fetch agent statistics.
 * @param {string} simulationId
 */
export const getAgentStats = (simulationId) => {
  return service.get(`/api/simulation/${simulationId}/agent-stats`)
}

/**
 * Fetch simulation action history.
 * @param {string} simulationId
 * @param {Object} params - { limit, offset, platform, agent_id, round_num }
 */
export const getSimulationActions = (simulationId, params = {}) => {
  return service.get(`/api/simulation/${simulationId}/actions`, { params })
}

/**
 * Close the simulation environment gracefully.
 * @param {Object} data - { simulation_id, timeout? }
 */
export const closeSimulationEnv = (data) => {
  return service.post('/api/simulation/close-env', data)
}

/**
 * Fetch simulation environment status.
 * @param {Object} data - { simulation_id }
 */
export const getEnvStatus = (data) => {
  return service.post('/api/simulation/env-status', data)
}

/**
 * Interview multiple agents in batch.
 * @param {Object} data - { simulation_id, interviews: [{ agent_id, prompt }] }
 */
export const interviewAgents = (data) => {
  return requestWithRetry(() => service.post('/api/simulation/interview/batch', data), 3, 1000)
}

/**
 * Fetch historical simulations with project details.
 * Used by the home page history view.
 * @param {number} limit - Maximum number of items to return
 */
export const getSimulationHistory = (limit = 20) => {
  return service.get('/api/simulation/history', { params: { limit } })
}
