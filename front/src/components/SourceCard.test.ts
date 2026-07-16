/**
 * SourceCard 컴포넌트 테스트.
 * 배지, score, ref/url 링크 렌더 검증.
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import SourceCard from './SourceCard.vue'

describe('SourceCard', () => {
  it('교재 소스 배지가 올바르게 표시됨', () => {
    const wrapper = mount(SourceCard, {
      props: {
        source: { type: 'textbook', ref: 'ent_test', score: 0.91 },
      },
    })
    expect(wrapper.find('.badge').text()).toContain('교재')
    expect(wrapper.find('.score').text()).toBe('91%')
  })

  it('웹 소스는 URL 링크로 렌더됨', () => {
    const wrapper = mount(SourceCard, {
      props: {
        source: { type: 'web', url: 'https://example.com', score: 0.75, fetched_at: '2026-07-16T00:00:00Z' },
      },
    })
    const link = wrapper.find('.source-link')
    expect(link.exists()).toBe(true)
    expect(link.attributes('href')).toBe('https://example.com')
    expect(link.attributes('target')).toBe('_blank')
  })

  it('영상 소스 배지가 올바르게 표시됨', () => {
    const wrapper = mount(SourceCard, {
      props: {
        source: { type: 'youtube', url: 'https://youtu.be/test', score: 0.65 },
      },
    })
    expect(wrapper.find('.badge').text()).toContain('영상')
  })

  it('코드 소스는 ref 텍스트로 표시됨 (링크 아님)', () => {
    const wrapper = mount(SourceCard, {
      props: {
        source: { type: 'code', ref: 'test.py#func#10', score: 0.88 },
      },
    })
    expect(wrapper.find('.source-link').exists()).toBe(false)
    expect(wrapper.find('.source-ref').text()).toBe('test.py#func#10')
  })

  it('fetched_at이 있으면 수집 시각 표시', () => {
    const wrapper = mount(SourceCard, {
      props: {
        source: { type: 'web', url: 'https://example.com', score: 0.5, fetched_at: '2026-07-16T00:00:00Z' },
      },
    })
    expect(wrapper.find('.card-footer').text()).toContain('2026-07-16')
  })
})
