<script setup lang="ts">
defineProps<{
  logs: string[]
}>()
</script>

<template>
  <div class="stream-output">
    <div class="stream-output__header">
      <p class="label">实时输出</p>
      <span>{{ logs.length }} 行</span>
    </div>

    <div class="stream-output__body">
      <p v-if="logs.length === 0" class="stream-output__empty">暂无输出</p>
      <pre v-for="(line, index) in logs" :key="`${index}-${line}`">{{ line }}</pre>
    </div>
  </div>
</template>

<style scoped>
.stream-output {
  display: grid;
  gap: 12px;
}

.stream-output__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.64);
}

.stream-output__body {
  padding: 16px;
  min-height: 180px;
  border-radius: 18px;
  background: #0b0b0f;
  border: 1px solid rgba(255, 255, 255, 0.08);
  overflow: auto;
}

.stream-output__body pre {
  margin: 0 0 10px;
  white-space: pre-wrap;
  line-height: 1.6;
  color: #34c759;
}

.stream-output__empty {
  margin: 0;
  color: rgba(255, 255, 255, 0.42);
}
</style>
