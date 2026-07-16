/**
 * SearchBar 컴포넌트 테스트.
 * 입력, 엔터 검색, 빈 값 검색 방지 검증.
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import SearchBar from './SearchBar.vue'

describe('SearchBar', () => {
  it('입력값 변경 시 update:modelValue 이벤트 방출', async () => {
    const wrapper = mount(SearchBar, {
      props: { modelValue: '' },
    })
    const input = wrapper.find('.search-input')
    await input.setValue('test query')
    expect(wrapper.emitted('update:modelValue')).toBeTruthy()
  })

  it('엔터 키 입력 시 search 이벤트 방출', async () => {
    const wrapper = mount(SearchBar, {
      props: { modelValue: 'test query' },
    })
    const input = wrapper.find('.search-input')
    await input.trigger('keydown.enter')
    expect(wrapper.emitted('search')?.[0]).toEqual(['test query'])
  })

  it('빈 값일 때 엔터 키 입력 시 search 이벤트 미방출', async () => {
    const wrapper = mount(SearchBar, {
      props: { modelValue: '' },
    })
    const input = wrapper.find('.search-input')
    await input.trigger('keydown.enter')
    expect(wrapper.emitted('search')).toBeFalsy()
  })

  it('빈 값일 때 검색 버튼 비활성화', () => {
    const wrapper = mount(SearchBar, {
      props: { modelValue: '' },
    })
    const button = wrapper.find('.search-button')
    expect(button.attributes('disabled')).toBeDefined()
  })

  it('disabled prop 전달 시 입력 비활성화', () => {
    const wrapper = mount(SearchBar, {
      props: { modelValue: 'test', disabled: true },
    })
    const input = wrapper.find('.search-input')
    expect(input.attributes('disabled')).toBeDefined()
  })
})
