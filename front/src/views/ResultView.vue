<script setup lang="ts">
/**
 * 검색 결과 화면.
 * SSE 부분결과를 순차 렌더하고 done 수신 시 최종값으로 확정.
 * 렌더 순서: 질문 에코 → 핵심 요약 → 예제 코드 → 출처 카드 → 미도달 소스.
 */
import { ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useSearchStore } from '@/stores/search'
import SearchBar from '@/components/SearchBar.vue'
import LlmSelect from '@/components/LlmSelect.vue'
import ResultSummary from '@/components/ResultSummary.vue'
import CodeBlock from '@/components/CodeBlock.vue'
import SourceCard from '@/components/SourceCard.vue'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import ErrorRetry from '@/components/ErrorRetry.vue'
import MissingSourcesBadge from '@/components/MissingSourcesBadge.vue'

const route = useRoute()
const router = useRouter()
const store = useSearchStore()
const searchQuery = ref((route.query.q as string) || '')

function handleSearch(query: string): void {
  searchQuery.value = query
  store.search(query)
  router.replace({ name: 'result', query: { q: query } })
}

function handleRetry(): void {
  store.retry()
}

onMounted(() => {
  const q = route.query.q as string
  if (q && !store.hasResults && !store.isLoading) {
    searchQuery.value = q
    store.search(q)
  }
})

// URL 쿼리 파라미터 변경 감지
watch(
  () => route.query.q,
  (newQ) => {
    if (newQ && typeof newQ === 'string' && newQ !== store.query) {
      searchQuery.value = newQ
      store.search(newQ)
    }
  },
)
</script>

<template>
  <div class="result-view">
    <!-- 상단 검색바 -->
    <header class="result-header">
      <button class="logo-link" @click="router.push({ name: 'search' })">
        <span class="logo-small">
          <span class="logo-code">Code</span><span class="logo-finder">Finder</span>
        </span>
      </button>
      <div class="header-search">
        <SearchBar
          v-model="searchQuery"
          @search="handleSearch"
          :disabled="store.isLoading"
        />
      </div>
      <div class="header-options">
        <LlmSelect v-model="store.selectedLlm" />
      </div>
    </header>

    <!-- 결과 영역 -->
    <main class="result-content" aria-live="polite" aria-atomic="false">
      <!-- 질문 에코 -->
      <div v-if="store.query" class="query-echo">
        <span class="query-label">질문</span>
        <span class="query-text">{{ store.query }}</span>
      </div>

      <!-- 에러 (부분결과 보존) -->
      <ErrorRetry
        v-if="store.error"
        :message="store.error"
        @retry="handleRetry"
      />

      <!-- 로딩 (부분결과 미도착 시 스켈레톤) -->
      <LoadingSkeleton
        v-if="store.isLoading && !store.hasResults"
      />

      <!-- 핵심 요약 -->
      <ResultSummary
        v-if="store.summary"
        :summary="store.summary"
      />

      <!-- 예제 코드 -->
      <section v-if="store.codeExamples.length > 0" class="code-section" aria-label="예제 코드">
        <h2 class="section-title">예제 코드</h2>
        <CodeBlock
          v-for="(example, idx) in store.codeExamples"
          :key="idx"
          :example="example"
        />
      </section>

      <!-- 출처 카드 (score 내림차순) -->
      <section v-if="store.sortedSources.length > 0" class="sources-section" aria-label="검색 출처">
        <h2 class="section-title">출처</h2>
        <div class="sources-grid">
          <SourceCard
            v-for="(source, idx) in store.sortedSources"
            :key="idx"
            :source="source"
          />
        </div>
      </section>

      <!-- 미도달 소스 -->
      <MissingSourcesBadge :missing-sources="store.missingSources" />

      <!-- 로딩 중 부분결과와 함께 표시되는 진행 상태 -->
      <div v-if="store.isLoading && store.hasResults" class="partial-loading">
        <span class="loading-dot"></span>
        추가 결과 수신 중...
      </div>
    </main>
  </div>
</template>

<style scoped>
.result-view {
  min-height: 100vh;
  background: #fff;
}

.result-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 24px;
  border-bottom: 1px solid #e8eaed;
  flex-wrap: wrap;
}

.logo-link {
  border: none;
  background: none;
  cursor: pointer;
  padding: 0;
}

.logo-small {
  font-size: 22px;
  font-weight: 300;
  white-space: nowrap;
}

.logo-code {
  color: #4285f4;
}

.logo-finder {
  color: #202124;
}

.header-search {
  flex: 1;
  min-width: 200px;
}

.header-options {
  flex-shrink: 0;
}

.result-content {
  max-width: 800px;
  margin: 0 auto;
  padding: 24px;
}

.query-echo {
  margin-bottom: 24px;
  padding: 12px 16px;
  background: #f8f9fa;
  border-radius: 8px;
}

.query-label {
  font-size: 12px;
  font-weight: 600;
  color: #9aa0a6;
  margin-right: 8px;
  text-transform: uppercase;
}

.query-text {
  font-size: 16px;
  color: #202124;
  font-weight: 500;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: #202124;
  margin: 0 0 12px 0;
}

.code-section {
  margin-bottom: 24px;
}

.sources-section {
  margin-bottom: 24px;
}

.sources-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 12px;
}

.partial-loading {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 0;
  color: #9aa0a6;
  font-size: 13px;
}

.loading-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #4285f4;
  animation: pulse 1s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 0.4; }
  50% { opacity: 1; }
}
</style>
