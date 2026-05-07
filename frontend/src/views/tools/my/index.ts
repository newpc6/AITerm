import { defineComponent } from 'vue'
import template from './index.html?raw'
import { useMyToolsPage } from './useMyToolsPage'

export default defineComponent({
  name: 'MyToolsPage',
  setup() {
    return useMyToolsPage()
  },
  template,
})
