import axios from 'axios'

const viteEnv = typeof import.meta !== 'undefined' && import.meta.env
  ? import.meta.env
  : {}

// Create the axios instance
const service = axios.create({
  baseURL: viteEnv.VITE_API_BASE_URL || 'http://localhost:5001',
  timeout: 300000, // 5 minute timeout; ontology generation can take a while
  headers: {
    'Content-Type': 'application/json'
  }
})

export const extractErrorMessage = (error) => (
  error?.response?.data?.error
  || error?.response?.data?.message
  || error?.message
  || 'Request failed'
)

export const shouldRetryRequestError = (error) => {
  const status = error?.status ?? error?.response?.status

  if (axios.isCancel(error) || error?.code === 'ERR_CANCELED') {
    return false
  }

  if (error?.code === 'ECONNABORTED' || error?.message === 'Network Error') {
    return true
  }

  if (status == null) {
    return true
  }

  return [408, 409, 425, 429, 500, 502, 503, 504].includes(status)
}

// Request interceptor
service.interceptors.request.use(
  config => {
    return config
  },
  error => {
    console.error('Request error:', error)
    return Promise.reject(error)
  }
)

// Response interceptor with fault-tolerant retry handling
service.interceptors.response.use(
  response => {
    const res = response.data
    
    // Throw if the API explicitly reports failure
    if (!res.success && res.success !== undefined) {
      console.error('API Error:', res.error || res.message || 'Unknown error')
      return Promise.reject(new Error(res.error || res.message || 'Error'))
    }
    
    return res
  },
  error => {
    console.error('Response error:', error)
    
    // Handle timeouts
    if (error.code === 'ECONNABORTED' && error.message.includes('timeout')) {
      console.error('Request timeout')
    }
    
    // Handle network errors
    if (error.message === 'Network Error') {
      console.error('Network error - please check your connection')
    }

    const wrappedError = new Error(extractErrorMessage(error))
    wrappedError.status = error?.response?.status
    wrappedError.responseData = error?.response?.data
    wrappedError.cause = error

    return Promise.reject(wrappedError)
  }
)

// Request helper with retries
export const requestWithRetry = async (requestFn, maxRetries = 3, delay = 1000) => {
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await requestFn()
    } catch (error) {
      if (axios.isCancel(error) || error?.code === 'ERR_CANCELED') {
        throw error
      }

      if (i === maxRetries - 1 || !shouldRetryRequestError(error)) throw error
      
      console.warn(`Request failed, retrying (${i + 1}/${maxRetries})...`)
      await new Promise(resolve => setTimeout(resolve, delay * Math.pow(2, i)))
    }
  }
}

export const isRequestCanceled = (error) => (
  axios.isCancel(error)
  || error?.code === 'ERR_CANCELED'
  || error?.name === 'CanceledError'
)

export default service
