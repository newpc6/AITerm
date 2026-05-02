<script setup lang="ts">
import { Loading } from '@element-plus/icons-vue'
</script>

<template>
  <div class="message-loading">
    <el-icon class="message-loading__icon is-loading">
      <Loading />
    </el-icon>
  </div>
</template>

<style scoped>
.message-loading {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 0;
}

.message-loading__icon {
  font-size: 18px;
  color: #60a5fa;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>
