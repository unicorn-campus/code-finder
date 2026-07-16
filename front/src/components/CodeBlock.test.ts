/**
 * CodeBlock 컴포넌트 테스트.
 * 코드 렌더링, 복사 버튼, 설명/출처 표시 검증.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import CodeBlock from './CodeBlock.vue'

// navigator.clipboard mock
const mockWriteText = vi.fn().mockResolvedValue(undefined)
Object.assign(navigator, {
  clipboard: { writeText: mockWriteText },
})

describe('CodeBlock', () => {
  const example = {
    lang: 'python',
    code: 'print("hello")',
    explain: '출력 예시',
    source: 'test.py#main#1',
  }

  beforeEach(() => {
    mockWriteText.mockClear()
  })

  it('코드 내용이 렌더링됨', () => {
    const wrapper = mount(CodeBlock, { props: { example } })
    expect(wrapper.text()).toContain('print')
    expect(wrapper.text()).toContain('hello')
  })

  it('언어 라벨이 표시됨', () => {
    const wrapper = mount(CodeBlock, { props: { example } })
    expect(wrapper.find('.code-lang').text()).toBe('python')
  })

  it('설명이 표시됨', () => {
    const wrapper = mount(CodeBlock, { props: { example } })
    expect(wrapper.find('.explain-text').text()).toBe('출력 예시')
  })

  it('출처가 표시됨', () => {
    const wrapper = mount(CodeBlock, { props: { example } })
    expect(wrapper.find('.source-ref').text()).toBe('test.py#main#1')
  })

  it('복사 버튼 클릭 시 clipboard에 코드 복사', async () => {
    const wrapper = mount(CodeBlock, { props: { example } })
    const button = wrapper.find('.copy-button')
    expect(button.text()).toBe('복사')

    await button.trigger('click')
    expect(mockWriteText).toHaveBeenCalledWith('print("hello")')
  })
})
