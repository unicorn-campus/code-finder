<script setup lang="ts">
/**
 * 핵심 요약 표시 컴포넌트.
 */
defineProps<{
  summary: string
}>()
</script>

<template>
  <section class="result-summary" aria-label="핵심 요약">
    <h2 class="section-title">핵심 요약</h2>
    <p class="summary-text">{{ summary }}</p>
  </section>
</template>

<style scoped>
.result-summary {
  margin-bottom: 24px;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: #202124;
  margin: 0 0 8px 0;
}

.summary-text {
  font-size: 15px;
  line-height: 1.6;
  color: #3c4043;
  margin: 0;
  white-space: pre-wrap;
}
</style>
