import { defineComponent } from 'vue'
import template from './index.html?raw'
import { useTeamsPage } from './useTeamsPage'

export default defineComponent({ name: 'TeamsPage', setup() { return useTeamsPage() }, template })
