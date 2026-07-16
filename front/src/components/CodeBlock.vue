<script setup lang="ts">
/**
 * 예제 코드 블록 컴포넌트.
 * highlight.js로 문법 하이라이트 + 복사 버튼 제공.
 */
import { ref, computed } from 'vue'
import hljs from 'highlight.js'
import 'highlight.js/styles/github.css'
import type { CodeExample } from '@/api/types'

const props = defineProps<{
  example: CodeExample
}>()

const copied = ref(false)

const highlightedCode = computed(() => {
  try {
    const result = hljs.highlight(props.example.code, {
      language: props.example.lang || 'plaintext',
    })
    return result.value
  } catch {
    // 언어 미지원 시 자동 감지
    try {
      return hljs.highlightAuto(props.example.code).value
    } catch {
      return props.example.code
    }
  }
})

async function copyCode(): Promise<void> {
  try {
    await navigator.clipboard.writeText(props.example.code)
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  } catch {
    // clipboard API 미지원 환경 대응
    const textarea = document.createElement('textarea')
    textarea.value = props.example.code
    document.body.appendChild(textarea)
    textarea.select()
    document.execCommand('copy')
    document.body.removeChild(textarea)
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  }
}

</script>

<template>
  <div class="code-block">
    <div class="code-header">
      <span class="code-lang">{{ example.lang }}</span>
      <button
        class="copy-button"
        @click="copyCode"
        :aria-label="copied ? '복사 완료' : '코드 복사'"
      >
        {{ copied ? '복사됨' : '복사' }}
      </button>
    </div>
    <pre class="code-pre"><code class="code-content" v-html="highlightedCode"></code></pre>
    <div class="code-explain">
      <span class="explain-label">설명</span>
      <span class="explain-text">{{ example.explain }}</span>
    </div>
    <div class="code-source">
      <span class="source-label">출처</span>
      <code class="source-ref">{{ example.source }}</code>
    </div>
  </div>
</template>

<style scoped>
.code-block {
  border: 1px solid #e8eaed;
  border-radius: 8px;
  overflow: hidden;
  margin-bottom: 16px;
  background: #fff;
}

.code-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: #f8f9fa;
  border-bottom: 1px solid #e8eaed;
}

.code-lang {
  font-size: 12px;
  font-weight: 600;
  color: #5f6368;
  text-transform: uppercase;
}

.copy-button {
  padding: 4px 12px;
  border: 1px solid #dadce0;
  border-radius: 4px;
  background: #fff;
  color: #5f6368;
  font-size: 12px;
  cursor: pointer;
  transition: background 0.2s;
}

.copy-button:hover {
  background: #e8eaed;
}

.code-pre {
  margin: 0;
  padding: 16px;
  overflow-x: auto;
  background: #fafafa;
}

.code-content {
  font-family: 'Menlo', 'Monaco', 'Consolas', monospace;
  font-size: 13px;
  line-height: 1.5;
}

.code-explain {
  padding: 10px 12px;
  border-top: 1px solid #e8eaed;
  font-size: 13px;
  color: #3c4043;
}

.explain-label {
  font-weight: 600;
  color: #5f6368;
  margin-right: 8px;
}

.code-source {
  padding: 6px 12px 10px;
  font-size: 12px;
  color: #9aa0a6;
}

.source-label {
  font-weight: 500;
  margin-right: 6px;
}

.source-ref {
  font-family: monospace;
  font-size: 11px;
  background: #f1f3f4;
  padding: 2px 6px;
  border-radius: 3px;
}
</style>
