import { defineComponent } from 'vue'
import './index.scss'
import template from './index.html?raw'
import { useSandboxPage } from './useSandboxPage'

export default defineComponent({
  name: 'SandboxPage',
  setup() {
    return useSandboxPage()
  },
  template,
})
