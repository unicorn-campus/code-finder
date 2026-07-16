/**
 * SSE 파서 단위 테스트.
 * 청크 경계 걸침·라인 버퍼링 케이스 포함.
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { SseLineParser } from './sse-parser'

describe('SseLineParser', () => {
  let parser: SseLineParser

  beforeEach(() => {
    parser = new SseLineParser()
  })

  it('완전한 단일 이벤트 파싱', () => {
    const events = parser.feed('event: summary\ndata: {"summary":"테스트"}\n\n')
    expect(events).toHaveLength(1)
    expect(events[0].event).toBe('summary')
    expect(events[0].data).toBe('{"summary":"테스트"}')
  })

  it('복수 이벤트 연속 파싱', () => {
    const events = parser.feed(
      'event: missing\ndata: {"missing_sources":["youtube"]}\n\n' +
      'event: summary\ndata: {"summary":"요약"}\n\n',
    )
    expect(events).toHaveLength(2)
    expect(events[0].event).toBe('missing')
    expect(events[1].event).toBe('summary')
  })

  it('청크 경계가 이벤트 중간에 걸치는 케이스', () => {
    // 첫 청크: 이벤트 미완성
    const events1 = parser.feed('event: source\nda')
    expect(events1).toHaveLength(0)

    // 두 번째 청크: 나머지 데이터 + 이벤트 종료
    const events2 = parser.feed('ta: {"type":"web","score":0.8}\n\n')
    expect(events2).toHaveLength(1)
    expect(events2[0].event).toBe('source')
    const data = JSON.parse(events2[0].data)
    expect(data.type).toBe('web')
    expect(data.score).toBe(0.8)
  })

  it('청크 경계가 \\n\\n 중간에 걸치는 케이스', () => {
    // 첫 청크: data 줄 끝 줄바꿈 1개까지
    const events1 = parser.feed('event: done\ndata: {"query":"q"}\n')
    expect(events1).toHaveLength(0)

    // 두 번째 청크: 빈 줄(이벤트 경계)
    const events2 = parser.feed('\n')
    expect(events2).toHaveLength(1)
    expect(events2[0].event).toBe('done')
  })

  it('event 필드 없는 이벤트는 message로 기본 지정', () => {
    const events = parser.feed('data: {"test":true}\n\n')
    expect(events).toHaveLength(1)
    expect(events[0].event).toBe('message')
  })

  it('CRLF 줄바꿈 지원', () => {
    const events = parser.feed('event: code\r\ndata: {"lang":"python"}\r\n\r\n')
    expect(events).toHaveLength(1)
    expect(events[0].event).toBe('code')
  })

  it('data가 여러 줄인 경우 줄바꿈으로 결합', () => {
    const events = parser.feed('event: test\ndata: line1\ndata: line2\n\n')
    expect(events).toHaveLength(1)
    expect(events[0].data).toBe('line1\nline2')
  })

  it('reset() 호출 후 상태 초기화', () => {
    parser.feed('event: incomplete\ndata: ')
    parser.reset()
    const events = parser.feed('event: fresh\ndata: {"ok":true}\n\n')
    expect(events).toHaveLength(1)
    expect(events[0].event).toBe('fresh')
  })

  it('빈 data 이벤트는 무시', () => {
    const events = parser.feed('\n\n')
    expect(events).toHaveLength(0)
  })
})
