<script setup>
import AuthPanel from '../components/AuthPanel.vue';

const socialProviders = {
  google: Boolean(import.meta.env.VITE_GOOGLE_CLIENT_ID && import.meta.env.VITE_GOOGLE_CLIENT_SECRET),
  github: Boolean(import.meta.env.VITE_GITHUB_ID && import.meta.env.VITE_GITHUB_SECRET),
};
</script>

<template>
  <section class="page">
    <AuthPanel :social-providers="socialProviders" />
  </section>
</template>
