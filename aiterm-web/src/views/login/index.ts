import { defineComponent } from 'vue'

import './index.scss'
import template from './index.html?raw'
import { useLoginPage } from './useLoginPage'

export default defineComponent({
  name: 'LoginPage',
  setup() {
    return useLoginPage()
  },
  template,
})
