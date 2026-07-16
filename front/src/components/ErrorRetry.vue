<script setup lang="ts">
/**
 * 에러 표시 + 재시도 버튼 컴포넌트.
 * 이미 받은 부분결과는 보존한 상태에서 재시도 버튼만 노출.
 */
defineProps<{
  message: string
}>()

const emit = defineEmits<{
  retry: []
}>()
</script>

<template>
  <div class="error-retry" role="alert">
    <div class="error-icon">⚠️</div>
    <p class="error-message">{{ message }}</p>
    <button class="retry-button" @click="emit('retry')">
      다시 검색
    </button>
  </div>
</template>

<style scoped>
.error-retry {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 24px;
  border: 1px solid #fce8e6;
  border-radius: 8px;
  background: #fef7f6;
  margin-bottom: 16px;
}

.error-icon {
  font-size: 32px;
  margin-bottom: 8px;
}

.error-message {
  font-size: 14px;
  color: #d93025;
  margin: 0 0 16px 0;
  text-align: center;
}

.retry-button {
  padding: 8px 24px;
  border: none;
  border-radius: 20px;
  background: #4285f4;
  color: #fff;
  font-size: 14px;
  cursor: pointer;
  transition: background 0.2s;
}

.retry-button:hover {
  background: #3367d6;
}
</style>
