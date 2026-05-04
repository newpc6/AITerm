import { defineComponent } from 'vue'

import ChatComposer from './components/ChatComposer.vue'
import MessageList from './components/MessageList.vue'
import './index.scss'
import template from './index.html?raw'
import { useChatPage } from './useChatPage'

export default defineComponent({
  name: 'ChatPage',
  components: {
    ChatComposer,
    MessageList,
  },
  setup() {
    return useChatPage()
  },
  template,
})
