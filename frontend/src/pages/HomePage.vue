<template>
  <section class="page">
    <div class="page__hero">
      <span class="page__kicker">Homepage</span>
      <h1 class="page__title">Welcome to NewsMatrix.</h1>
      <p class="page__copy">
        This is the public homepage. Use the navigation to explore News, Organization, and Category if you have access.
      </p>
    </div>

    <div class="page__grid page__grid--3">
      <div class="panel"><h2 class="panel__title">News</h2><p class="panel__meta">Public updates and stories.</p></div>
      <div class="panel"><h2 class="panel__title">Organization</h2><p class="panel__meta">Open overview for everyone.</p></div>
      <div class="panel"><h2 class="panel__title">Login</h2><p class="panel__meta">Sign in to unlock protected areas.</p></div>
    </div>

    <div class="home-images">
      <button class="btn" type="button" @click="showImages = !showImages">{{ showImages ? 'Hide' : 'Show' }} images</button>

      <div v-if="showImages" class="home-images__grid bento-grid">
        <div
          v-for="(img, idx) in images"
          :key="idx"
          class="bento-tile"
          :title="img.alt"
          @click="onImageClick(idx)"
          :style="{ backgroundImage: `url(${img.src})` }"
        >
          <span class="bento-tile__label">{{ img.alt }}</span>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { ref } from 'vue';

const showImages = ref(true);

const images = ref([
  { src: 'https://images.unsplash.com/photo-1501785888041-af3ef285b470?w=1200&q=60&auto=format&fit=crop', alt: 'Mountain' },
  { src: 'https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=1200&q=60&auto=format&fit=crop', alt: 'Ocean' },
]);

function onImageClick(idx) {
  const url = images.value[idx] && images.value[idx].src;
  if (url) window.open(url, '_blank');
}
</script>

<style scoped>
.home-images { margin-top: 1.25rem; }
.home-images .btn { margin-bottom: 0.75rem; }
.home-images__grid.bento-grid {
  display: grid;
  gap: 0.75rem;
  grid-template-columns: repeat(6, 1fr);
  grid-auto-rows: minmax(80px, 1fr);
}
.bento-tile {
  border-radius: 0.9rem;
  overflow: hidden;
  background-size: cover;
  background-position: center;
  position: relative;
  min-height: 120px;
  box-shadow: 0 12px 28px rgba(0,0,0,0.28);
  cursor: pointer;
  border: 1px solid var(--border);
}
.bento-tile__label {
  position: absolute;
  left: 0.7rem;
  bottom: 0.6rem;
  background: rgba(0,0,0,0.45);
  padding: 0.35rem 0.6rem;
  border-radius: 0.6rem;
  color: var(--text);
  font-weight: 700;
  font-size: 0.86rem;
}
.bento-tile:nth-child(1) { grid-column: span 3; grid-row: span 2; min-height: 260px; }
.bento-tile:nth-child(2) { grid-column: span 3; grid-row: span 2; min-height: 260px; }

@media (max-width: 900px) {
  .home-images__grid.bento-grid { grid-template-columns: repeat(3, 1fr); }
  .bento-tile:nth-child(1), .bento-tile:nth-child(2) { grid-column: span 3; }
}

@media (max-width: 480px) {
  .home-images__grid.bento-grid { grid-template-columns: repeat(2, 1fr); }
  .bento-tile { min-height: 140px; }
}
</style>
 