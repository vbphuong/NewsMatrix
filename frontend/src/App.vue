<script setup>
import { computed } from 'vue';
import { useRoute } from 'vue-router';

import SiteShell from './components/SiteShell.vue';

const route = useRoute();
const showShell = computed(() => route.path !== '/login');
</script>

<template>
  <SiteShell v-if="showShell">
    <router-view />
  </SiteShell>

  <router-view v-else />
</template>
