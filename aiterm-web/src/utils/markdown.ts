import DOMPurify from 'dompurify'
import MarkdownIt from 'markdown-it'

const markdown = new MarkdownIt({
  breaks: true,
  html: false,
  linkify: true,
})

function normalizeMarkdown(source: string) {
  let value = source.replace(/\r\n/g, '\n')

  value = value.replace(/(^|\n)(#{1,6})(\S)/g, '$1$2 $3')

  value = value.replace(/([。！？.!?])\s*(#{2,6})\s*/g, '$1\n\n$2 ')

  value = value.replace(/([。！？.!?])\s*([-*+]\s+)/g, '$1\n\n$2')
  value = value.replace(/([。！？.!?])\s*(\d+\.\s+)/g, '$1\n\n$2')
  value = value.replace(/([。！？.!?])\s*(\|)/g, '$1\n\n$2')

  return value
}

export function renderMarkdown(content: string) {
  const source = normalizeMarkdown(content.trim())
  if (!source) {
    return ''
  }

  const html = markdown.render(source)
  return DOMPurify.sanitize(html, {
    ADD_TAGS: ['table', 'thead', 'tbody', 'tr', 'th', 'td'],
  })
}
