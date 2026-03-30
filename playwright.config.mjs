import { defineConfig } from '@playwright/test'

const backendPort = process.env.PLAYWRIGHT_BACKEND_PORT || '50141'
const frontendPort = process.env.PLAYWRIGHT_FRONTEND_PORT || '41731'
const backendBaseURL = process.env.PLAYWRIGHT_BACKEND_BASE_URL || `http://127.0.0.1:${backendPort}`
const baseURL = process.env.PLAYWRIGHT_BASE_URL || `http://127.0.0.1:${frontendPort}`

const backendEnv = {
  ...process.env,
  FLASK_HOST: '127.0.0.1',
  FLASK_PORT: backendPort,
  FLASK_DEBUG: 'false',
  LLM_API_KEY: process.env.LLM_API_KEY || 'smoke-local-key',
  ZEP_API_KEY: process.env.ZEP_API_KEY || 'smoke-local-key',
  PROBABILISTIC_PREPARE_ENABLED: 'true',
  PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED: 'true',
  PROBABILISTIC_REPORT_ENABLED: 'true',
  PROBABILISTIC_INTERACTION_ENABLED: 'false',
  CALIBRATED_PROBABILITY_ENABLED: 'false'
  ,
  UV_CACHE_DIR: '/tmp/mirofish-uv-cache'
}

const frontendEnv = {
  ...process.env,
  CI: process.env.CI || 'true',
  VITE_OPEN_BROWSER: 'false',
  VITE_API_BASE_URL: backendBaseURL
}

export default defineConfig({
  testDir: './tests/smoke',
  timeout: 30_000,
  expect: {
    timeout: 10_000
  },
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  reporter: [
    ['list'],
    ['html', { open: 'never', outputFolder: 'output/playwright/report' }]
  ],
  use: {
    baseURL,
    headless: true,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure'
  },
  webServer: [
    {
      command: "/bin/sh -c 'if command -v uv >/dev/null 2>&1; then cd backend && uv run python run.py; elif [ -x backend/.venv/bin/python ]; then backend/.venv/bin/python backend/run.py; else python3 backend/run.py; fi'",
      url: `${backendBaseURL}/api/simulation/prepare/capabilities`,
      env: backendEnv,
      reuseExistingServer: false,
      timeout: 120_000
    },
    {
      command: `npm --prefix frontend run dev -- --host 127.0.0.1 --port ${frontendPort}`,
      url: baseURL,
      env: frontendEnv,
      reuseExistingServer: false,
      timeout: 120_000
    }
  ]
})
