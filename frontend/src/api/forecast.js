import service from './index'

export const getForecastCapabilities = () => {
  return service.get('/api/forecast/capabilities')
}

export const listForecastEvidenceProviders = () => {
  return service.get('/api/forecast/evidence-providers')
}

export const createForecastWorkspace = (data) => {
  return service.post('/api/forecast/workspaces', data)
}

export const createForecastQuestion = (data) => {
  return service.post('/api/forecast/questions', data)
}

export const listForecastQuestions = () => {
  return service.get('/api/forecast/questions')
}

export const getForecastQuestion = (forecastId) => {
  return service.get(`/api/forecast/questions/${forecastId}`)
}

export const updateForecastQuestion = (forecastId, data) => {
  return service.patch(`/api/forecast/questions/${forecastId}`, data)
}

export const resolveForecastQuestion = (forecastId, data) => {
  return service.post(`/api/forecast/questions/${forecastId}/resolve`, data)
}

export const getForecastLedger = (forecastId) => {
  return service.get(`/api/forecast/questions/${forecastId}/ledger`)
}

export const listForecastEvidenceBundles = (forecastId) => {
  return service.get(`/api/forecast/questions/${forecastId}/evidence-bundles`)
}

export const getForecastEvidenceBundle = (forecastId, bundleId) => {
  return service.get(`/api/forecast/questions/${forecastId}/evidence-bundles/${bundleId}`)
}

export const createForecastEvidenceBundle = (forecastId, data) => {
  return service.post(`/api/forecast/questions/${forecastId}/evidence-bundles`, data)
}

export const updateForecastEvidenceBundle = (forecastId, bundleId, data) => {
  return service.patch(`/api/forecast/questions/${forecastId}/evidence-bundles/${bundleId}`, data)
}

export const acquireForecastEvidenceBundle = (forecastId, bundleId, data) => {
  const suffix = bundleId ? `/${bundleId}` : ''
  return service.post(`/api/forecast/questions/${forecastId}/evidence-bundles${suffix}/acquire`, data)
}

export const issueForecastPrediction = (forecastId, data) => {
  return service.post(`/api/forecast/questions/${forecastId}/ledger/predictions`, data)
}

export const reviseForecastPrediction = (forecastId, predictionId, data) => {
  return service.post(`/api/forecast/questions/${forecastId}/ledger/predictions/${predictionId}/revisions`, data)
}

export const listForecastWorkspaces = () => {
  return service.get('/api/forecast/workspaces')
}

export const getForecastWorkspace = (forecastId) => {
  return service.get(`/api/forecast/workspaces/${forecastId}`)
}

export const registerForecastWorker = (forecastId, data) => {
  return service.post(`/api/forecast/workspaces/${forecastId}/workers`, data)
}

export const appendForecastPredictionEntry = (forecastId, data) => {
  return service.post(`/api/forecast/workspaces/${forecastId}/prediction-ledger/entries`, data)
}

export const appendForecastEvaluationCase = (forecastId, data) => {
  return service.post(`/api/forecast/workspaces/${forecastId}/evaluation-cases`, data)
}

export const appendForecastAnswer = (forecastId, data) => {
  return service.post(`/api/forecast/workspaces/${forecastId}/forecast-answers`, data)
}
