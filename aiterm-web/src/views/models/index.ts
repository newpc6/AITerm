import { defineComponent } from 'vue'

import Pagination from '@/components/Pagination.vue'
import './index.scss'
import template from './index.html?raw'
import { useModelsPage } from './useModelsPage'

export default defineComponent({
  name: 'ModelsPage',
  components: {
    Pagination,
  },
  setup() {
    return useModelsPage()
  },
  template,
})
