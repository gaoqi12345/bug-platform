import DOMPurify from 'dompurify'

/**
 * 富文本内容消毒 — 用于所有 v-html 渲染前。
 *
 * Tiptap 编辑器输出的 HTML 本身不保证安全（若后端未消毒存储），
 * 恶意用户可注入 <script> / onerror 等。此处用 DOMPurify 白名单过滤，
 * 保留富文本常用标签（p/strong/em/img 等），剥离脚本与事件处理器。
 */
export function sanitizeHtml(html: string | null | undefined): string {
  if (!html) return ''
  return DOMPurify.sanitize(html, {
    // 允许 Tiptap StarterKit 输出的富文本标签
    ALLOWED_TAGS: [
      'p', 'br', 'strong', 'em', 'u', 's', 'code', 'pre', 'blockquote',
      'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'hr',
      'img', 'a', 'span',
    ],
    ALLOWED_ATTR: ['href', 'src', 'alt', 'title', 'target', 'rel'],
    // 禁止 data-* 属性（避免 Tiptap 内部属性残留）
    ALLOW_DATA_ATTR: false,
  })
}
