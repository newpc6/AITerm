import { defineComponent } from 'vue'

import AuthSettingsPanel from './components/AuthSettingsPanel.vue'
import SettingsPanel from './components/SettingsPanel.vue'
import './index.scss'
import template from './index.html?raw'
import { useSettingsPage } from './useSettingsPage'

export default defineComponent({
  name: 'SettingsPage',
  components: {
    AuthSettingsPanel,
    SettingsPanel,
  },
  setup() {
    return useSettingsPage()
  },
  template,
})
