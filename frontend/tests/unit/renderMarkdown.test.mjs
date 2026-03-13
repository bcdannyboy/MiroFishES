import test from 'node:test'
import assert from 'node:assert/strict'

import { renderSafeMarkdown } from '../../src/utils/safeMarkdown.js'

test('renderSafeMarkdown escapes raw HTML while preserving limited markdown formatting', () => {
  const rendered = renderSafeMarkdown('Hello <script>alert(1)</script> **world**')

  assert.match(rendered, /&lt;script&gt;alert\(1\)&lt;\/script&gt;/)
  assert.doesNotMatch(rendered, /<script>alert\(1\)<\/script>/)
  assert.match(rendered, /<strong>world<\/strong>/)
})

test('renderSafeMarkdown keeps code blocks escaped instead of executable', () => {
  const rendered = renderSafeMarkdown('```html\n<div onclick="boom()">unsafe</div>\n```')

  assert.match(rendered, /<pre class="code-block"><code>&lt;div onclick=&quot;boom\(\)&quot;&gt;unsafe&lt;\/div&gt;\n?<\/code><\/pre>/)
  assert.doesNotMatch(rendered, /<div onclick="boom\(\)">unsafe<\/div>/)
})
