import { defineComponent } from 'vue'

import NodeForm from './components/NodeForm.vue'
import NodeTable from './components/NodeTable.vue'
import './index.scss'
import template from './index.html?raw'
import { useNodesPage } from './useNodesPage'

export default defineComponent({
  name: 'NodesPage',
  components: {
    NodeForm,
    NodeTable,
  },
  setup() {
    return useNodesPage()
  },
  template,
})
