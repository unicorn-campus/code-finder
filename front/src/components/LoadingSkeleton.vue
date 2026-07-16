<script setup lang="ts">
/**
 * 로딩 스켈레톤 컴포넌트.
 * 검색 결과 로딩 중 표시되는 플레이스홀더.
 */
</script>

<template>
  <div class="loading-skeleton" aria-busy="true" aria-label="검색 결과 로딩 중">
    <div class="skeleton-section">
      <div class="skeleton-title shimmer"></div>
      <div class="skeleton-line shimmer"></div>
      <div class="skeleton-line shimmer" style="width: 80%"></div>
    </div>
    <div class="skeleton-section">
      <div class="skeleton-title shimmer" style="width: 40%"></div>
      <div class="skeleton-code shimmer"></div>
    </div>
    <div class="skeleton-section">
      <div class="skeleton-title shimmer" style="width: 30%"></div>
      <div class="skeleton-cards">
        <div class="skeleton-card shimmer"></div>
        <div class="skeleton-card shimmer"></div>
        <div class="skeleton-card shimmer"></div>
      </div>
    </div>
    <p class="loading-text">검색 결과를 가져오는 중...</p>
  </div>
</template>

<style scoped>
.loading-skeleton {
  max-width: 800px;
  margin: 0 auto;
  padding: 24px 0;
}

.skeleton-section {
  margin-bottom: 24px;
}

.skeleton-title {
  height: 20px;
  width: 50%;
  border-radius: 4px;
  margin-bottom: 12px;
}

.skeleton-line {
  height: 14px;
  width: 100%;
  border-radius: 4px;
  margin-bottom: 8px;
}

.skeleton-code {
  height: 120px;
  width: 100%;
  border-radius: 8px;
}

.skeleton-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}

.skeleton-card {
  height: 80px;
  border-radius: 8px;
}

.shimmer {
  background: linear-gradient(
    90deg,
    #f0f0f0 25%,
    #e0e0e0 50%,
    #f0f0f0 75%
  );
  background-size: 200% 100%;
  animation: shimmer 1.5s ease-in-out infinite;
}

@keyframes shimmer {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}

.loading-text {
  text-align: center;
  color: #9aa0a6;
  font-size: 14px;
  margin-top: 16px;
}
</style>
