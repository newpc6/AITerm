import { defineComponent } from 'vue'
import MessageList from '@/views/chat/components/MessageList.vue'
import './index.scss'
import template from './index.html?raw'
import { useSharePage } from './useSharePage'

export default defineComponent({
  name: 'SharePage',
  components: {
    MessageList,
  },
  setup() {
    return useSharePage()
  },
  template,
})
