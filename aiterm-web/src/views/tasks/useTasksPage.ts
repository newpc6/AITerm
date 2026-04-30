import { onMounted, ref } from 'vue'
import { ElMessageBox } from 'element-plus'

import { deleteTask, getTasks } from '@/api/aiterm'
import type { TaskItem } from '@/types/api'

export function useTasksPage() {
  const loading = ref(false)
  const errorMessage = ref('')
  const successMessage = ref('')
  const tasks = ref<TaskItem[]>([])
  const deletingTaskId = ref('')
  const page = ref(1)
  const pageSize = ref(10)
  const total = ref(0)

  async function loadTasks() {
    loading.value = true
    errorMessage.value = ''

    try {
      const data = await getTasks({ page: page.value, page_size: pageSize.value })
      tasks.value = data.items
      total.value = data.total
    } catch {
      errorMessage.value = '任务接口不可用。'
    } finally {
      loading.value = false
    }
  }

  function handlePageChange(newPage: number) {
    page.value = newPage
    void loadTasks()
  }

  function handlePageSizeChange(newSize: number) {
    pageSize.value = newSize
    page.value = 1
    void loadTasks()
  }

  async function removeTask(taskId: string) {
    errorMessage.value = ''
    successMessage.value = ''

    try {
      await ElMessageBox.confirm('确定删除该任务吗？', '删除任务', {
        type: 'warning',
        confirmButtonText: '删除',
        cancelButtonText: '取消',
      })
    } catch {
      return
    }

    deletingTaskId.value = taskId
    try {
      await deleteTask(taskId)
      successMessage.value = '任务删除成功。'
      total.value = Math.max(0, total.value - 1)
      if (tasks.value.length === 0 && page.value > 1) {
        page.value -= 1
      }
      await loadTasks()
    } catch {
      errorMessage.value = '删除任务失败。'
    } finally {
      deletingTaskId.value = ''
    }
  }

  onMounted(() => {
    void loadTasks()
  })

  return {
    deletingTaskId,
    errorMessage,
    loading,
    loadTasks,
    removeTask,
    successMessage,
    tasks,
    page,
    pageSize,
    total,
    handlePageChange,
    handlePageSizeChange,
  }
}
