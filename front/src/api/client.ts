/**
 * 백엔드 검색 API 클라이언트.
 * POST /search → SSE 스트림을 fetch + ReadableStream으로 소비.
 * VITE_USE_MOCK=true이면 mock 스트림으로 대체.
 */

import { SseLineParser } from './sse-parser'
import { executeMockStream } from './mock'
import type { SearchRequest, SseCallbacks, CodeExample, Source, SearchAnswer } from './types'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'

/**
 * 요청 타임아웃(ms). 기본 30초.
 * 실 MAS 백엔드는 팬아웃·리랭킹·합성으로 응답이 길 수 있어 VITE_REQUEST_TIMEOUT_MS로 override 가능.
 */
const DEFAULT_TIMEOUT = Number(import.meta.env.VITE_REQUEST_TIMEOUT_MS) || 30_000

/**
 * SSE 이벤트 데이터를 파싱하고 콜백으로 분배.
 */
function dispatchEvent(eventType: string, dataStr: string, callbacks: SseCallbacks): void {
  try {
    const data = JSON.parse(dataStr)

    switch (eventType) {
      case 'missing':
        callbacks.onMissing(data.missing_sources as string[])
        break
      case 'source':
        callbacks.onSource(data as Source)
        break
      case 'summary':
        callbacks.onSummary(data.summary as string)
        break
      case 'code':
        callbacks.onCode(data as CodeExample)
        break
      case 'done':
        callbacks.onDone(data as SearchAnswer)
        break
      case 'error':
        callbacks.onError(data.error as string)
        break
    }
  } catch {
    callbacks.onError(`SSE 데이터 파싱 실패: ${dataStr}`)
  }
}

/**
 * 검색 요청 실행.
 * mock 모드 여부에 따라 mock 스트림 또는 실제 fetch SSE 스트림으로 분기.
 *
 * @returns AbortController — 호출자가 요청 취소 시 사용
 */
export function executeSearch(request: SearchRequest, callbacks: SseCallbacks): AbortController {
  const controller = new AbortController()

  if (USE_MOCK) {
    // mock 모드: 동일 계약의 mock SSE 스트림 사용
    executeMockStream(request.query, callbacks, controller.signal).catch((err) => {
      if (!controller.signal.aborted) {
        callbacks.onError(`Mock 스트림 오류: ${String(err)}`)
      }
    })
    return controller
  }

  // 실제 백엔드 SSE 스트림
  const timeoutId = setTimeout(() => controller.abort(), DEFAULT_TIMEOUT)

  const body: Record<string, unknown> = { query: request.query }
  if (request.llm) {
    body.llm = request.llm
  }

  fetch(`${API_BASE_URL}/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal: controller.signal,
  })
    .then(async (response) => {
      clearTimeout(timeoutId)

      if (!response.ok) {
        callbacks.onError(`서버 응답 오류: ${response.status} ${response.statusText}`)
        return
      }

      const reader = response.body?.getReader()
      if (!reader) {
        callbacks.onError('응답 스트림을 읽을 수 없음')
        return
      }

      const decoder = new TextDecoder()
      const parser = new SseLineParser()

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const chunk = decoder.decode(value, { stream: true })
        const events = parser.feed(chunk)

        for (const evt of events) {
          dispatchEvent(evt.event, evt.data, callbacks)
        }
      }
    })
    .catch((err) => {
      clearTimeout(timeoutId)
      if (controller.signal.aborted) {
        callbacks.onError('요청 시간 초과 (30초)')
      } else {
        callbacks.onError(`네트워크 오류: ${String(err)}`)
      }
    })

  return controller
}
