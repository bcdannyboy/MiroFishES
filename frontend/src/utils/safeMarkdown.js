const escapeHtml = (content = '') => (
  String(content)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
)

const stashTokens = (content, regex, formatter, prefix) => {
  const tokens = []
  const safePrefix = String(prefix).replace(/[^A-Za-z0-9]/g, '')

  const replacedContent = content.replace(regex, (...args) => {
    const token = `ZZ${safePrefix}${tokens.length}ZZ`
    tokens.push(formatter(...args))
    return token
  })

  return {
    content: replacedContent,
    tokens,
    prefix: safePrefix
  }
}

const restoreTokens = (content, tokens, prefix) => (
  tokens.reduce(
    (restoredContent, tokenValue, index) => (
      restoredContent.replaceAll(`ZZ${prefix}${index}ZZ`, tokenValue)
    ),
    content
  )
)

const applyInlineFormatting = (content) => {
  let formattedContent = content.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  formattedContent = formattedContent.replace(/\*(.+?)\*/g, '<em>$1</em>')
  formattedContent = formattedContent.replace(/_(.+?)_/g, '<em>$1</em>')
  return formattedContent
}

export const renderSafeInlineMarkdown = (content = '') => {
  if (!content) {
    return ''
  }

  const escapedContent = escapeHtml(content)
  const inlineCode = stashTokens(
    escapedContent,
    /`([^`]+)`/g,
    (_match, codeContent) => `<code class="inline-code">${codeContent}</code>`,
    'SAFE_INLINE_CODE'
  )

  let html = applyInlineFormatting(inlineCode.content)
  html = restoreTokens(html, inlineCode.tokens, inlineCode.prefix)
  html = html.replace(/\n/g, '<br>')
  return html
}

export const renderSafeMarkdown = (content = '') => {
  if (!content) {
    return ''
  }

  let processedContent = escapeHtml(content).replace(/^##\s+.+\n+/, '')

  const codeBlocks = stashTokens(
    processedContent,
    /```(\w*)\n([\s\S]*?)```/g,
    (_match, _language, codeContent) => (
      `<pre class="code-block"><code>${codeContent}</code></pre>`
    ),
    'SAFE_BLOCK_CODE'
  )

  const inlineCode = stashTokens(
    codeBlocks.content,
    /`([^`]+)`/g,
    (_match, codeContent) => `<code class="inline-code">${codeContent}</code>`,
    'SAFE_INLINE_CODE'
  )

  let html = inlineCode.content
  html = html.replace(/^#### (.+)$/gm, '<h5 class="md-h5">$1</h5>')
  html = html.replace(/^### (.+)$/gm, '<h4 class="md-h4">$1</h4>')
  html = html.replace(/^## (.+)$/gm, '<h3 class="md-h3">$1</h3>')
  html = html.replace(/^# (.+)$/gm, '<h2 class="md-h2">$1</h2>')
  html = html.replace(/^> (.+)$/gm, '<blockquote class="md-quote">$1</blockquote>')

  html = html.replace(/^(\s*)- (.+)$/gm, (_match, indent, text) => {
    const level = Math.floor(indent.length / 2)
    return `<li class="md-li" data-level="${level}">${text}</li>`
  })
  html = html.replace(/^(\s*)(\d+)\. (.+)$/gm, (_match, indent, _num, text) => {
    const level = Math.floor(indent.length / 2)
    return `<li class="md-oli" data-level="${level}">${text}</li>`
  })

  html = html.replace(/(<li class="md-li"[^>]*>.*?<\/li>\s*)+/g, '<ul class="md-ul">$&</ul>')
  html = html.replace(/(<li class="md-oli"[^>]*>.*?<\/li>\s*)+/g, '<ol class="md-ol">$&</ol>')
  html = html.replace(/<\/li>\s+<li/g, '</li><li')
  html = html.replace(/<ul class="md-ul">\s+/g, '<ul class="md-ul">')
  html = html.replace(/<ol class="md-ol">\s+/g, '<ol class="md-ol">')
  html = html.replace(/\s+<\/ul>/g, '</ul>')
  html = html.replace(/\s+<\/ol>/g, '</ol>')
  html = applyInlineFormatting(html)
  html = html.replace(/^---$/gm, '<hr class="md-hr">')
  html = html.replace(/\n\n/g, '</p><p class="md-p">')
  html = html.replace(/\n/g, '<br>')
  html = `<p class="md-p">${html}</p>`

  html = restoreTokens(html, inlineCode.tokens, inlineCode.prefix)
  html = restoreTokens(html, codeBlocks.tokens, codeBlocks.prefix)

  html = html.replace(/<p class="md-p"><\/p>/g, '')
  html = html.replace(/<p class="md-p">(<h[2-5])/g, '$1')
  html = html.replace(/(<\/h[2-5]>)<\/p>/g, '$1')
  html = html.replace(/<p class="md-p">(<ul|<ol|<blockquote|<pre|<hr)/g, '$1')
  html = html.replace(/(<\/ul>|<\/ol>|<\/blockquote>|<\/pre>)<\/p>/g, '$1')
  html = html.replace(/<br>\s*(<ul|<ol|<blockquote)/g, '$1')
  html = html.replace(/(<\/ul>|<\/ol>|<\/blockquote>)\s*<br>/g, '$1')
  html = html.replace(/<p class="md-p">(<br>\s*)+(<ul|<ol|<blockquote|<pre|<hr)/g, '$2')
  html = html.replace(/(<br>\s*){2,}/g, '<br>')
  html = html.replace(/(<\/ol>|<\/ul>|<\/blockquote>)<br>(<p|<div)/g, '$1$2')

  const tokens = html.split(/(<ol class="md-ol">(?:<li class="md-oli"[^>]*>[\s\S]*?<\/li>)+<\/ol>)/g)
  let olCounter = 0
  let inSequence = false
  for (let i = 0; i < tokens.length; i++) {
    if (tokens[i].startsWith('<ol class="md-ol">')) {
      const liCount = (tokens[i].match(/<li class="md-oli"/g) || []).length
      if (liCount === 1) {
        olCounter++
        if (olCounter > 1) {
          tokens[i] = tokens[i].replace('<ol class="md-ol">', `<ol class="md-ol" start="${olCounter}">`)
        }
        inSequence = true
      } else {
        olCounter = 0
        inSequence = false
      }
    } else if (inSequence && /<h[2-5]/.test(tokens[i])) {
      olCounter = 0
      inSequence = false
    }
  }

  return tokens.join('')
}
