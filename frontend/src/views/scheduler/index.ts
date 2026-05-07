import { defineComponent } from 'vue'
import template from './index.html?raw'
import { useSchedulerPage } from './useSchedulerPage'

export default defineComponent({ name: 'SchedulerPage', setup() { return useSchedulerPage() }, template })
