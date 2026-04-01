import test from 'node:test'
import assert from 'node:assert/strict'

import {
  extractErrorMessage,
  requestWithRetry,
  shouldRetryRequestError,
} from '../../src/api/index.js'

test('extractErrorMessage prefers backend payload details over generic transport text', () => {
  const error = {
    message: 'Request failed with status code 413',
    response: {
      status: 413,
      data: {
        error: 'Upload exceeds the 100 MB limit. Remove some files or split the upload into smaller batches.',
      },
    },
  }

  assert.equal(
    extractErrorMessage(error),
    'Upload exceeds the 100 MB limit. Remove some files or split the upload into smaller batches.',
  )
})

test('shouldRetryRequestError skips deterministic client failures such as upload-too-large', () => {
  assert.equal(
    shouldRetryRequestError({
      status: 413,
      message: 'Upload exceeds the 100 MB limit.',
    }),
    false,
  )
})

test('requestWithRetry does not retry non-retriable upload validation failures', async () => {
  let attempts = 0

  await assert.rejects(
    requestWithRetry(async () => {
      attempts += 1
      const error = new Error('Upload exceeds the 100 MB limit.')
      error.status = 413
      throw error
    }, 3, 1),
    /Upload exceeds the 100 MB limit/,
  )

  assert.equal(attempts, 1)
})

test('requestWithRetry retries transient server failures and eventually returns the result', async () => {
  let attempts = 0

  const result = await requestWithRetry(async () => {
    attempts += 1
    if (attempts < 3) {
      const error = new Error('Upstream provider unavailable')
      error.status = 503
      throw error
    }
    return { success: true }
  }, 3, 1)

  assert.deepEqual(result, { success: true })
  assert.equal(attempts, 3)
})
