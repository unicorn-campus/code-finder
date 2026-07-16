/**
 * 백엔드 검색 API 계약 타입 정의.
 * 정본: app/common/schemas.py — 프론트는 이 계약을 그대로 소비함.
 */

/** 소스 유형 */
export type SourceType = 'textbook' | 'code' | 'web' | 'youtube'

/** 예제 코드 1건 */
export interface CodeExample {
  lang: string
  code: string
  explain: string
  source: string
}

/** 검색 출처 1건 */
export interface Source {
  type: SourceType
  ref?: string
  url?: string
  score: number
  fetched_at?: string
}

/** POST /search 최종 응답 (SSE `done` 이벤트 데이터) */
export interface SearchAnswer {
  query: string
  summary: string
  code_examples: CodeExample[]
  sources: Source[]
  missing_sources: string[]
  used_models: Record<string, string>
}

/** POST /search 요청 바디 */
export interface SearchRequest {
  query: string
  llm?: 'claude' | 'openai' | 'gemini'
}

/** LLM 선택 옵션 (UI 드롭다운용) */
export type LlmOption = 'auto' | 'claude' | 'openai' | 'gemini'

/** SSE 이벤트 콜백 */
export interface SseCallbacks {
  onMissing: (missingSources: string[]) => void
  onSource: (source: Source) => void
  onSummary: (summary: string) => void
  onCode: (code: CodeExample) => void
  onDone: (answer: SearchAnswer) => void
  onError: (error: string) => void
}
