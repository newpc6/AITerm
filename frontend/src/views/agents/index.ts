import { defineComponent } from 'vue'
import template from './index.html?raw'
import { useAgentsPage } from './useAgentsPage'

export default defineComponent({
  name: 'AgentsPage',
  setup() {
    return useAgentsPage()
  },
  template,
})
