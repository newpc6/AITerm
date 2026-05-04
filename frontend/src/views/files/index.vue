<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Download, Delete, Upload, Refresh, Search } from '@element-plus/icons-vue'
import type { FileItem } from '@/api/aiterm'
import { getFiles, deleteFile, batchDeleteFiles, getFileDownloadUrl, uploadFile, getFileTypes, getFileSources } from '@/api/aiterm'
import Pagination from '@/components/Pagination.vue'

const files = ref<FileItem[]>([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const search = ref('')
const selectedFileType = ref('')
const selectedSource = ref('')
const selectedFiles = ref<FileItem[]>([])
const fileTypes = ref<string[]>([])
const fileSources = ref<string[]>(['generated', 'uploaded', 'system'])

const uploadDialogVisible = ref(false)
const uploadLoading = ref(false)
const uploadFile_ = ref<File | null>(null)
const uploadDescription = ref('')

const fileCount = computed(() => total.value)

async function loadFiles() {
  loading.value = true
  try {
    const result = await getFiles({
      page: page.value,
      page_size: pageSize.value,
      search: search.value || undefined,
      file_type: selectedFileType.value || undefined,
      source: selectedSource.value || undefined,
    })
    files.value = result.files
    total.value = result.total
  } catch {
    ElMessage.error('加载文件列表失败')
  } finally {
    loading.value = false
  }
}

async function loadFileTypes() {
  try {
    fileTypes.value = await getFileTypes()
  } catch {
    // ignore
  }
}

function handlePageChange(newPage: number) {
  page.value = newPage
  loadFiles()
}

function handlePageSizeChange(newSize: number) {
  pageSize.value = newSize
  page.value = 1
  loadFiles()
}

function handleSearch() {
  page.value = 1
  loadFiles()
}

function handleFilterChange() {
  page.value = 1
  loadFiles()
}

function formatFileSize(size: number): string {
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(2)} KB`
  if (size < 1024 * 1024 * 1024) return `${(size / 1024 / 1024).toFixed(2)} MB`
  return `${(size / 1024 / 1024 / 1024).toFixed(2)} GB`
}

function getSourceLabel(source: string): string {
  const labels: Record<string, string> = {
    generated: '生成',
    uploaded: '上传',
    system: '系统',
  }
  return labels[source] || source
}

function getSourceType(source: string): string {
  const types: Record<string, string> = {
    generated: 'success',
    uploaded: 'primary',
    system: 'info',
  }
  return types[source] || ''
}

function handleDownload(file: FileItem) {
  const url = getFileDownloadUrl(file.uuid)
  const a = document.createElement('a')
  a.href = url
  a.download = file.original_filename
  a.click()
}

async function handleDelete(file: FileItem) {
  try {
    await ElMessageBox.confirm(`确定要删除文件 "${file.original_filename}" 吗？`, '删除确认', {
      type: 'warning',
    })
    await deleteFile(file.id)
    ElMessage.success('删除成功')
    await loadFiles()
  } catch {
    // cancelled
  }
}

async function handleBatchDelete() {
  if (selectedFiles.value.length === 0) {
    ElMessage.warning('请先选择要删除的文件')
    return
  }
  try {
    await ElMessageBox.confirm(`确定要删除选中的 ${selectedFiles.value.length} 个文件吗？`, '批量删除确认', {
      type: 'warning',
    })
    const ids = selectedFiles.value.map(f => f.id)
    const count = await batchDeleteFiles(ids)
    ElMessage.success(`成功删除 ${count} 个文件`)
    selectedFiles.value = []
    await loadFiles()
  } catch {
    // cancelled
  }
}

function openUploadDialog() {
  uploadFile_.value = null
  uploadDescription.value = ''
  uploadDialogVisible.value = true
}

function handleUploadFileChange(event: Event) {
  const target = event.target as HTMLInputElement
  if (target.files && target.files[0]) {
    uploadFile_.value = target.files[0]
  }
}

async function handleUpload() {
  if (!uploadFile_.value) {
    ElMessage.warning('请选择文件')
    return
  }

  uploadLoading.value = true
  try {
    await uploadFile({
      file: uploadFile_.value,
      description: uploadDescription.value || undefined,
    })
    ElMessage.success('上传成功')
    uploadDialogVisible.value = false
    await loadFiles()
  } catch (e: unknown) {
    const message = (e as { response?: { data?: { message?: string } } })?.response?.data?.message || '上传失败'
    ElMessage.error(message)
  } finally {
    uploadLoading.value = false
  }
}

onMounted(() => {
  loadFiles()
  loadFileTypes()
})
</script>

<template>
  <section class="page">
    <div class="hero">
      <p class="label">文件</p>
      <h1>文件管理</h1>
      <p>管理生成的文件、上传的文件等，支持下载和删除操作。</p>
    </div>

    <div class="card">
      <div class="page-header">
        <div>
          <p class="label">文件列表</p>
          <div class="value">{{ fileCount }} 个文件</div>
        </div>
        <div class="page-header__actions">
          <el-button :loading="loading" @click="loadFiles">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
          <el-button type="primary" @click="openUploadDialog">
            <el-icon><Upload /></el-icon>
            上传文件
          </el-button>
          <el-button type="danger" :disabled="selectedFiles.length === 0" @click="handleBatchDelete">
            <el-icon><Delete /></el-icon>
            删除选中 ({{ selectedFiles.length }})
          </el-button>
        </div>
      </div>

      <div class="filters">
        <el-input
          v-model="search"
          placeholder="搜索文件名..."
          clearable
          style="width: 200px"
          @keyup.enter="handleSearch"
          @clear="handleSearch"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-select v-model="selectedFileType" placeholder="文件类型" clearable style="width: 150px" @change="handleFilterChange">
          <el-option v-for="type in fileTypes" :key="type" :label="type.toUpperCase()" :value="type" />
        </el-select>
        <el-select v-model="selectedSource" placeholder="来源" clearable style="width: 120px" @change="handleFilterChange">
          <el-option v-for="source in fileSources" :key="source" :label="getSourceLabel(source)" :value="source" />
        </el-select>
        <el-button type="primary" @click="handleSearch">搜索</el-button>
      </div>

      <el-table :data="files" v-loading="loading" @selection-change="selectedFiles = $event">
        <el-table-column type="selection" width="50" />
        <el-table-column prop="original_filename" label="文件名" min-width="200">
          <template #default="{ row }">
            <div class="filename-cell">
              <span class="filename">{{ row.original_filename }}</span>
              <span v-if="row.description" class="description">{{ row.description }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="file_size" label="大小" width="100">
          <template #default="{ row }">
            {{ formatFileSize(row.file_size) }}
          </template>
        </el-table-column>
        <el-table-column prop="file_type" label="类型" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.file_type" size="small">{{ row.file_type.toUpperCase() }}</el-tag>
            <span v-else class="text-secondary">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="source" label="来源" width="80">
          <template #default="{ row }">
            <el-tag :type="getSourceType(row.source)" size="small">{{ getSourceLabel(row.source) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ row.created_at ? new Date(row.created_at).toLocaleString() : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="handleDownload(row)">
              <el-icon><Download /></el-icon>
              下载
            </el-button>
            <el-button type="danger" link @click="handleDelete(row)">
              <el-icon><Delete /></el-icon>
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <Pagination
        :page="page"
        :page-size="pageSize"
        :total="total"
        @update:page="handlePageChange"
        @update:page-size="handlePageSizeChange"
      />
    </div>

    <el-dialog v-model="uploadDialogVisible" title="上传文件" width="500px">
      <el-form label-position="top">
        <el-form-item label="选择文件">
          <input type="file" @change="handleUploadFileChange" class="file-input" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="uploadDescription" type="textarea" :rows="3" placeholder="可选，填写文件描述..." />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="uploadDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="uploadLoading" @click="handleUpload">上传</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
@use '@/styles/global.scss';

.filters {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.filename-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.filename {
  font-weight: 500;
}

.description {
  font-size: 12px;
  color: var(--color-text-secondary);
}

.text-secondary {
  color: var(--color-text-secondary);
}

.file-input {
  width: 100%;
  padding: 8px;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  background: var(--color-bg);
  color: var(--color-text);
}
</style>
