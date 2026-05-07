import { defineComponent } from 'vue'
import template from './index.html?raw'
import { useProfilePage } from './useProfilePage'

export default defineComponent({
  name: 'ProfilePage',
  setup() {
    return useProfilePage()
  },
  template,
})
