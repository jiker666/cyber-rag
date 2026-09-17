/**
 * Markdown 渲染工具: markdown-it(html:false 默认转义, 防 XSS) + highlight.js 代码高亮。
 * 代码块输出统一结构: .code-block > .code-head(语言 + 复制按钮) + pre>code.hljs
 */
import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js/lib/core'
import java from 'highlight.js/lib/languages/java'
import python from 'highlight.js/lib/languages/python'
import javascript from 'highlight.js/lib/languages/javascript'
import typescript from 'highlight.js/lib/languages/typescript'
import xml from 'highlight.js/lib/languages/xml'
import json from 'highlight.js/lib/languages/json'
import bash from 'highlight.js/lib/languages/bash'
import shell from 'highlight.js/lib/languages/shell'
import sql from 'highlight.js/lib/languages/sql'
import yaml from 'highlight.js/lib/languages/yaml'
import ini from 'highlight.js/lib/languages/ini'
import plaintext from 'highlight.js/lib/languages/plaintext'
import 'highlight.js/styles/atom-one-dark.css'

hljs.registerLanguage('java', java)
hljs.registerLanguage('python', python)
hljs.registerLanguage('javascript', javascript)
hljs.registerLanguage('typescript', typescript)
hljs.registerLanguage('xml', xml)
hljs.registerLanguage('html', xml)
hljs.registerLanguage('json', json)
hljs.registerLanguage('bash', bash)
hljs.registerLanguage('sh', shell)
hljs.registerLanguage('shell', shell)
hljs.registerLanguage('sql', sql)
hljs.registerLanguage('yaml', yaml)
hljs.registerLanguage('yml', yaml)
hljs.registerLanguage('ini', ini)
hljs.registerLanguage('plaintext', plaintext)
hljs.registerLanguage('text', plaintext)

const md = new MarkdownIt({
  html: false, // 不信任原始 HTML, 模型输出中的标签一律转义
  linkify: true,
  breaks: true,
})

// 链接一律新窗口打开并加 noopener
const defaultLink =
  md.renderer.rules.link_open ||
  ((tokens, idx, options, _, self) => self.renderToken(tokens, idx, options))
md.renderer.rules.link_open = (tokens, idx, options, env, self) => {
  const token = tokens[idx]
  token.attrSet('target', '_blank')
  token.attrSet('rel', 'noopener noreferrer')
  return defaultLink(tokens, idx, options, env, self)
}

// 代码块: 带语言标签与复制按钮的容器
md.renderer.rules.fence = (tokens, idx) => {
  const token = tokens[idx]
  const lang = (token.info || '').trim().split(/\s+/)[0].toLowerCase()
  const highlighted =
    lang && hljs.getLanguage(lang)
      ? hljs.highlight(token.content, { language: lang, ignoreIllegals: true }).value
      : md.utils.escapeHtml(token.content)
  const label = lang && hljs.getLanguage(lang) ? lang : 'text'
  return `<div class="code-block"><div class="code-head"><span class="code-lang">${label}</span><button class="code-copy" type="button">复制</button></div><pre><code class="hljs">${highlighted}</code></pre></div>`
}

export function renderMarkdown(source: string): string {
  return md.render(source ?? '')
}
