/** API 모듈 진입점 — 타입과 클라이언트 re-export */
export type {
  SourceType,
  CodeExample,
  Source,
  SearchAnswer,
  SearchRequest,
  LlmOption,
  SseCallbacks,
} from './types'
export { executeSearch } from './client'
export { SseLineParser } from './sse-parser'
export type { ParsedSseEvent } from './sse-parser'
