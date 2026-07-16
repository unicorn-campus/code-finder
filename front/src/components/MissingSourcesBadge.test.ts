/**
 * MissingSourcesBadge 컴포넌트 테스트.
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import MissingSourcesBadge from './MissingSourcesBadge.vue'

describe('MissingSourcesBadge', () => {
  it('missing 소스가 있으면 배지 표시', () => {
    const wrapper = mount(MissingSourcesBadge, {
      props: { missingSources: ['youtube', 'code'] },
    })
    const badges = wrapper.findAll('.missing-badge')
    expect(badges).toHaveLength(2)
    expect(badges[0].text()).toContain('영상')
    expect(badges[1].text()).toContain('코드')
  })

  it('missing 소스가 없으면 렌더링하지 않음', () => {
    const wrapper = mount(MissingSourcesBadge, {
      props: { missingSources: [] },
    })
    expect(wrapper.find('.missing-sources').exists()).toBe(false)
  })
})
