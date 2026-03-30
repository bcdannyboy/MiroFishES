import test from 'node:test'
import assert from 'node:assert/strict'

import baseConfig from '../../playwright.config.mjs'
import liveConfig from '../../playwright.live.config.mjs'

test('playwright live config reserves a longer timeout than smoke for live operator flows', () => {
  assert.equal(liveConfig.testDir, './tests/live')
  assert.ok(
    typeof liveConfig.timeout === 'number' && liveConfig.timeout >= 300_000,
    `expected live timeout >= 300000ms, received ${liveConfig.timeout}`
  )
  assert.ok(
    typeof baseConfig.timeout === 'number' && liveConfig.timeout > baseConfig.timeout,
    `expected live timeout > base timeout (${baseConfig.timeout}), received ${liveConfig.timeout}`
  )
})
