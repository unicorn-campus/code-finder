/**
 * SSE 스트림 파서.
 * POST 요청이므로 EventSource(GET 전용) 사용 불가 — fetch + ReadableStream으로 직접 파싱.
 * 청크가 이벤트 경계(`\n\n`) 중간에 끊길 수 있으므로 라인 버퍼링 필수.
 */

export interface ParsedSseEvent {
  event: string
  data: string
}

/**
 * SSE 라인 버퍼 파서.
 * feed()로 청크를 투입하면 완성된 이벤트만 반환함.
 * 미완성 라인은 내부 버퍼에 누적 후 다음 청크에서 합산.
 */
export class SseLineParser {
  private buffer = ''
  private currentEvent = ''
  private currentData: string[] = []

  /**
   * 텍스트 청크를 투입하고 완성된 SSE 이벤트 배열을 반환함.
   */
  feed(chunk: string): ParsedSseEvent[] {
    this.buffer += chunk
    const events: ParsedSseEvent[] = []

    // 줄 단위 분리 (CR, LF, CRLF 지원)
    const lines = this.buffer.split(/\r\n|\r|\n/)
    // 마지막 요소는 미완성 라인일 수 있음 — 버퍼에 보존
    this.buffer = lines.pop() ?? ''

    for (const line of lines) {
      if (line === '') {
        // 빈 줄 = 이벤트 경계
        if (this.currentData.length > 0) {
          events.push({
            event: this.currentEvent || 'message',
            data: this.currentData.join('\n'),
          })
        }
        this.currentEvent = ''
        this.currentData = []
      } else if (line.startsWith('event:')) {
        this.currentEvent = line.slice(6).trim()
      } else if (line.startsWith('data:')) {
        this.currentData.push(line.slice(5).trim())
      }
      // id:, retry: 등 기타 필드는 무시
    }

    return events
  }

  /** 파서 상태 초기화 */
  reset(): void {
    this.buffer = ''
    this.currentEvent = ''
    this.currentData = []
  }
}
