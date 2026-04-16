import { defineComponent } from 'vue'

import './index.scss'
import template from './index.html?raw'
import { useTerminalPage } from './useTerminalPage'

export default defineComponent({
  name: 'TerminalPage',
  setup() {
    return useTerminalPage()
  },
  template,
})
