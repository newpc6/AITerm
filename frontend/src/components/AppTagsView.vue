<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const props = defineProps<{
  tabs: { path: string; label: string }[]
}>()

const emit = defineEmits<{
  close: [path: string]
  closeOthers: [path: string]
  closeAll: []
  closeLeft: [path: string]
  closeRight: [path: string]
}>()

const route = useRoute()
const router = useRouter()

const fixedTabs = ['/chat']

function isFixed(path: string) {
  return fixedTabs.includes(path)
}

function isActive(path: string) {
  return route.path === path || route.path.startsWith(path + '/')
}

function handleClick(path: string) {
  router.push(path)
}

function handleContextMenu(event: MouseEvent, path: string) {
  event.preventDefault()
  if (isFixed(path)) return

  const items: { label: string; action: () => void; divided?: boolean }[] = [
    { label: '关闭当前', action: () => emit('close', path) },
    { label: '关闭其他', action: () => emit('closeOthers', path) },
    { label: '关闭全部', action: () => emit('closeAll'), divided: true },
    { label: '关闭左侧', action: () => emit('closeLeft', path) },
    { label: '关闭右侧', action: () => emit('closeRight', path) },
  ]

  const menu = document.createElement('div')
  menu.className = 'tagsview-context-menu'
  menu.style.cssText = `position:fixed;left:${event.clientX}px;top:${event.clientY}px;z-index:9999;background:var(--color-bg-card);border:1px solid var(--color-border-primary);border-radius:8px;padding:4px 0;min-width:120px;box-shadow:0 4px 16px rgba(0,0,0,0.3);`

  const closeMenu = () => {
    menu.remove()
    document.removeEventListener('click', closeMenu)
  }

  items.forEach(item => {
    const el = document.createElement('div')
    el.textContent = item.label
    el.style.cssText = `padding:6px 16px;font-size:13px;cursor:pointer;color:var(--color-text-secondary);${item.divided ? 'border-top:1px solid var(--color-border-primary);margin-top:4px;padding-top:10px;' : ''}`
    el.onmouseenter = () => { el.style.background = 'var(--color-bg-card-hover)' }
    el.onmouseleave = () => { el.style.background = 'transparent' }
    el.onclick = () => { item.action(); closeMenu() }
    menu.appendChild(el)
  })

  document.body.appendChild(menu)
  setTimeout(() => document.addEventListener('click', closeMenu), 0)
}

function handleClose(path: string) {
  if (!isFixed(path)) {
    emit('close', path)
  }
}
</script>

<template>
  <div v-if="tabs.length > 0" class="tagsview">
    <div
      v-for="tab in tabs"
      :key="tab.path"
      class="tagsview__tab"
      :class="{ 'is-active': isActive(tab.path), 'is-fixed': isFixed(tab.path) }"
      @click="handleClick(tab.path)"
      @contextmenu="(e: MouseEvent) => handleContextMenu(e, tab.path)"
    >
      <span class="tagsview__tab-label">{{ tab.label }}</span>
      <span
        v-if="!isFixed(tab.path)"
        class="tagsview__tab-close"
        @click.stop="handleClose(tab.path)"
      >×</span>
    </div>
  </div>
</template>

<style scoped>
.tagsview {
  display: flex;
  align-items: center;
  height: 36px;
  padding: 0 8px;
  background: var(--color-bg-secondary);
  border-bottom: 1px solid var(--color-border-primary);
  overflow-x: auto;
  flex-shrink: 0;
  gap: 4px;
}

.tagsview::-webkit-scrollbar {
  height: 2px;
}

.tagsview::-webkit-scrollbar-thumb {
  background: var(--color-border-primary);
  border-radius: 2px;
}

.tagsview__tab {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 28px;
  padding: 0 10px;
  border-radius: 6px;
  font-size: 12px;
  color: var(--color-text-muted);
  background: transparent;
  cursor: pointer;
  white-space: nowrap;
  transition: all var(--transition-fast);
  border: 1px solid transparent;
  user-select: none;
}

.tagsview__tab:hover {
  color: var(--color-text-secondary);
  background: var(--color-bg-card);
}

.tagsview__tab.is-active {
  color: var(--color-text-primary);
  background: var(--color-bg-card);
  border-color: var(--color-border-primary);
}

.tagsview__tab-label {
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.tagsview__tab-close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border-radius: 4px;
  font-size: 14px;
  line-height: 1;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.tagsview__tab-close:hover {
  background: var(--color-danger-bg);
  color: var(--color-danger);
}
</style>
