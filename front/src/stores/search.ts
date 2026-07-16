/**
 * 검색 상태 Pinia 스토어.
 * SSE 스트림의 부분결과를 점진적으로 반영하고, done 수신 시 최종값으로 확정함.
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { executeSearch } from '@/api/client'
import type { CodeExample, Source, SearchAnswer, LlmOption } from '@/api/types'

export const useSearchStore = defineStore('search', () => {
  // --- 상태 ---
  const query = ref('')
  const selectedLlm = ref<LlmOption>('auto')
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  // 부분결과 (SSE 스트리밍 중 점진 반영)
  const summary = ref('')
  const codeExamples = ref<CodeExample[]>([])
  const sources = ref<Source[]>([])
  const missingSources = ref<string[]>([])
  const usedModels = ref<Record<string, string>>({})

  // 최종 결과 확정 여부
  const isDone = ref(false)

  // 요청 취소용 AbortController
  let abortController: AbortController | null = null

  // --- Getters ---
  /** 소스를 score 내림차순으로 정렬한 목록 */
  const sortedSources = computed(() =>
    [...sources.value].sort((a, b) => b.score - a.score),
  )

  /** 검색 결과 존재 여부 */
  const hasResults = computed(() =>
    summary.value !== '' || codeExamples.value.length > 0 || sources.value.length > 0,
  )

  // --- Actions ---
  /** 상태 초기화 */
  function resetResults(): void {
    summary.value = ''
    codeExamples.value = []
    sources.value = []
    missingSources.value = []
    usedModels.value = {}
    error.value = null
    isDone.value = false
  }

  /** 진행 중인 요청 취소 */
  function cancelSearch(): void {
    if (abortController) {
      abortController.abort()
      abortController = null
    }
    isLoading.value = false
  }

  /** 검색 실행 */
  function search(searchQuery: string): void {
    // 기존 요청 취소
    cancelSearch()
    resetResults()

    query.value = searchQuery
    isLoading.value = true

    const request = {
      query: searchQuery,
      ...(selectedLlm.value !== 'auto' ? { llm: selectedLlm.value } : {}),
    } as const

    abortController = executeSearch(
      { query: request.query, llm: 'llm' in request ? request.llm : undefined },
      {
        onMissing: (missing) => {
          missingSources.value = missing
        },
        onSource: (source) => {
          sources.value = [...sources.value, source]
        },
        onSummary: (s) => {
          summary.value = s
        },
        onCode: (code) => {
          codeExamples.value = [...codeExamples.value, code]
        },
        onDone: (answer: SearchAnswer) => {
          // done 수신 시 최종 정본으로 확정
          summary.value = answer.summary
          codeExamples.value = answer.code_examples
          sources.value = answer.sources
          missingSources.value = answer.missing_sources
          usedModels.value = answer.used_models
          isDone.value = true
          isLoading.value = false
          abortController = null
        },
        onError: (err) => {
          error.value = err
          isLoading.value = false
          abortController = null
        },
      },
    )
  }

  /** 재검색 (동일 질의 재실행) */
  function retry(): void {
    if (query.value) {
      search(query.value)
    }
  }

  return {
    // state
    query,
    selectedLlm,
    isLoading,
    error,
    summary,
    codeExamples,
    sources,
    missingSources,
    usedModels,
    isDone,
    // getters
    sortedSources,
    hasResults,
    // actions
    search,
    retry,
    cancelSearch,
    resetResults,
  }
})
