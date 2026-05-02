<script setup lang="ts">
import { ref, onMounted, watch, shallowRef } from 'vue'
import { EditorView, keymap, lineNumbers, highlightActiveLine, highlightActiveLineGutter, drawSelection, dropCursor, rectangularSelection, crosshairCursor } from '@codemirror/view'
import { EditorState, Compartment } from '@codemirror/state'
import { python } from '@codemirror/lang-python'
import { defaultKeymap, history, historyKeymap, indentWithTab, undo, redo } from '@codemirror/commands'
import { bracketMatching, indentOnInput, foldGutter } from '@codemirror/language'
import { highlightSelectionMatches } from '@codemirror/search'
import { defaultHighlightStyle, syntaxHighlighting, HighlightStyle } from '@codemirror/language'
import { tags } from '@lezer/highlight'

const props = defineProps<{
  modelValue: string
  readonly?: boolean
  placeholder?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const editorContainer = ref<HTMLElement | null>(null)
const editorView = shallowRef<EditorView | null>(null)
const readOnlyConfig = new Compartment()

const draculaTheme = EditorView.theme({
  '&': {
    backgroundColor: '#282a36',
    color: '#f8f8f2',
    height: '100%'
  },
  '.cm-content': {
    caretColor: '#f8f8f2',
    fontFamily: "'JetBrains Mono', 'Fira Code', 'Consolas', 'Monaco', monospace",
    fontSize: '14px',
    lineHeight: '1.6',
    padding: '12px 0'
  },
  '.cm-cursor': {
    borderLeftColor: '#f8f8f2'
  },
  '.cm-selectionBackground, &.cm-focused .cm-selectionBackground': {
    backgroundColor: '#bd93f940'
  },
  '.cm-activeLine': {
    backgroundColor: '#44475a'
  },
  '.cm-activeLineGutter': {
    backgroundColor: '#44475a'
  },
  '.cm-gutters': {
    backgroundColor: '#21222c',
    color: '#6272a4',
    border: 'none',
    borderRight: '1px solid #44475a'
  },
  '.cm-lineNumbers .cm-gutterElement': {
    padding: '0 12px 0 8px',
    minWidth: '40px'
  },
  '.cm-foldGutter': {
    width: '12px'
  },
  '.cm-foldPlaceholder': {
    backgroundColor: '#44475a',
    color: '#f8f8f2',
    border: 'none'
  },
  '.cm-scroller::-webkit-scrollbar': {
    width: '8px',
    height: '8px'
  },
  '.cm-scroller::-webkit-scrollbar-track': {
    background: '#21222c'
  },
  '.cm-scroller::-webkit-scrollbar-thumb': {
    background: '#44475a',
    borderRadius: '4px'
  },
  '.cm-scroller::-webkit-scrollbar-thumb:hover': {
    background: '#6272a4'
  }
}, { dark: true })

const draculaHighlightStyle = HighlightStyle.define([
  { tag: tags.keyword, color: '#ff79c6' },
  { tag: [tags.name, tags.deleted, tags.character, tags.propertyName, tags.macroName], color: '#50fa7b' },
  { tag: [tags.variableName], color: '#f8f8f2' },
  { tag: [tags.function(tags.variableName)], color: '#50fa7b' },
  { tag: [tags.labelName], color: '#8be9fd' },
  { tag: [tags.color, tags.constant(tags.name), tags.standard(tags.name)], color: '#bd93f9' },
  { tag: [tags.definition(tags.name), tags.separator], color: '#f8f8f2' },
  { tag: [tags.className], color: '#8be9fd' },
  { tag: [tags.number, tags.changed, tags.annotation, tags.modifier, tags.self, tags.namespace], color: '#bd93f9' },
  { tag: [tags.typeName], color: '#8be9fd', fontStyle: 'italic' },
  { tag: [tags.operator, tags.operatorKeyword, tags.url, tags.escape, tags.regexp, tags.link, tags.special(tags.string)], color: '#ff79c6' },
  { tag: [tags.meta, tags.comment], color: '#6272a4', fontStyle: 'italic' },
  { tag: tags.strong, fontWeight: 'bold', color: '#ffb86c' },
  { tag: tags.emphasis, fontStyle: 'italic', color: '#f1fa8c' },
  { tag: tags.strikethrough, textDecoration: 'line-through' },
  { tag: tags.heading, fontWeight: 'bold', color: '#bd93f9' },
  { tag: [tags.atom, tags.bool, tags.special(tags.variableName)], color: '#bd93f9' },
  { tag: [tags.processingInstruction, tags.string, tags.inserted], color: '#f1fa8c' },
  { tag: tags.invalid, color: '#ff5555', background: '#ff555520' }
])

function handleUndo() {
  if (editorView.value) {
    undo(editorView.value)
  }
}

function handleRedo() {
  if (editorView.value) {
    redo(editorView.value)
  }
}

function handleClear() {
  if (editorView.value) {
    editorView.value.dispatch({
      changes: {
        from: 0,
        to: editorView.value.state.doc.length,
        insert: ''
      }
    })
  }
}

function handleFormat() {
  if (editorView.value) {
    const doc = editorView.value.state.doc.toString()
    try {
      const formatted = formatPythonCode(doc)
      editorView.value.dispatch({
        changes: {
          from: 0,
          to: editorView.value.state.doc.length,
          insert: formatted
        }
      })
    } catch {
      // ignore format errors
    }
  }
}

function formatPythonCode(code: string): string {
  const lines = code.split('\n')
  const formatted: string[] = []
  let indentLevel = 0

  for (let line of lines) {
    const trimmed = line.trim()
    if (!trimmed) {
      formatted.push('')
      continue
    }

    if (trimmed.endsWith(':') && (trimmed.startsWith('def ') || trimmed.startsWith('class ') || trimmed.startsWith('if ') || trimmed.startsWith('elif ') || trimmed.startsWith('else') || trimmed.startsWith('for ') || trimmed.startsWith('while ') || trimmed.startsWith('try') || trimmed.startsWith('except') || trimmed.startsWith('with '))) {
      formatted.push('    '.repeat(indentLevel) + trimmed)
      indentLevel++
    } else if (trimmed.startsWith('return ') || trimmed.startsWith('break') || trimmed.startsWith('continue') || trimmed.startsWith('pass') || trimmed.startsWith('raise ')) {
      if (indentLevel > 0) {
        formatted.push('    '.repeat(indentLevel) + trimmed)
      } else {
        formatted.push(trimmed)
      }
    } else {
      formatted.push('    '.repeat(indentLevel) + trimmed)
    }
  }

  return formatted.join('\n')
}

onMounted(() => {
  if (!editorContainer.value) return

  const updateListener = EditorView.updateListener.of((update) => {
    if (update.docChanged) {
      const newValue = update.state.doc.toString()
      emit('update:modelValue', newValue)
    }
  })

  const state = EditorState.create({
    doc: props.modelValue,
    extensions: [
      lineNumbers(),
      highlightActiveLine(),
      highlightActiveLineGutter(),
      foldGutter(),
      drawSelection(),
      dropCursor(),
      bracketMatching(),
      indentOnInput(),
      rectangularSelection(),
      crosshairCursor(),
      highlightSelectionMatches(),
      history(),
      python(),
      syntaxHighlighting(draculaHighlightStyle, { fallback: true }),
      keymap.of([...defaultKeymap, ...historyKeymap, indentWithTab]),
      draculaTheme,
      updateListener,
      EditorView.lineWrapping,
      EditorState.tabSize.of(4),
      readOnlyConfig.of(EditorState.readOnly.of(props.readonly || false))
    ]
  })

  editorView.value = new EditorView({
    state,
    parent: editorContainer.value
  })
})

watch(() => props.modelValue, (newValue) => {
  if (editorView.value && editorView.value.state.doc.toString() !== newValue) {
    editorView.value.dispatch({
      changes: {
        from: 0,
        to: editorView.value.state.doc.length,
        insert: newValue
      }
    })
  }
})

watch(() => props.readonly, (readonly) => {
  if (editorView.value) {
    editorView.value.dispatch({
      effects: readOnlyConfig.reconfigure(EditorState.readOnly.of(readonly || false))
    })
  }
})
</script>

<template>
  <div class="code-editor-wrapper">
    <div class="code-editor-toolbar" @click.stop>
      <div class="toolbar-left">
        <span class="toolbar-title">Python</span>
      </div>
      <div class="toolbar-right">
        <button class="toolbar-btn" @click.stop="handleFormat" title="格式化代码">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
            <path d="M3 21h18v-2H3v2zm0-4h18v-2H3v2zm0-4h18v-2H3v2zm0-4h18V7H3v2zm0-6v2h18V3H3z" />
          </svg>
        </button>
        <button class="toolbar-btn" @click.stop="handleUndo" title="撤销">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
            <path
              d="M12.5 8c-2.65 0-5.05.99-6.9 2.6L2 7v9h9l-3.62-3.62c1.39-1.16 3.16-1.88 5.12-1.88 3.54 0 6.55 2.31 7.6 5.5l2.37-.78C21.08 11.03 17.15 8 12.5 8z" />
          </svg>
        </button>
        <button class="toolbar-btn" @click.stop="handleRedo" title="重做">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
            <path
              d="M18.4 10.6C16.55 8.99 14.15 8 11.5 8c-4.65 0-8.58 3.03-9.96 7.22L3.9 16c1.05-3.19 4.05-5.5 7.6-5.5 1.95 0 3.73.72 5.12 1.88L13 16h9V7l-3.6 3.6z" />
          </svg>
        </button>
        <button class="toolbar-btn" @click.stop="handleClear" title="清空">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
            <path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z" />
          </svg>
        </button>
      </div>
    </div>
    <div ref="editorContainer" class="code-editor"></div>
  </div>
</template>

<style scoped>
.code-editor-wrapper {
  width: 100%;
  height: 100%;
  min-height: 200px;
  border: 1px solid #44475a;
  border-radius: 8px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.code-editor-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 12px;
  background: #21222c;
  border-bottom: 1px solid #44475a;
  flex-shrink: 0;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.toolbar-title {
  font-size: 12px;
  color: #6272a4;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 4px;
}

.toolbar-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  color: #6272a4;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.toolbar-btn:hover {
  background: #44475a;
  color: #f8f8f2;
}

.code-editor {
  width: 100%;
  flex: 1;
  min-height: 200px;
}

.code-editor :deep(.cm-editor) {
  height: 100%;
}

.code-editor :deep(.cm-scroller) {
  overflow: auto;
}
</style>
