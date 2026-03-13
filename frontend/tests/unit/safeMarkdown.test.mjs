import test from 'node:test'
import assert from 'node:assert/strict'

const loadSafeMarkdownModule = async () => {
  try {
    return await import('../../src/utils/safeMarkdown.js')
  } catch (error) {
    assert.fail(`safeMarkdown utility is missing: ${error.message}`)
  }
}

test('renderSafeMarkdown escapes raw HTML while preserving the limited markdown subset', async () => {
  const { renderSafeMarkdown } = await loadSafeMarkdownModule()

  assert.equal(typeof renderSafeMarkdown, 'function')

  const html = renderSafeMarkdown([
    '## Section heading',
    '<script>alert("xss")</script>',
    '',
    '**Bold** `code`',
    '- item one',
    '- item two'
  ].join('\n'))

  assert.equal(html.includes('<script>'), false)
  assert.equal(html.includes('&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;'), true)
  assert.equal(html.includes('<strong>Bold</strong>'), true)
  assert.equal(html.includes('<code class="inline-code">code</code>'), true)
  assert.equal(html.includes('<ul class="md-ul">'), true)
})

test('renderSafeInlineMarkdown escapes HTML and keeps inline formatting readable', async () => {
  const { renderSafeInlineMarkdown } = await loadSafeMarkdownModule()

  assert.equal(typeof renderSafeInlineMarkdown, 'function')

  const html = renderSafeInlineMarkdown('Hello <img src=x onerror=1>\n**safe**')

  assert.equal(html.includes('<img'), false)
  assert.equal(html.includes('&lt;img src=x onerror=1&gt;'), true)
  assert.equal(html.includes('<br>'), true)
  assert.equal(html.includes('<strong>safe</strong>'), true)
})
