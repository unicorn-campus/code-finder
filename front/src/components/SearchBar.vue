<script setup lang="ts">
/**
 * 검색 입력창 컴포넌트.
 * 엔터 키 또는 검색 버튼으로 검색 실행.
 */
import { ref } from 'vue'

const props = defineProps<{
  modelValue?: string
  placeholder?: string
  disabled?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
  search: [query: string]
}>()

const inputRef = ref<HTMLInputElement | null>(null)

function handleInput(event: Event): void {
  const value = (event.target as HTMLInputElement).value
  emit('update:modelValue', value)
}

function handleSubmit(): void {
  const value = props.modelValue?.trim()
  if (value) {
    emit('search', value)
  }
}

function focus(): void {
  inputRef.value?.focus()
}

defineExpose({ focus })
</script>

<template>
  <div class="search-bar">
    <div class="search-input-wrapper">
      <svg class="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
        <circle cx="11" cy="11" r="8" />
        <line x1="21" y1="21" x2="16.65" y2="16.65" />
      </svg>
      <input
        ref="inputRef"
        type="text"
        class="search-input"
        :value="modelValue"
        :placeholder="placeholder || '학습 관련 질문을 입력하세요'"
        :disabled="disabled"
        @input="handleInput"
        @keydown.enter="handleSubmit"
        aria-label="검색 질문 입력"
      />
      <button
        class="search-button"
        :disabled="disabled || !modelValue?.trim()"
        @click="handleSubmit"
        aria-label="검색"
      >
        검색
      </button>
    </div>
  </div>
</template>

<style scoped>
.search-bar {
  width: 100%;
  max-width: 680px;
}

.search-input-wrapper {
  display: flex;
  align-items: center;
  border: 2px solid #dfe1e5;
  border-radius: 24px;
  padding: 4px 8px 4px 16px;
  background: #fff;
  transition: box-shadow 0.2s, border-color 0.2s;
}

.search-input-wrapper:focus-within {
  border-color: #4285f4;
  box-shadow: 0 1px 6px rgba(66, 133, 244, 0.28);
}

.search-icon {
  width: 20px;
  height: 20px;
  color: #9aa0a6;
  flex-shrink: 0;
  margin-right: 8px;
}

.search-input {
  flex: 1;
  border: none;
  outline: none;
  font-size: 16px;
  padding: 10px 4px;
  background: transparent;
  color: #202124;
}

.search-input::placeholder {
  color: #9aa0a6;
}

.search-button {
  flex-shrink: 0;
  padding: 8px 20px;
  border: none;
  border-radius: 20px;
  background: #4285f4;
  color: #fff;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s;
}

.search-button:hover:not(:disabled) {
  background: #3367d6;
}

.search-button:disabled {
  background: #c4c7cc;
  cursor: not-allowed;
}
</style>
