<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, Refresh, View } from '@element-plus/icons-vue'
import type { ShareItem } from '@/api/aiterm'
import { listShares, batchDeleteShares, deleteShare } from '@/api/aiterm'
import Pagination from '@/components/Pagination.vue'

const shares = ref<ShareItem[]>([])
const loading = ref(false)
const deleting = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const selectedShares = ref<ShareItem[]>([])

const shareCount = computed(() => total.value)

async function loadShares() {
  loading.value = true
  try {
    const result = await listShares(page.value, pageSize.value)
    shares.value = result.items
    total.value = result.total
  } catch {
    ElMessage.error('加载分享列表失败')
  } finally {
    loading.value = false
  }
}

function handlePageChange(newPage: number) {
  page.value = newPage
  loadShares()
}

function handlePageSizeChange(newSize: number) {
  pageSize.value = newSize
  page.value = 1
  loadShares()
}

async function handleDelete(share: ShareItem) {
  try {
    await ElMessageBox.confirm(`确定要删除分享 "${share.title || '未命名'}" 吗？`, '删除确认', {
      type: 'warning',
    })
    await deleteShare(share.share_id)
    ElMessage.success('删除成功')
    await loadShares()
  } catch {
    // cancelled
  }
}

async function handleBatchDelete() {
  if (selectedShares.value.length === 0) {
    ElMessage.warning('请先选择要删除的分享')
    return
  }
  try {
    await ElMessageBox.confirm(`确定要删除选中的 ${selectedShares.value.length} 个分享吗？`, '批量删除确认', {
      type: 'warning',
    })
    deleting.value = true
    const ids = selectedShares.value.map(s => s.share_id)
    await batchDeleteShares(ids)
    ElMessage.success('批量删除成功')
    selectedShares.value = []
    await loadShares()
  } catch {
    // cancelled
  } finally {
    deleting.value = false
  }
}

function handleOpen(shareId: string) {
  window.open(`/share/${shareId}`, '_blank')
}

function formatDate(dateStr: string | null) {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString()
}

function isExpired(expiresAt: string | null) {
  if (!expiresAt) return false
  return new Date(expiresAt) < new Date()
}

onMounted(() => {
  loadShares()
})
</script>

<template>
  <section class="page">
    <div class="hero">
      <p class="label">分享</p>
      <h1>分享管理</h1>
      <p>管理对话分享链接，支持查看、删除操作。</p>
    </div>

    <div class="card">
      <div class="page-header">
        <div>
          <p class="label">分享列表</p>
          <div class="value">{{ shareCount }} 个分享</div>
        </div>
        <div class="page-header__actions">
          <el-button :loading="loading" @click="loadShares">
            <el-icon>
              <Refresh />
            </el-icon>
            刷新
          </el-button>
          <el-button type="danger" :disabled="selectedShares.length === 0" :loading="deleting"
            @click="handleBatchDelete">
            <el-icon>
              <Delete />
            </el-icon>
            删除选中 ({{ selectedShares.length }})
          </el-button>
        </div>
      </div>

      <el-table :data="shares" v-loading="loading" @selection-change="selectedShares = $event">
        <el-table-column type="selection" width="50" />
        <el-table-column prop="share_id" label="分享ID" width="140" />
        <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <span>{{ row.title || '未命名' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="chat_id" label="对话ID" width="100" />
        <el-table-column prop="has_password" label="密码保护" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.has_password" type="warning" size="small">有密码</el-tag>
            <el-tag v-else type="info" size="small">无</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="expires_at" label="有效期" width="180">
          <template #default="{ row }">
            <span v-if="!row.expires_at">永不过期</span>
            <span v-else :class="{ 'text-expired': isExpired(row.expires_at) }">
              {{ formatDate(row.expires_at) }}
            </span>
            <el-tag v-if="isExpired(row.expires_at)" type="danger" size="small" style="margin-left: 4px;">已过期</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="view_count" label="访问次数" width="100" />
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="handleOpen(row.share_id)">
              <el-icon>
                <View />
              </el-icon>
              查看
            </el-button>
            <el-button type="danger" link @click="handleDelete(row)">
              <el-icon>
                <Delete />
              </el-icon>
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <Pagination :page="page" :page-size="pageSize" :total="total" @update:page="handlePageChange"
        @update:page-size="handlePageSizeChange" />
    </div>
  </section>
</template>

<style scoped>
@use '@/styles/global.scss';

.text-expired {
  color: var(--el-color-danger);
}
</style>
