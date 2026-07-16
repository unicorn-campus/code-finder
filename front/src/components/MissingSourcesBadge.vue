<script setup lang="ts">
/**
 * 미도달 소스 배지 컴포넌트.
 * 타임아웃·실패 소스를 회색 배지로 표시.
 */
import { computed } from 'vue'

const props = defineProps<{
  missingSources: string[]
}>()

/** 소스 유형별 라벨 */
const labelMap: Record<string, string> = {
  textbook: '📘 교재',
  code: '💻 코드',
  web: '🌐 웹',
  youtube: '▶️ 영상',
}

const badges = computed(() =>
  props.missingSources.map((s) => ({
    key: s,
    label: labelMap[s] || s,
  })),
)
</script>

<template>
  <div v-if="missingSources.length > 0" class="missing-sources" aria-label="미도달 소스">
    <span class="missing-label">미도달 소스</span>
    <span
      v-for="badge in badges"
      :key="badge.key"
      class="missing-badge"
    >
      {{ badge.label }}
    </span>
  </div>
</template>

<style scoped>
.missing-sources {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 16px;
}

.missing-label {
  font-size: 13px;
  color: #9aa0a6;
  font-weight: 500;
}

.missing-badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 12px;
  border-radius: 12px;
  background: #f1f3f4;
  color: #9aa0a6;
  font-size: 12px;
}
</style>
