import { defineComponent } from 'vue'

import ConversationHistoryTable from './components/ConversationHistoryTable.vue'
import Pagination from '@/components/Pagination.vue'
import './index.scss'
import template from './index.html?raw'
import { useConversationHistoryPage } from './useConversationHistoryPage'

export default defineComponent({
  name: 'HistoryPage',
  components: {
    ConversationHistoryTable,
    Pagination,
  },
  setup() {
    return useConversationHistoryPage()
  },
  template,
})
