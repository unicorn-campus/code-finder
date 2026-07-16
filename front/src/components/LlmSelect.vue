<script setup lang="ts">
/**
 * LLM 선택 드롭다운 컴포넌트.
 * "자동" 선택 시 llm 파라미터 미포함 → 백엔드 자동 라우팅.
 */
import type { LlmOption } from '@/api/types'

defineProps<{
  modelValue: LlmOption
}>()

const emit = defineEmits<{
  'update:modelValue': [value: LlmOption]
}>()

const options: { value: LlmOption; label: string }[] = [
  { value: 'auto', label: '자동 선택' },
  { value: 'claude', label: 'Claude' },
  { value: 'openai', label: 'OpenAI' },
  { value: 'gemini', label: 'Gemini' },
]

function handleChange(event: Event): void {
  const value = (event.target as HTMLSelectElement).value as LlmOption
  emit('update:modelValue', value)
}
</script>

<template>
  <div class="llm-select">
    <label for="llm-select" class="llm-label">LLM</label>
    <select
      id="llm-select"
      class="llm-dropdown"
      :value="modelValue"
      @change="handleChange"
      aria-label="LLM 모델 선택"
    >
      <option v-for="opt in options" :key="opt.value" :value="opt.value">
        {{ opt.label }}
      </option>
    </select>
  </div>
</template>

<style scoped>
.llm-select {
  display: flex;
  align-items: center;
  gap: 8px;
}

.llm-label {
  font-size: 13px;
  color: #5f6368;
  font-weight: 500;
}

.llm-dropdown {
  padding: 6px 12px;
  border: 1px solid #dadce0;
  border-radius: 8px;
  font-size: 13px;
  color: #202124;
  background: #fff;
  cursor: pointer;
  outline: none;
  transition: border-color 0.2s;
}

.llm-dropdown:focus {
  border-color: #4285f4;
}
</style>
