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

  async function loadTasks() {
    loading.value = true
    errorMessage.value = ''

    try {
      const data = await getTasks()
      tasks.value = data.items
    } catch {
      errorMessage.value = '任务接口不可用。'
    } finally {
      loading.value = false
    }
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
  }
}
