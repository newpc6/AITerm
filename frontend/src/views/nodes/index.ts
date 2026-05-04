import { defineComponent } from 'vue'

import NodeForm from './components/NodeForm.vue'
import NodeTable from './components/NodeTable.vue'
import Pagination from '@/components/Pagination.vue'
import './index.scss'
import template from './index.html?raw'
import { useNodesPage } from './useNodesPage'

export default defineComponent({
  name: 'NodesPage',
  components: {
    NodeForm,
    NodeTable,
    Pagination,
  },
  setup() {
    return useNodesPage()
  },
  template,
})
