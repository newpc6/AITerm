import { defineComponent } from 'vue'
import template from './index.html?raw'
import { useFilesPage } from './useFilesPage'

export default defineComponent({ name: 'FilesPage', setup() { return useFilesPage() }, template })
