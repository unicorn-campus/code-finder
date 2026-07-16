<script setup lang="ts">
/**
 * 소스별 출처 카드 컴포넌트.
 * 소스 유형 배지(교재/코드/웹/영상) + score + ref/url 링크.
 */
import { computed } from 'vue'
import type { Source } from '@/api/types'

const props = defineProps<{
  source: Source
}>()

/** 소스 유형별 배지 정보 */
const badgeInfo = computed(() => {
  const map: Record<string, { emoji: string; label: string; color: string }> = {
    textbook: { emoji: '📘', label: '교재', color: '#1a73e8' },
    code: { emoji: '💻', label: '코드', color: '#0d652d' },
    web: { emoji: '🌐', label: '웹', color: '#e37400' },
    youtube: { emoji: '▶️', label: '영상', color: '#d93025' },
  }
  return map[props.source.type] || { emoji: '🔗', label: props.source.type, color: '#5f6368' }
})

/** 표시용 참조 텍스트 */
const displayRef = computed(() => {
  return props.source.url || props.source.ref || '-'
})

/** 클릭 가능 여부 */
const isLinkable = computed(() => {
  return !!props.source.url
})

/** score 퍼센트 표시 */
const scorePercent = computed(() => {
  return Math.round(props.source.score * 100)
})
</script>

<template>
  <div class="source-card">
    <div class="card-header">
      <span class="badge" :style="{ background: badgeInfo.color }">
        {{ badgeInfo.emoji }} {{ badgeInfo.label }}
      </span>
      <span class="score" :title="`관련도: ${source.score}`">
        {{ scorePercent }}%
      </span>
    </div>
    <div class="card-body">
      <a
        v-if="isLinkable"
        :href="source.url"
        target="_blank"
        rel="noopener noreferrer"
        class="source-link"
      >
        {{ displayRef }}
      </a>
      <span v-else class="source-ref">{{ displayRef }}</span>
    </div>
    <div v-if="source.fetched_at" class="card-footer">
      수집: {{ source.fetched_at }}
    </div>
  </div>
</template>

<style scoped>
.source-card {
  border: 1px solid #e8eaed;
  border-radius: 8px;
  padding: 12px;
  background: #fff;
  transition: box-shadow 0.2s;
}

.source-card:hover {
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 10px;
  border-radius: 12px;
  color: #fff;
  font-size: 12px;
  font-weight: 500;
}

.score {
  font-size: 13px;
  font-weight: 600;
  color: #5f6368;
}

.card-body {
  margin-bottom: 4px;
}

.source-link {
  font-size: 13px;
  color: #1a73e8;
  text-decoration: none;
  word-break: break-all;
}

.source-link:hover {
  text-decoration: underline;
}

.source-ref {
  font-size: 13px;
  color: #3c4043;
  font-family: monospace;
  word-break: break-all;
}

.card-footer {
  font-size: 11px;
  color: #9aa0a6;
  margin-top: 4px;
}
</style>
