import { defineComponent } from 'vue'

import './index.scss'
import template from './index.html?raw'
import { useGlobalSettingsPage } from './useGlobalSettingsPage'

export default defineComponent({
  name: 'GlobalSettingsPage',
  setup() {
    return useGlobalSettingsPage()
  },
  template,
})
