<script setup>
import { computed, ref, watch } from 'vue';
import { RouterLink, useRoute, useRouter } from 'vue-router';

import { authState, isAdmin, isAuthenticated, isJournalist, logout } from '../lib/auth';

const route = useRoute();
const router = useRouter();
const mobileMenuOpen = ref(false);

watch(
  () => route.path,
  () => {
    mobileMenuOpen.value = false;
  },
);

const canSeeWorkspace = computed(() => !authState.role || isJournalist.value || isAdmin.value);
const showPeopleAndCategory = computed(() => isAdmin.value);
const showDocumentUpload = computed(() => isAdmin.value);

const navLinks = computed(() => [
  { to: '/', label: 'Home', public: true },
  { to: '/news', label: 'News', public: true },
  { to: '/about', label: 'About', public: true },
  { to: '/organization', label: 'Organization', public: true },
  ...(canSeeWorkspace.value ? [{ to: '/workspace', label: 'Workspace', journalistOnly: true }] : []),
  ...(showDocumentUpload.value ? [{ to: '/documents', label: 'Documents', adminOnly: true }] : []),
  ...(showPeopleAndCategory.value ? [{ to: '/people', label: 'People', adminOnly: true }, { to: '/category', label: 'Category', adminOnly: true }] : []),
  { to: '/ai-assistant', label: 'AI Assistant', authOnly: true },
]);

function handleProtectedClick(link, navigate) {
  if (link.to === '/workspace' && authState.role === 'User') {
    window.alert('Workspace is available only to Journalist and Admin roles.');
    return;
  }

  if ((link.to === '/workspace' || link.to === '/ai-assistant') && !isAuthenticated.value) {
    window.alert('You need to login to access this site.');
    router.push('/login');
    return;
  }

  if ((link.to === '/people' || link.to === '/category') && !isAdmin.value) {
    window.alert('Only admin can access this page.');
    router.push('/');
    return;
  }

  if (link.to === '/documents' && !isAdmin.value) {
    window.alert('Only admin can access this page.');
    router.push('/');
    return;
  }

  navigate();
}

function handleLogout() {
  logout();
  router.push('/login');
}
</script>

<template>
  <div class="app-shell">
    <header class="app-shell__header">
      <div class="app-shell__header-inner">
        <RouterLink to="/" class="brand">
          <span class="brand__dot" />
          NewsMatrix
        </RouterLink>

        <button class="menu-button" type="button" aria-label="Open navigation menu" @click="mobileMenuOpen = true">
          <span class="menu-button__bars">
            <span />
            <span />
            <span />
          </span>
        </button>

        <nav class="nav">
          <RouterLink
            v-for="link in navLinks"
            :key="link.to"
            :to="link.to"
            custom
            v-slot="{ href, navigate, isActive }"
          >
            <a :href="href" class="nav-link" :class="{ 'nav-link--active': isActive }" @click.prevent="handleProtectedClick(link, navigate)">
              <span class="nav-link__dot" />
              <span>{{ link.label }}</span>
              <span class="nav-link__underline" />
            </a>
          </RouterLink>

          <RouterLink v-if="!isAuthenticated" to="/login" class="nav-action nav-action--gold">Login</RouterLink>
          <button v-else type="button" class="nav-action" @click="handleLogout">Logout</button>
        </nav>
      </div>
    </header>

    <div v-if="mobileMenuOpen" class="drawer">
      <button class="drawer__backdrop" type="button" aria-label="Close navigation menu" @click="mobileMenuOpen = false" />

      <aside class="drawer__panel">
        <div class="drawer__header">
          <span class="drawer__title">Menu</span>
          <button class="nav-action" type="button" @click="mobileMenuOpen = false">Close</button>
        </div>

        <nav class="drawer__nav">
          <RouterLink
            v-for="link in navLinks"
            :key="link.to"
            :to="link.to"
            custom
            v-slot="{ href, navigate, isActive }"
          >
            <a :href="href" class="nav-link" :class="{ 'nav-link--active': isActive }" @click.prevent="handleProtectedClick(link, navigate)">
              <span class="nav-link__dot" />
              <span>{{ link.label }}</span>
              <span class="nav-link__underline" />
            </a>
          </RouterLink>

          <RouterLink v-if="!isAuthenticated" to="/login" class="nav-action nav-action--gold" @click="mobileMenuOpen = false">Login</RouterLink>
          <button v-else type="button" class="nav-action" @click="handleLogout">Logout</button>
        </nav>
      </aside>
    </div>

    <main class="page--wide">
      <slot />
    </main>
  </div>
</template>
