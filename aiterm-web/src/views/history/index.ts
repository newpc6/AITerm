import { defineComponent } from 'vue'

import ConversationHistoryTable from './components/ConversationHistoryTable.vue'
import './index.scss'
import template from './index.html?raw'
import { useConversationHistoryPage } from './useConversationHistoryPage'

export default defineComponent({
  name: 'HistoryPage',
  components: {
    ConversationHistoryTable,
  },
  setup() {
    return useConversationHistoryPage()
  },
  template,
})
