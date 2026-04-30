import { defineComponent } from 'vue'

import TaskTable from './components/TaskTable.vue'
import Pagination from '@/components/Pagination.vue'
import './index.scss'
import template from './index.html?raw'
import { useTasksPage } from './useTasksPage'

export default defineComponent({
  name: 'TasksPage',
  components: {
    TaskTable,
    Pagination,
  },
  setup() {
    return useTasksPage()
  },
  template,
})
