import { defineComponent } from 'vue'
import { Share } from '@element-plus/icons-vue'

import ChatComposer from './components/ChatComposer.vue'
import MessageList from './components/MessageList.vue'
import ShareDialog from './components/ShareDialog.vue'
import './index.scss'
import template from './index.html?raw'
import { useChatPage } from './useChatPage'

export default defineComponent({
  name: 'ChatPage',
  components: {
    ChatComposer,
    MessageList,
    ShareDialog,
    Share,
  },
  setup() {
    return useChatPage()
  },
  template,
})
