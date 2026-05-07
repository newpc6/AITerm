import { defineComponent } from 'vue'
import template from './index.html?raw'
import { useSkillsPage } from './useSkillsPage'

export default defineComponent({
  name: 'SkillsPage',
  setup() { return useSkillsPage() },
  template,
})
