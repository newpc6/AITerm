import { defineComponent } from 'vue'
import template from './index.html?raw'
import { useWorkbenchPage } from './useWorkbenchPage'
import AgentChatPanel from './AgentChatPanel.vue'

export default defineComponent({
  name: 'WorkbenchPage',
  components: { AgentChatPanel },
  setup() { return useWorkbenchPage() },
  template,
})
