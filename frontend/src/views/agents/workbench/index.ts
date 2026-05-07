import { defineComponent } from 'vue'
import template from './index.html?raw'
import { useWorkbenchPage } from './useWorkbenchPage'

export default defineComponent({
  name: 'WorkbenchPage',
  setup() {
    return useWorkbenchPage()
  },
  template,
})
