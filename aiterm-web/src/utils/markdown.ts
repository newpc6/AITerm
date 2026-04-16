import DOMPurify from 'dompurify'
import { marked } from 'marked'

marked.setOptions({
  breaks: true,
  gfm: true,
})

export function renderMarkdown(content: string) {
  const source = content.trim()
  if (!source) {
    return ''
  }

  const html = marked.parse(source, { async: false })
  return DOMPurify.sanitize(html)
}
