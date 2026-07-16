/**
 * Vue Router 라우트 정의.
 * / → 검색 입력 화면, /result → 결과 화면.
 */
import { createRouter, createWebHistory } from 'vue-router'
import SearchView from '@/views/SearchView.vue'
import ResultView from '@/views/ResultView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'search',
      component: SearchView,
    },
    {
      path: '/result',
      name: 'result',
      component: ResultView,
    },
  ],
})

export default router
