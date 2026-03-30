import test from 'node:test'
import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

const viteConfigUrl = pathToFileURL(
  path.resolve(__dirname, '..', '..', 'vite.config.js')
).href

const loadConfig = async () => {
  const imported = await import(`${viteConfigUrl}?t=${Date.now()}-${Math.random()}`)
  return imported.default
}

test('vite dev proxy follows VITE_API_BASE_URL when provided', async () => {
  const previous = process.env.VITE_API_BASE_URL
  process.env.VITE_API_BASE_URL = 'http://127.0.0.1:50141'

  try {
    const config = await loadConfig()
    assert.equal(config.server.proxy['/api'].target, 'http://127.0.0.1:50141')
  } finally {
    if (previous === undefined) {
      delete process.env.VITE_API_BASE_URL
    } else {
      process.env.VITE_API_BASE_URL = previous
    }
  }
})
