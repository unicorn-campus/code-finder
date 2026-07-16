<script setup lang="ts">
/**
 * 예시 질문 칩 컴포넌트.
 * 클릭 시 해당 질문으로 즉시 검색 실행.
 */
const emit = defineEmits<{
  select: [query: string]
}>()

const examples = [
  'LangGraph에서 StateGraph 만드는 법',
  'RAG 임베딩 방법',
  'ReAct 에이전트 패턴이란',
  'MCP 서버 구현 방법',
]
</script>

<template>
  <div class="example-chips" role="list" aria-label="예시 질문">
    <button
      v-for="example in examples"
      :key="example"
      class="chip"
      role="listitem"
      @click="emit('select', example)"
    >
      {{ example }}
    </button>
  </div>
</template>

<style scoped>
.example-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
  margin-top: 16px;
}

.chip {
  padding: 8px 16px;
  border: 1px solid #dadce0;
  border-radius: 16px;
  background: #f8f9fa;
  color: #5f6368;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.2s, border-color 0.2s;
  white-space: nowrap;
}

.chip:hover {
  background: #e8eaed;
  border-color: #bdc1c6;
}

.chip:focus-visible {
  outline: 2px solid #4285f4;
  outline-offset: 2px;
}
</style>
