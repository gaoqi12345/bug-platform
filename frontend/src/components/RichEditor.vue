<template>
  <div class="rich-editor-wrapper" :class="{ 'is-focused': isFocused }">
    <!-- 工具栏 -->
    <div class="rich-editor-toolbar">
      <button type="button" class="toolbar-btn" :class="{ active: editor?.isActive('bold') }"
        @mousedown.prevent="editor?.chain().focus().toggleBold().run()" title="粗体 (Ctrl+B)">
        <b>B</b>
      </button>
      <button type="button" class="toolbar-btn" :class="{ active: editor?.isActive('italic') }"
        @mousedown.prevent="editor?.chain().focus().toggleItalic().run()" title="斜体 (Ctrl+I)">
        <i>I</i>
      </button>
      <button type="button" class="toolbar-btn" :class="{ active: editor?.isActive('bulletList') }"
        @mousedown.prevent="editor?.chain().focus().toggleBulletList().run()" title="无序列表">
        ≡
      </button>
      <button type="button" class="toolbar-btn" :class="{ active: editor?.isActive('orderedList') }"
        @mousedown.prevent="editor?.chain().focus().toggleOrderedList().run()" title="有序列表">
        1.
      </button>
      <button type="button" class="toolbar-btn" :class="{ active: editor?.isActive('code') }"
        @mousedown.prevent="editor?.chain().focus().toggleCode().run()" title="行内代码">
        &lt;/&gt;
      </button>
      <div class="toolbar-sep" />
      <!-- 上传图片按钮 -->
      <button type="button" class="toolbar-btn" @mousedown.prevent="fileInputRef?.click()" title="插入图片">
        🖼
      </button>
      <span class="toolbar-hint">Ctrl+V 可直接粘贴截图</span>
      <span v-if="uploading" class="toolbar-uploading">⏳ 图片上传中…</span>
    </div>

    <!-- 编辑区 -->
    <editor-content :editor="editor" class="rich-editor-body" />

    <!-- 隐藏文件输入 -->
    <input ref="fileInputRef" type="file" accept="image/*" multiple style="display:none" @change="handleFileUpload" />
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onBeforeUnmount } from 'vue'
import { useEditor, EditorContent } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'
import Image from '@tiptap/extension-image'
import Placeholder from '@tiptap/extension-placeholder'
import { imageApi } from '@/api'

const props = defineProps<{
  modelValue: string
  placeholder?: string
  minHeight?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const isFocused  = ref(false)
const uploading  = ref(false)
const fileInputRef = ref<HTMLInputElement>()

const editor = useEditor({
  content: props.modelValue,
  extensions: [
    StarterKit,
    // allowBase64 改为 false：彻底禁止 base64 内嵌，强制走 MinIO
    Image.configure({ inline: false, allowBase64: false }),
    Placeholder.configure({ placeholder: props.placeholder || '请输入内容，可 Ctrl+V 粘贴截图…' }),
  ],
  onUpdate({ editor }) {
    const html = editor.getHTML()
    emit('update:modelValue', html === '<p></p>' ? '' : html)
  },
  onFocus() { isFocused.value = true },
  onBlur()  { isFocused.value = false },
  editorProps: {
    handlePaste(view, event) {
      const items = event.clipboardData?.items
      if (!items) return false
      for (const item of Array.from(items)) {
        if (item.type.startsWith('image/')) {
          event.preventDefault()
          const file = item.getAsFile()
          if (file) insertImageFile(file)
          return true
        }
      }
      return false
    },
    handleDrop(view, event) {
      const files = event.dataTransfer?.files
      if (!files || files.length === 0) return false
      const imageFiles = Array.from(files).filter(f => f.type.startsWith('image/'))
      if (imageFiles.length === 0) return false
      event.preventDefault()
      imageFiles.forEach(f => insertImageFile(f))
      return true
    },
  },
})

// 外部 v-model 变化时同步（如表单 reset）
watch(() => props.modelValue, (val) => {
  if (!editor.value) return
  const current    = editor.value.getHTML()
  const normalized = current === '<p></p>' ? '' : current
  if (val !== normalized) {
    editor.value.commands.setContent(val || '', false)
  }
})

// 占位图 src（透明 1×1 GIF）
const PLACEHOLDER_SRC = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'

async function insertImageFile(file: File) {
  if (!editor.value) return

  // 1. 先插入占位图，让用户看到"图片正在上传"的位置
  editor.value.chain().focus().setImage({ src: PLACEHOLDER_SRC, alt: '上传中…' }).run()

  // 找到刚插入的占位节点位置（用于后续替换）
  const { state } = editor.value
  let placeholderPos = -1
  state.doc.descendants((node, pos) => {
    if (node.type.name === 'image' && node.attrs.src === PLACEHOLDER_SRC) {
      placeholderPos = pos
    }
  })

  uploading.value = true
  try {
    // 2. 向后端申请预签名 URL
    const presign = await imageApi.presign(file.name, file.type) as any

    // 3. 直传 MinIO（不经过后端）
    await fetch(presign.upload_url, {
      method: 'PUT',
      body: file,
      headers: { 'Content-Type': file.type },
    })

    // 4. 把占位图替换为真实 URL
    if (placeholderPos >= 0 && editor.value) {
      const { tr } = editor.value.state
      const node = editor.value.state.doc.nodeAt(placeholderPos)
      if (node && node.type.name === 'image' && node.attrs.src === PLACEHOLDER_SRC) {
        const newNode = node.type.create({ ...node.attrs, src: presign.image_url, alt: '' })
        editor.value.view.dispatch(tr.replaceWith(placeholderPos, placeholderPos + node.nodeSize, newNode))
      }
    }
  } catch {
    // 上传失败：移除占位图，不静默失败
    if (placeholderPos >= 0 && editor.value) {
      const { tr } = editor.value.state
      const node = editor.value.state.doc.nodeAt(placeholderPos)
      if (node && node.attrs.src === PLACEHOLDER_SRC) {
        editor.value.view.dispatch(tr.delete(placeholderPos, placeholderPos + node.nodeSize))
      }
    }
    // 用原生 alert 避免引入 ElMessage 依赖
    alert('图片上传失败，请检查网络后重试')
  } finally {
    uploading.value = false
  }
}

function handleFileUpload(event: Event) {
  const files = (event.target as HTMLInputElement).files
  if (!files) return
  Array.from(files).forEach(f => insertImageFile(f))
  ;(event.target as HTMLInputElement).value = ''
}

onBeforeUnmount(() => {
  editor.value?.destroy()
})
</script>

<style scoped>
.rich-editor-wrapper {
  border: 1px solid var(--border-input);
  border-radius: var(--radius-md);
  transition: border-color 0.2s, box-shadow 0.2s;
  background: var(--bg-input);
  width: 100%;
}

.rich-editor-wrapper.is-focused {
  border-color: var(--border-focus);
  box-shadow: 0 0 0 1px var(--border-focus);
}

.rich-editor-toolbar {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 4px 8px;
  border-bottom: 1px solid var(--border-subtle);
  background: var(--bg-surface);
  border-radius: var(--radius-md) var(--radius-md) 0 0;
  flex-wrap: wrap;
}

.toolbar-btn {
  min-width: 28px;
  height: 26px;
  padding: 0 6px;
  border: 1px solid transparent;
  border-radius: 3px;
  background: transparent;
  cursor: pointer;
  font-size: 13px;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s;
}

.toolbar-btn:hover {
  background: var(--bg-surface-2);
  border-color: var(--border-subtle);
}

.toolbar-btn.active {
  background: var(--accent-lime-bg);
  border-color: transparent;
  color: var(--accent-lime);
}

.toolbar-sep {
  width: 1px;
  height: 18px;
  background: var(--border-subtle);
  margin: 0 4px;
}

.toolbar-hint {
  font-size: 11px;
  color: var(--text-muted);
  margin-left: auto;
}

.toolbar-uploading {
  font-size: 11px;
  color: var(--accent-lime);
  margin-left: 8px;
  animation: pulse 1s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0.4; }
}

.rich-editor-body {
  padding: 8px 12px;
  min-height: v-bind('props.minHeight || "80px"');
  cursor: text;
}

/* tiptap ProseMirror 样式 */
.rich-editor-body :deep(.ProseMirror) {
  outline: none;
  min-height: v-bind('props.minHeight || "80px"');
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-primary);
}

.rich-editor-body :deep(.ProseMirror p) {
  margin: 0 0 4px;
}

.rich-editor-body :deep(.ProseMirror p:last-child) {
  margin-bottom: 0;
}

.rich-editor-body :deep(.ProseMirror img) {
  max-width: 100%;
  height: auto;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-subtle);
  margin: 4px 0;
  cursor: default;
}

.rich-editor-body :deep(.ProseMirror img.ProseMirror-selectednode) {
  outline: 2px solid var(--border-focus);
}

.rich-editor-body :deep(.ProseMirror ul),
.rich-editor-body :deep(.ProseMirror ol) {
  padding-left: 20px;
  margin: 4px 0;
}

.rich-editor-body :deep(.ProseMirror code) {
  background: var(--bg-canvas);
  border-radius: 3px;
  padding: 1px 4px;
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--color-warning);
}

.rich-editor-body :deep(.ProseMirror .is-editor-empty:first-child::before) {
  content: attr(data-placeholder);
  color: var(--text-muted);
  pointer-events: none;
  float: left;
  height: 0;
}
</style>
