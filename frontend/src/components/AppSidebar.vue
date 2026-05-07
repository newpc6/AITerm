<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ChatDotRound, Cpu, Clock, Monitor, Share,
  Folder, UserFilled, MagicStick, Timer, Setting,
  Tools, Box, Tickets, Lock,
  List, Files, DataBoard, SetUp
} from '@element-plus/icons-vue'

defineProps<{
  isAdmin: boolean
}>()

const route = useRoute()
const router = useRouter()

const collapsed = ref(false)

interface MenuItem {
  path: string
  label: string
  icon: unknown
  adminOnly?: boolean
}

interface MenuGroup {
  key: string
  label: string
  icon: unknown
  items: MenuItem[]
}

const menuGroups: MenuGroup[] = [
  {
    key: 'ai-chat',
    label: 'AI 对话',
    icon: ChatDotRound,
    items: [
      { path: '/chat', label: '对话', icon: ChatDotRound },
      { path: '/agents/workbench', label: '智能体工作台', icon: Cpu },
      { path: '/history', label: '历史', icon: Clock },
      { path: '/terminal', label: '终端', icon: Monitor },
      { path: '/shares', label: '分享管理', icon: Share },
    ]
  },
  {
    key: 'workspace',
    label: '工作空间',
    icon: Folder,
    items: [
      { path: '/workspace/files', label: '文件浏览', icon: Files },
      { path: '/workspace/agents', label: '智能体管理', icon: UserFilled },
      { path: '/workspace/skills', label: '技能', icon: MagicStick },
      { path: '/workspace/scheduler', label: '定时任务', icon: Timer },
      { path: '/workspace/models', label: '模型配置', icon: Setting },
    ]
  },
  {
    key: 'tools',
    label: '工具',
    icon: Tools,
    items: [
      { path: '/tools/library', label: '工具库', icon: Box, adminOnly: true },
      { path: '/tools/my', label: '我的工具', icon: Tools },
    ]
  },
  {
    key: 'org',
    label: '组织管理',
    icon: DataBoard,
    items: [
      { path: '/system/users', label: '用户管理', icon: UserFilled, adminOnly: true },
      { path: '/system/teams', label: '团队管理', icon: Tickets, adminOnly: true },
    ]
  },
  {
    key: 'system',
    label: '系统管理',
    icon: SetUp,
    items: [
      { path: '/system/nodes', label: '节点管理', icon: Monitor, adminOnly: true },
      { path: '/system/sandbox', label: '沙盒配置', icon: Lock, adminOnly: true },
      { path: '/system/settings', label: '全局配置', icon: Setting, adminOnly: true },
    ]
  },
]

const expandedGroup = ref<string>('ai-chat')

function toggleGroup(key: string) {
  expandedGroup.value = expandedGroup.value === key ? '' : key
}

function isActive(path: string) {
  return route.path === path || route.path.startsWith(path + '/')
}

function isGroupActive(items: MenuItem[]) {
  return items.some(item => isActive(item.path))
}

function visibleItems(items: MenuItem[]) {
  return items.filter(item => !item.adminOnly || true)
}

function navigate(path: string) {
  router.push(path)
}
</script>

<template>
  <aside class="sidebar" :class="{ 'sidebar--collapsed': collapsed }">
    <div class="sidebar__toggle" @click="collapsed = !collapsed">
      <svg viewBox="0 0 24 24" fill="currentColor" width="18" height="18">
        <path v-if="collapsed" d="M10 6l6 6-6 6z"/>
        <path v-else d="M14 6l-6 6 6 6z"/>
      </svg>
    </div>

    <div v-for="group in menuGroups" :key="group.key" class="sidebar__group">
      <div
        class="sidebar__group-title"
        :class="{ 'is-expanded': expandedGroup === group.key }"
        @click="toggleGroup(group.key)"
      >
        <component :is="group.icon" class="sidebar__group-icon" />
        <span v-show="!collapsed" class="sidebar__group-label">{{ group.label }}</span>
        <svg v-show="!collapsed" class="sidebar__group-arrow" :class="{ 'is-rotated': expandedGroup === group.key }" viewBox="0 0 24 24" fill="currentColor" width="14" height="14">
          <path d="M7 10l5 5 5-5z"/>
        </svg>
      </div>

      <Transition name="sidebar-collapse">
        <div v-show="expandedGroup === group.key && !collapsed" class="sidebar__group-items">
          <div
            v-for="item in visibleItems(group.items)"
            :key="item.path"
            class="sidebar__item"
            :class="{ 'is-active': isActive(item.path) }"
            :title="item.label"
            @click="navigate(item.path)"
          >
            <component :is="item.icon" class="sidebar__item-icon" />
            <span v-show="!collapsed" class="sidebar__item-label">{{ item.label }}</span>
          </div>
        </div>
      </Transition>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  width: 220px;
  flex-shrink: 0;
  background: var(--color-bg-secondary);
  border-right: 1px solid var(--color-border-primary);
  overflow-y: auto;
  overflow-x: hidden;
  transition: width var(--transition-normal);
  display: flex;
  flex-direction: column;
  padding-top: 4px;
}

.sidebar--collapsed {
  width: 64px;
}

.sidebar__toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 36px;
  cursor: pointer;
  color: var(--color-text-muted);
  transition: color var(--transition-fast);
  margin-bottom: 4px;
}

.sidebar__toggle:hover {
  color: var(--color-text-primary);
}

.sidebar__group {
  margin-bottom: 2px;
}

.sidebar__group-title {
  display: flex;
  align-items: center;
  height: 40px;
  padding: 0 12px;
  cursor: pointer;
  color: var(--color-text-muted);
  font-size: 13px;
  font-weight: 500;
  transition: background var(--transition-fast), color var(--transition-fast);
  gap: 10px;
}

.sidebar__group-title:hover {
  background: var(--color-bg-card);
  color: var(--color-text-secondary);
}

.sidebar__group-title.is-expanded {
  color: var(--color-text-primary);
}

.sidebar__group-icon {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
}

.sidebar__group-label {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
}

.sidebar__group-arrow {
  flex-shrink: 0;
  transition: transform var(--transition-fast);
}

.sidebar__group-arrow.is-rotated {
  transform: rotate(180deg);
}

.sidebar__group-items {
  overflow: hidden;
}

.sidebar__item {
  display: flex;
  align-items: center;
  height: 36px;
  padding: 0 12px 0 40px;
  cursor: pointer;
  color: var(--color-text-muted);
  font-size: 13px;
  transition: background var(--transition-fast), color var(--transition-fast);
  gap: 8px;
}

.sidebar__item:hover {
  background: var(--color-bg-card);
  color: var(--color-text-secondary);
}

.sidebar__item.is-active {
  color: var(--color-accent-primary);
  background: rgba(0, 113, 227, 0.1);
  border-right: 2px solid var(--color-accent-primary);
}

.sidebar__item-icon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

.sidebar__item-label {
  white-space: nowrap;
  overflow: hidden;
}

.sidebar-collapse-enter-active,
.sidebar-collapse-leave-active {
  transition: all 0.2s ease;
}

.sidebar-collapse-enter-from,
.sidebar-collapse-leave-to {
  opacity: 0;
  max-height: 0;
}
</style>
