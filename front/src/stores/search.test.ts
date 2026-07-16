/**
 * Pinia 검색 스토어 단위 테스트.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useSearchStore } from './search'

// mock: executeSearch
vi.mock('@/api/client', () => ({
  executeSearch: vi.fn((_request, callbacks) => {
    const controller = new AbortController()
    // 비동기 mock 이벤트 방출
    setTimeout(() => {
      callbacks.onMissing(['youtube'])
      callbacks.onSource({ type: 'textbook', ref: 'ent_test', score: 0.9 })
      callbacks.onSummary('테스트 요약')
      callbacks.onCode({ lang: 'python', code: 'print("hi")', explain: '출력 예시', source: 'test.py#main#1' })
      callbacks.onDone({
        query: 'test',
        summary: '최종 요약',
        code_examples: [{ lang: 'python', code: 'print("hi")', explain: '출력 예시', source: 'test.py#main#1' }],
        sources: [{ type: 'textbook', ref: 'ent_test', score: 0.9 }],
        missing_sources: ['youtube'],
        used_models: { summary: 'claude' },
      })
    }, 10)
    return controller
  }),
}))

describe('useSearchStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('초기 상태 확인', () => {
    const store = useSearchStore()
    expect(store.query).toBe('')
    expect(store.isLoading).toBe(false)
    expect(store.error).toBeNull()
    expect(store.summary).toBe('')
    expect(store.codeExamples).toEqual([])
    expect(store.sources).toEqual([])
    expect(store.missingSources).toEqual([])
    expect(store.isDone).toBe(false)
    expect(store.hasResults).toBe(false)
  })

  it('search() 호출 시 로딩 상태로 전환', () => {
    const store = useSearchStore()
    store.search('test query')
    expect(store.query).toBe('test query')
    expect(store.isLoading).toBe(true)
  })

  it('search() 완료 시 done 이벤트로 최종 확정', async () => {
    const store = useSearchStore()
    store.search('test')

    // mock 콜백 비동기 완료 대기
    await new Promise((resolve) => setTimeout(resolve, 50))

    expect(store.isDone).toBe(true)
    expect(store.isLoading).toBe(false)
    expect(store.summary).toBe('최종 요약')
    expect(store.codeExamples).toHaveLength(1)
    expect(store.sources).toHaveLength(1)
    expect(store.missingSources).toEqual(['youtube'])
    expect(store.usedModels).toEqual({ summary: 'claude' })
    expect(store.hasResults).toBe(true)
  })

  it('resetResults()로 결과 초기화', () => {
    const store = useSearchStore()
    store.search('test')
    store.resetResults()
    expect(store.summary).toBe('')
    expect(store.codeExamples).toEqual([])
    expect(store.sources).toEqual([])
    expect(store.error).toBeNull()
    expect(store.isDone).toBe(false)
  })

  it('sortedSources는 score 내림차순', async () => {
    const store = useSearchStore()
    // 직접 상태 설정
    store.sources = [
      { type: 'web', score: 0.5, url: 'https://example.com' },
      { type: 'textbook', ref: 'test', score: 0.9 },
      { type: 'code', ref: 'code.py', score: 0.7 },
    ]
    const sorted = store.sortedSources
    expect(sorted[0].score).toBe(0.9)
    expect(sorted[1].score).toBe(0.7)
    expect(sorted[2].score).toBe(0.5)
  })

  it('selectedLlm 기본값은 auto', () => {
    const store = useSearchStore()
    expect(store.selectedLlm).toBe('auto')
  })
})
