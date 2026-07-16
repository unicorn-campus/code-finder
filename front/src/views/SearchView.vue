<script setup lang="ts">
/**
 * 질문 입력 화면 — Google 검색 스타일 단일 검색창.
 * 중앙 배치, 예시 질문 칩, LLM 선택 드롭다운.
 */
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useSearchStore } from '@/stores/search'
import SearchBar from '@/components/SearchBar.vue'
import ExampleChips from '@/components/ExampleChips.vue'
import LlmSelect from '@/components/LlmSelect.vue'

const router = useRouter()
const store = useSearchStore()
const searchQuery = ref('')
const searchBarRef = ref<InstanceType<typeof SearchBar> | null>(null)

function handleSearch(query: string): void {
  store.search(query)
  router.push({ name: 'result', query: { q: query } })
}

function handleChipSelect(query: string): void {
  searchQuery.value = query
  handleSearch(query)
}

onMounted(() => {
  searchBarRef.value?.focus()
})
</script>

<template>
  <div class="search-view">
    <div class="search-container">
      <h1 class="logo">
        <span class="logo-code">Code</span><span class="logo-finder">Finder</span>
      </h1>
      <p class="tagline">학습 질문을 입력하면 핵심 내용과 예제 코드를 찾아드림</p>

      <SearchBar
        ref="searchBarRef"
        v-model="searchQuery"
        @search="handleSearch"
      />

      <div class="options-row">
        <LlmSelect v-model="store.selectedLlm" />
      </div>

      <ExampleChips @select="handleChipSelect" />
    </div>
  </div>
</template>

<style scoped>
.search-view {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: 24px;
}

.search-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
  max-width: 680px;
  margin-top: -80px;
}

.logo {
  font-size: 48px;
  font-weight: 300;
  margin: 0 0 8px 0;
  letter-spacing: -1px;
}

.logo-code {
  color: #4285f4;
}

.logo-finder {
  color: #202124;
}

.tagline {
  font-size: 14px;
  color: #5f6368;
  margin: 0 0 32px 0;
}

.options-row {
  display: flex;
  justify-content: center;
  margin-top: 16px;
}
</style>
