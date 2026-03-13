import service, { requestWithRetry } from './index'

/**
 * Generate ontology data from uploaded documents and the simulation requirement.
 * @param {Object} data - Includes files, simulation_requirement, project_name, etc.
 * @returns {Promise}
 */
export function generateOntology(formData) {
  return requestWithRetry(() => 
    service({
      url: '/api/graph/ontology/generate',
      method: 'post',
      data: formData,
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
  )
}

/**
 * Build the graph.
 * @param {Object} data - Includes project_id, graph_name, etc.
 * @returns {Promise}
 */
export function buildGraph(data) {
  return requestWithRetry(() =>
    service({
      url: '/api/graph/build',
      method: 'post',
      data
    })
  )
}

/**
 * Query task status.
 * @param {String} taskId - Task ID
 * @returns {Promise}
 */
export function getTaskStatus(taskId) {
  return service({
    url: `/api/graph/task/${taskId}`,
    method: 'get'
  })
}

/**
 * Fetch graph data.
 * @param {String} graphId - Graph ID
 * @param {Object} options - { mode?, maxNodes?, maxEdges?, signal? }
 * @returns {Promise}
 */
export function getGraphData(graphId, options = {}) {
  const params = {}

  if (typeof options.mode === 'string' && options.mode.trim()) {
    params.mode = options.mode.trim()
  }
  if (Number.isInteger(options.maxNodes) && options.maxNodes > 0) {
    params.max_nodes = options.maxNodes
  }
  if (Number.isInteger(options.maxEdges) && options.maxEdges > 0) {
    params.max_edges = options.maxEdges
  }

  return service({
    url: `/api/graph/data/${graphId}`,
    method: 'get',
    params: Object.keys(params).length ? params : undefined,
    signal: options.signal
  })
}

/**
 * Fetch project information.
 * @param {String} projectId - Project ID
 * @returns {Promise}
 */
export function getProject(projectId) {
  return service({
    url: `/api/graph/project/${projectId}`,
    method: 'get'
  })
}
