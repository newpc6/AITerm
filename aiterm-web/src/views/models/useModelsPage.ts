import { onMounted, ref, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { getModels, createModel, updateModel, deleteModel, setDefaultModel } from '@/api/aiterm'
import type { ModelConfigItem, ModelConfigPayload } from '@/types/api'

export function useModelsPage() {
  const loading = ref(false)
  const saving = ref(false)
  const models = ref<ModelConfigItem[]>([])
  const dialogVisible = ref(false)
  const dialogTitle = ref('新建模型配置')
  const editingModel = ref<ModelConfigItem | null>(null)
  const form = ref<ModelConfigPayload>({
    name: '',
    api_url: 'https://api.openai.com/v1',
    api_key: '',
    model: 'gpt-4o-mini',
    temperature: 0.7,
    extra_params: {},
    extra_body: {},
    extra_headers: {},
    is_default: false,
  })
  const extraBodyText = ref('{}')
  const extraHeadersText = ref('{}')
  const page = ref(1)
  const pageSize = ref(10)
  const total = ref(0)

  const hasModels = computed(() => models.value.length > 0)

  async function loadModels() {
    loading.value = true
    try {
      const data = await getModels({ page: page.value, page_size: pageSize.value })
      models.value = data.items || []
      total.value = data.total || 0
    } catch {
      ElMessage.error('加载模型配置失败')
    } finally {
      loading.value = false
    }
  }

  function handlePageChange(newPage: number) {
    page.value = newPage
    void loadModels()
  }

  function handlePageSizeChange(newSize: number) {
    pageSize.value = newSize
    page.value = 1
    void loadModels()
  }

  function openCreateDialog() {
    dialogTitle.value = '新建模型配置'
    editingModel.value = null
    form.value = {
      name: '',
      api_url: 'https://api.openai.com/v1',
      api_key: '',
      model: 'gpt-4o-mini',
      temperature: 0.7,
      extra_params: {},
      extra_body: {},
      extra_headers: {},
      is_default: models.value.length === 0,
    }
    extraBodyText.value = '{}'
    extraHeadersText.value = '{}'
    dialogVisible.value = true
  }

  function openEditDialog(model: ModelConfigItem) {
    dialogTitle.value = '编辑模型配置'
    editingModel.value = model
    form.value = {
      name: model.name,
      api_url: model.api_url,
      api_key: model.api_key,
      model: model.model,
      temperature: model.temperature,
      extra_params: model.extra_params || {},
      extra_body: model.extra_body || {},
      extra_headers: model.extra_headers || {},
      is_default: model.is_default,
    }
    extraBodyText.value = JSON.stringify(model.extra_body || {}, null, 2)
    extraHeadersText.value = JSON.stringify(model.extra_headers || {}, null, 2)
    dialogVisible.value = true
  }

  function parseJsonSafe(text: string, fallback: Record<string, unknown>) {
    try {
      return JSON.parse(text)
    } catch {
      return fallback
    }
  }

  async function saveModel() {
    if (!form.value.name.trim()) {
      ElMessage.warning('请输入模型名称')
      return
    }
    if (!form.value.api_url.trim()) {
      ElMessage.warning('请输入API地址')
      return
    }
    if (!form.value.model.trim()) {
      ElMessage.warning('请输入模型标识')
      return
    }

    form.value.extra_body = parseJsonSafe(extraBodyText.value, {})
    form.value.extra_headers = parseJsonSafe(extraHeadersText.value, {})

    saving.value = true
    try {
      if (editingModel.value) {
        await updateModel(editingModel.value.id, form.value)
        ElMessage.success('模型配置已更新')
      } else {
        await createModel(form.value)
        ElMessage.success('模型配置已创建')
      }
      dialogVisible.value = false
      await loadModels()
    } catch (e: unknown) {
      const error = e as { response?: { data?: { message?: string } } }
      ElMessage.error(error.response?.data?.message || '保存失败')
    } finally {
      saving.value = false
    }
  }

  async function handleDelete(model: ModelConfigItem) {
    if (model.is_default && models.value.length === 1) {
      ElMessage.warning('不能删除唯一的模型配置')
      return
    }

    try {
      await ElMessageBox.confirm(`确定要删除模型配置「${model.name}」吗？`, '删除确认', { type: 'warning' })
      await deleteModel(model.id)
      ElMessage.success('模型配置已删除')
      total.value = Math.max(0, total.value - 1)
      if (models.value.length === 0 && page.value > 1) {
        page.value -= 1
      }
      await loadModels()
    } catch {
      // 用户取消
    }
  }

  async function handleSetDefault(model: ModelConfigItem) {
    try {
      await setDefaultModel(model.id)
      ElMessage.success('已设置为默认模型')
      await loadModels()
    } catch {
      ElMessage.error('设置默认模型失败')
    }
  }

  onMounted(() => {
    void loadModels()
  })

  return {
    loading,
    saving,
    models,
    hasModels,
    dialogVisible,
    dialogTitle,
    form,
    extraBodyText,
    extraHeadersText,
    loadModels,
    openCreateDialog,
    openEditDialog,
    saveModel,
    handleDelete,
    handleSetDefault,
    page,
    pageSize,
    total,
    handlePageChange,
    handlePageSizeChange,
  }
}
