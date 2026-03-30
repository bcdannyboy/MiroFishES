import { defineConfig } from '@playwright/test'

import baseConfig from './playwright.config.mjs'

const liveWebServer = Array.isArray(baseConfig.webServer)
  ? baseConfig.webServer.map((entry, index) => {
      if (index !== 0) {
        return entry
      }
      return {
        ...entry,
        env: {
          ...entry.env,
          PROBABILISTIC_INTERACTION_ENABLED: 'true'
        }
      }
    })
  : baseConfig.webServer

export default defineConfig({
  ...baseConfig,
  testDir: './tests/live',
  // Live operator flows mutate real local artifacts and can legitimately take
  // longer than the fixture-backed smoke budget, especially while polling
  // report generation and replay surfaces.
  timeout: 360_000,
  webServer: liveWebServer
})
