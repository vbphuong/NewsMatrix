<script setup>
import '../assets/about-page.css';
import { ref, computed } from 'vue';

const values = [
  {
    title: 'Credible reporting',
    desc: 'Editorial workflows are built to prioritize clarity, context, and source integrity.',
  },
  {
    title: 'Collaborative newsroom',
    desc: 'Writers, editors, and admins share one workspace with role-aware access control.',
  },
  {
    title: 'Secure by default',
    desc: 'Authentication and role-based permissions keep the platform safe and accountable.',
  },
];

const timeline = [
  ['Phase 1', 'Core authentication and role model'],
  ['Phase 2', 'News and organization management'],
  ['Phase 3', 'AI assistant and workflow optimization'],
];

// User inputs for the assignment requirement
const firstName = ref('');
const lastName = ref('');
const selectedImage = ref('mountain');

const welcomeMessage = computed(() => {
  if (!firstName.value && !lastName.value) return '';
  return `${firstName.value} ${lastName.value}`.trim();
});
</script>

<template>
  <section class="page about-page">
    <div class="page__hero about-hero">
      <span class="page__kicker">About NewsMatrix</span>
      <h1 class="page__title">A newsroom platform designed for speed, trust, and teamwork.</h1>
      <p class="page__copy">
        NewsMatrix helps teams publish reliable content with a modern, role-aware workflow.
        This page gives a quick overview of what the platform stands for and where it is heading.
      </p>
    </div>

    <article class="about-card about-card--user">
      <h2 class="about-card__title">Try it out</h2>
      <p class="about-card__copy">Enter your name and choose an image to see interactive bindings.</p>

      <div class="about-user-form">
        <input class="input" placeholder="First name" v-model="firstName" />
        <input class="input" placeholder="Last name" v-model="lastName" />
      </div>

      <p v-if="welcomeMessage">Hello, {{ welcomeMessage }}!</p>

      <div class="about-image-thumbs" role="tablist">
        <button type="button" class="thumb" :class="{ active: selectedImage === 'mountain' }" @click="selectedImage = 'mountain'">
          <img src="https://images.unsplash.com/photo-1501785888041-af3ef285b470?w=400&q=60&auto=format&fit=crop" alt="Mountain" />
          <span class="muted">Mountain</span>
        </button>
        <button type="button" class="thumb" :class="{ active: selectedImage === 'ocean' }" @click="selectedImage = 'ocean'">
          <img src="https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=400&q=60&auto=format&fit=crop" alt="Ocean" />
          <span class="muted">Ocean</span>
        </button>
      </div>

      <div class="about-user-image-wrap">
        <img v-if="selectedImage === 'mountain'" class="about-user-image" src="https://images.unsplash.com/photo-1501785888041-af3ef285b470?w=1200&q=60&auto=format&fit=crop" alt="Mountain" />
        <img v-else class="about-user-image" src="https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=1200&q=60&auto=format&fit=crop" alt="Ocean" />
      </div>
    </article>

    <div class="about-bento">
      <article class="about-card about-card--statement">
        <h2 class="about-card__title">Our mission</h2>
        <p class="about-card__copy">
          Build a practical content system where quality journalism and clean engineering meet.
          From account management to publishing flow, every screen aims to reduce friction.
        </p>
      </article>

      <article class="about-card about-card--metrics">
        <div class="about-metric">
          <span class="about-metric__value">3</span>
          <span class="about-metric__label">Core roles</span>
        </div>
        <div class="about-metric">
          <span class="about-metric__value">1</span>
          <span class="about-metric__label">Unified workspace</span>
        </div>
        <div class="about-metric">
          <span class="about-metric__value">24/7</span>
          <span class="about-metric__label">Availability mindset</span>
        </div>
      </article>

      <article class="about-card about-card--values">
        <h2 class="about-card__title">What we value</h2>
        <div class="about-value-grid">
          <div v-for="value in values" :key="value.title" class="about-value-item">
            <h3>{{ value.title }}</h3>
            <p>{{ value.desc }}</p>
          </div>
        </div>
      </article>

      <article class="about-card about-card--timeline">
        <h2 class="about-card__title">Roadmap snapshot</h2>
        <ul class="about-timeline">
          <li v-for="([phase, detail]) in timeline" :key="phase">
            <strong>{{ phase }}</strong>
            <span>{{ detail }}</span>
          </li>
        </ul>
      </article>
    </div>
  </section>
</template>


<style scoped>
.about-user-form { margin: 1rem 0; display: flex; gap: 0.6rem; }
.about-user-form input { margin: 0; flex: 1 1 0; min-width: 0; }
</style>
