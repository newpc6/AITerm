<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import MarkdownContent from '@/components/MarkdownContent.vue'
import type { TaskDetail, TaskDetailStep } from '@/types/api'

const props = defineProps<{
  canRestart: boolean
  canStop: boolean
  confirming: boolean
  streaming: boolean
  task: TaskDetail | null
}>()

const emit = defineEmits<{
  restart: []
  stop: []
}>()

const detailDrawerVisible = ref(false)

watch(
  () => props.task?.id,
  () => {
    detailDrawerVisible.value = false
  },
  { immediate: true },
)

function resolveTagType(step: TaskDetailStep) {
  switch (step.status) {
    case 'completed':
      return 'success'
    case 'failed':
    case 'cancelled':
      return 'danger'
    case 'executing':
      return 'primary'
    case 'waiting_confirm':
      return 'warning'
    default:
      return 'info'
  }
}

function hasRepairInfo(step: TaskDetailStep) {
  return !!step.repair_count || !!step.original_command || !!step.first_failure_output || !!step.repaired_output || !!step.last_error || !!step.repair_reason || !!step.repair_suggestion || !!step.repaired_command
}

function toSummaryText(content?: string) {
  if (!content) {
    return ''
  }

  return content
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/[*_>#-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

const summaryText = computed(() => {
  if (!props.task) {
    return ''
  }

  return toSummaryText(props.task.summary) || '暂无任务摘要。'
})
</script>

<template>
  <div class="task-status-card">
    <div class="task-status-card__header">
      <div class="task-status-card__headline">
        <span class="task-status-card__label-text">任务信息</span>
        <strong class="task-status-card__title">{{ task?.title ?? '暂无活动任务' }}</strong>
      </div>
      <div class="task-status-card__badges">
        <el-tag size="small" effect="dark" :type="streaming ? 'primary' : 'warning'">{{ streaming ? '执行中' : task?.status
          ?? '空闲' }}</el-tag>
        <el-tag v-if="task" size="small" effect="plain" type="info">进度 {{ task.progress }}%</el-tag>
      </div>
    </div>

    <div v-if="task" class="task-status-card__summary-row">
      <div class="task-status-card__summary-text" :title="summaryText">{{ summaryText }}</div>
      <el-button type="primary" plain @click="detailDrawerVisible = true">查看详情</el-button>
    </div>

    <el-drawer v-model="detailDrawerVisible" :teleported="false" class="task-status-drawer" title="任务详情" size="720px">
      <template v-if="task">
        <div class="task-status-card__details">
          <div class="task-status-card__detail-header">
            <div>
              <div class="task-status-card__detail-title">{{ task.title }}</div>
              <div class="task-status-card__meta">
                <span>状态 {{ task.status }}</span>
                <span>进度 {{ task.progress }}%</span>
                <span>节点 {{ task.node_id }}</span>
                <span>任务 {{ task.id }}</span>
              </div>
            </div>
            <el-progress class="task-status-card__detail-progress" :percentage="task.progress" :stroke-width="8"
              :show-text="false" />
          </div>

          <MarkdownContent v-if="task.summary" class="task-status-card__summary" :content="task.summary" />
          <div v-if="task.final_result" class="task-status-card__final-result">
            <span class="task-status-card__label-text">最终结果</span>
            <MarkdownContent :content="task.final_result" />
          </div>
          <MarkdownContent v-if="task.risk_reason" class="task-status-card__risk" :content="task.risk_reason" />

          <div v-if="task.steps?.length" class="task-status-card__steps">
            <div v-for="step in task.steps" :key="step.index" class="task-status-card__step">
              <div class="task-status-card__step-header">
                <div class="task-status-card__step-title">
                  <span>第 {{ step.index }} 步</span>
                  <strong>{{ step.title }}</strong>
                </div>
                <div class="task-status-card__step-tags">
                  <el-tag size="small" :type="resolveTagType(step)">{{ step.status }}</el-tag>
                  <el-tag v-if="step.repair_count" size="small" type="warning">自动修正 {{ step.repair_count }} 次</el-tag>
                </div>
              </div>

              <div v-if="step.command" class="task-status-card__block">
                <span class="task-status-card__label-text">当前命令</span>
                <code>{{ step.command }}</code>
              </div>

              <div v-if="step.result_output" class="task-status-card__block">
                <span class="task-status-card__label-text">执行结果</span>
                <code>{{ step.result_output }}</code>
              </div>

              <div v-if="hasRepairInfo(step)" class="task-status-card__repair">
                <div v-if="step.original_command" class="task-status-card__block">
                  <span class="task-status-card__label-text">失败前命令</span>
                  <code>{{ step.original_command }}</code>
                </div>
                <div v-if="step.first_failure_output" class="task-status-card__block">
                  <span class="task-status-card__label-text">首次失败输出</span>
                  <code>{{ step.first_failure_output }}</code>
                </div>
                <div v-if="step.repaired_output" class="task-status-card__block">
                  <span class="task-status-card__label-text">修正后输出</span>
                  <code>{{ step.repaired_output }}</code>
                </div>
                <div v-if="step.last_error" class="task-status-card__block">
                  <span class="task-status-card__label-text">最近错误</span>
                  <MarkdownContent :content="step.last_error" />
                </div>
                <div v-if="step.repair_reason" class="task-status-card__block">
                  <span class="task-status-card__label-text">复盘原因</span>
                  <MarkdownContent :content="step.repair_reason" />
                </div>
                <div v-if="step.repair_suggestion" class="task-status-card__block">
                  <span class="task-status-card__label-text">模型建议</span>
                  <MarkdownContent :content="step.repair_suggestion" />
                </div>
                <div v-if="step.repaired_command" class="task-status-card__block">
                  <span class="task-status-card__label-text">修正后命令</span>
                  <code>{{ step.repaired_command }}</code>
                </div>
              </div>
            </div>
          </div>
        </div>
      </template>
      <template #footer>
        <div v-if="task" class="task-status-card__actions">
          <el-button @click="detailDrawerVisible = false">关闭</el-button>
          <el-button v-if="canStop" :disabled="confirming" @click="emit('stop')">停止任务</el-button>
          <el-button v-if="canRestart" type="primary" :disabled="confirming || streaming"
            @click="emit('restart')">重新执行</el-button>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<style scoped>
.task-status-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  flex-shrink: 0;
  padding: 14px 16px;
  border-radius: 18px;
  border: 1px solid rgba(96, 165, 250, 0.35);
  background:
    linear-gradient(135deg, rgba(30, 64, 175, 0.34), rgba(14, 116, 144, 0.2)),
    rgba(15, 23, 42, 0.78);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.06);
}

.task-status-card__header,
.task-status-card__summary-row,
.task-status-card__detail-header,
.task-status-card__meta,
.task-status-card__step-header,
.task-status-card__step-tags,
.task-status-card__actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.task-status-card__headline {
  display: grid;
  gap: 4px;
}

.task-status-card__title {
  font-size: 15px;
  color: rgba(255, 255, 255, 0.96);
}

.task-status-card__label-text {
  font-size: 12px;
  color: rgba(191, 219, 254, 0.82);
}

.task-status-card__badges {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.task-status-card__summary-row {
  align-items: center;
}

.task-status-card__summary-text {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  color: rgba(239, 246, 255, 0.88);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-status-card__detail-title {
  font-size: 18px;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.96);
}

.task-status-card__detail-progress {
  min-width: 180px;
}

.task-status-card__meta {
  flex-wrap: wrap;
  margin-top: 8px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.62);
}

.task-status-card__summary,
.task-status-card__final-result,
.task-status-card__risk {
  margin: 0;
  padding: 14px 16px;
  border-radius: 16px;
  background: rgba(2, 6, 23, 0.62);
  border: 1px solid rgba(148, 163, 184, 0.16);
  color: rgba(255, 255, 255, 0.92);
}

.task-status-card__risk {
  color: #fbbf24;
}

.task-status-card__summary :deep(.markdown-content),
.task-status-card__final-result :deep(.markdown-content),
.task-status-card__risk :deep(.markdown-content) {
  color: inherit;
}

.task-status-card__details {
  display: grid;
  gap: 16px;
}

.task-status-card__steps {
  display: grid;
  gap: 12px;
}

.task-status-card__step,
.task-status-card__repair {
  display: grid;
  gap: 10px;
}

.task-status-card__step {
  padding: 14px 16px;
  border-radius: 16px;
  background: rgba(15, 23, 42, 0.64);
  border: 1px solid rgba(148, 163, 184, 0.18);
}

.task-status-card__step-title {
  display: grid;
  gap: 4px;
}

.task-status-card__step-title span {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.56);
}

.task-status-card__block {
  display: grid;
  gap: 6px;
}

.task-status-card__block code {
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(2, 6, 23, 0.78);
  border: 1px solid rgba(96, 165, 250, 0.16);
  color: rgba(255, 255, 255, 0.92);
  overflow-wrap: anywhere;
  white-space: pre-wrap;
  font-family: Consolas, 'Courier New', monospace;
}

.task-status-card__actions {
  justify-content: flex-end;
  width: 100%;
}

:deep(.task-status-drawer) {
  background: #0f172a;
  color: #fff;
}

:deep(.task-status-drawer .el-drawer__header) {
  margin-bottom: 0;
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

:deep(.task-status-drawer .el-drawer__body) {
  padding-top: 20px;
  overflow: auto;
}

:deep(.task-status-drawer .el-drawer__footer) {
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  padding-top: 14px;
}

@media (max-width: 720px) {

  .task-status-card__header,
  .task-status-card__summary-row,
  .task-status-card__detail-header,
  .task-status-card__step-header,
  .task-status-card__actions {
    display: grid;
    justify-content: stretch;
  }

  .task-status-card__detail-progress {
    min-width: 0;
  }

  .task-status-card__step-tags {
    justify-content: flex-start;
    flex-wrap: wrap;
  }
}
</style>
