import { defineComponent } from 'vue'

import UserForm from './components/UserForm.vue'
import UserTable from './components/UserTable.vue'
import Pagination from '@/components/Pagination.vue'
import './index.scss'
import template from './index.html?raw'
import { useUsersPage } from './useUsersPage'

export default defineComponent({
  name: 'UsersPage',
  components: {
    UserForm,
    UserTable,
    Pagination,
  },
  setup() {
    return useUsersPage()
  },
  template,
})
