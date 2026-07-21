<template>
  <section class="page">
    <div class="page__hero">
      <span class="page__kicker">Homepage</span>
      <h1 class="page__title">Welcome to NewsMatrix.</h1>
      <p class="page__copy">
        This is the public homepage. Use the navigation to explore News, Organization, and Category if you have access.
      </p>
    </div>

    <!-- (below-fold moved to after images to preserve original order) -->

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
    
    <!-- BELOW THE FOLD: English content (moved below images) -->
    <section class="below-fold">
      <div class="below-fold__inner">
        <h2 class="below-fold__title">Why NewsMatrix?</h2>
        <p class="below-fold__lead">NewsMatrix helps you cut through the noise. We combine curated sources, smart ranking, and fast search so you can find the stories that matter.</p>

        <div class="features-grid">
          <div class="feature-card">
            <h3>Concise Summaries</h3>
            <p>Quick article previews give you the gist so you can decide what to read next.</p>
          </div>
          <div class="feature-card">
            <h3>Filter & Follow</h3>
            <p>Follow organizations, authors, and categories to build a personalized feed.</p>
          </div>
          <div class="feature-card">
            <h3>Secure Sharing</h3>
            <p>Share insights with colleagues while keeping private content protected.</p>
          </div>
        </div>

        <div class="below-fold__cta">
          <a class="btn " href="/news">Browse Latest News</a>
          <a class="btn btn--outline" href="/organization">Explore Organizations</a>
        </div>
      </div>
    </section>

    <!-- MORE CONTENT: Popular topics, featured orgs, newsletter -->
    <section class="more-content">
      <div class="more-inner">
        <div class="more-grid">
          <div class="panel popular-topics">
            <h3 class="panel__title">Popular Topics</h3>
            <p class="panel__meta">Quick filters to help you explore trending subjects.</p>
            <div class="tags">
              <a class="tag" href="/categories/Education">Education</a>
              <a class="tag" href="/categories/Business">Business</a>
              <a class="tag" href="/categories/Local">Local</a>
              <a class="tag" href="/categories/Science">Science</a>
              <a class="tag" href="/categories/Events">Events</a>
            </div>
          </div>

          <div class="panel featured-orgs">
            <h3 class="panel__title">Featured Organizations</h3>
            <p class="panel__meta">Organizations with active coverage and followers.</p>
            <ul class="org-list">
              <li><strong>Swinburne</strong> <span class="muted">· 120 followers</span></li>
              <li><strong>Athletics Dept</strong> <span class="muted">· 300 followers</span></li>
              <li><strong>Research Centre</strong> <span class="muted">· 220 followers</span></li>
            </ul>
          </div>

          <div class="panel newsletter">
            <h3 class="panel__title">Stay Updated</h3>
            <p class="panel__meta">Subscribe for a weekly digest of top stories.</p>
            <form class="newsletter-form" @submit.prevent>
              <input class="input" type="email" placeholder="Your email address" aria-label="email" />
              <div style="height:0.5rem"></div>
              <button class="btn btn--primary" type="submit">Subscribe</button>
            </form>
          </div>
        </div>
      </div>
    </section>
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

  <style scoped>
  .below-fold { margin-top: 2rem; }
  .below-fold__inner { max-width: 1100px; margin: 0 auto; padding: 2rem; background: rgba(10,12,16,0.6); color: #e6eef8; border-radius: 10px; box-shadow: 0 6px 20px rgba(2,6,23,0.6); }
  .below-fold__title { margin: 0 0 0.5rem; font-size: 1.4rem; color: #f3f4f6 }
  .below-fold__lead { margin: 0 0 1rem; color: #cbd5e1 }
  .features-grid { display: grid; grid-template-columns: repeat(3,1fr); gap: 1rem; margin-bottom: 1rem; }
  .feature-card { padding: 1rem; background: rgba(255,255,255,0.02); border-radius: 8px; border: 1px solid rgba(255,255,255,0.03); color: #dbe7ff }
  .feature-card h3 { margin:0 0 0.5rem; color:#fff }
  .below-fold__cta { display:flex; gap:0.75rem; }
  .btn--blue { background: #2563eb; color: #fff; border-color: rgba(37,99,235,0.16); }
  .btn--blue:hover { background: #1e40af }
  .btn--blue.btn--outline { background: transparent; color: #cfe2ff; border-color: rgba(37,99,235,0.22); }

  @media (max-width: 900px) {
    .features-grid { grid-template-columns: 1fr; }
    .below-fold__cta { flex-direction:column; }
  }
  </style>

  <style scoped>
  .more-content { margin-top: 2rem; }
  .more-inner { max-width: 1100px; margin: 0 auto; }
  .more-grid { display: grid; grid-template-columns: 1fr 1fr 360px; gap: 1rem; }
  .tags { display:flex; flex-wrap:wrap; gap:0.5rem; margin-top:1rem }
  .tag { padding:0.45rem 0.7rem; border-radius:8px; background: rgba(255,255,255,0.03); color:#dbe7ff; border:1px solid rgba(255,255,255,0.03); text-decoration:none }
  .org-list { margin:0.6rem 0 0; padding:0; list-style:none; color:#dbe7ff }
  .org-list li { padding:0.45rem 0; border-bottom:1px solid rgba(255,255,255,0.02) }
  .org-list .muted { color:#9fb0d6; font-weight:600 }
  .newsletter-form { display:flex; flex-direction:column }

  @media (max-width: 900px) {
    .more-grid { grid-template-columns: 1fr; }
  }
  </style>
 