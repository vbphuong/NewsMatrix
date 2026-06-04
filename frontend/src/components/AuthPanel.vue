<script setup>
import { computed, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { isAuthenticated, loginWithEmail, loginWithSocial, registerWithEmail } from '../lib/auth';
import '../assets/auth-panel.css';

const props = defineProps({
  socialProviders: {
    type: Object,
    required: true,
  },
});

const route = useRoute();
const router = useRouter();

const mode = ref('sign-in');
const email = ref('');
const password = ref('');
const loading = ref(false);
const error = ref('');
const success = ref('');

const isSignUp = computed(() => mode.value === 'sign-up');
const redirectTarget = computed(() => (typeof route.query.redirect === 'string' ? route.query.redirect : '/'));

function setMode(nextMode) {
  mode.value = nextMode;
  error.value = '';
  success.value = '';
}

async function submitEmail() {
  loading.value = true;
  error.value = '';
  success.value = '';

  try {
    if (isSignUp.value) {
      await registerWithEmail(email.value, password.value);
    } else {
      await loginWithEmail(email.value, password.value);
    }

    success.value = isSignUp.value ? 'Account created and signed in.' : 'Signed in successfully.';
    await router.push(redirectTarget.value);
  } catch (submitError) {
    error.value = submitError instanceof Error ? submitError.message : 'Authentication failed';
  } finally {
    loading.value = false;
  }
}

async function submitSocial(provider) {
  if (!email.value) {
    error.value = 'Please enter your email first.';
    return;
  }

  loading.value = true;
  error.value = '';
  success.value = '';

  try {
    await loginWithSocial(email.value, provider);
    success.value = `Signed in with ${provider}.`;
    await router.push(redirectTarget.value);
  } catch (submitError) {
    error.value = submitError instanceof Error ? submitError.message : 'Authentication failed';
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="login-layout">
    <section class="login-layout__content">
      <div class="hero-card">
        <span class="badge">NewsMatrix authentication</span>
        <div>
          <h1 class="page__title">One workspace. Every story.</h1>
          <p class="page__copy">
            Sign in with email, Google, or GitHub. Create a new account directly from the web, then keep using the same backend JWT for protected API calls.
          </p>
        </div>
      </div>

      <div class="page__grid page__grid--3">
        <div class="panel panel--soft"><h3 class="panel__title">Email login</h3><p class="panel__meta">Local signup and password-based access.</p></div>
        <div class="panel panel--soft"><h3 class="panel__title">Google</h3><p class="panel__meta">OAuth ready via backend social login.</p></div>
        <div class="panel panel--soft"><h3 class="panel__title">GitHub</h3><p class="panel__meta">Developer-friendly auth flow.</p></div>
      </div>
    </section>

    <section class="login-layout__panel panel">
      <div class="login-form-head">
        <div>
          <p class="badge">Account access</p>
          <h2 class="login-form-head__title">{{ isSignUp ? 'Create account' : 'Welcome back' }}</h2>
          <p class="muted">{{ isSignUp ? 'Join NewsMatrix today' : 'Secure JWT session' }}</p>
        </div>
      </div>

      <div class="segmented-control">
        <button type="button" :class="{ active: !isSignUp }" @click="setMode('sign-in')">Sign in</button>
        <button type="button" :class="{ active: isSignUp }" @click="setMode('sign-up')">Sign up</button>
      </div>

      <form class="form" @submit.prevent="submitEmail">
        <label class="label">
          <span class="label__text">Email</span>
          <input v-model="email" class="input" type="email" placeholder="you@example.com" autocomplete="email" required />
        </label>

        <label class="label">
          <span class="label__text">Password</span>
          <input
            v-model="password"
            class="input"
            type="password"
            placeholder="Enter a secure password"
            :autocomplete="isSignUp ? 'new-password' : 'current-password'"
            required
          />
        </label>

        <p v-if="error" class="panel__notice notice--error">{{ error }}</p>
        <p v-if="success" class="panel__notice notice--success">{{ success }}</p>

        <button class="btn btn--primary" type="submit" :disabled="loading">
          {{ loading ? 'Working...' : (isSignUp ? 'Create account' : 'Sign in') }}
        </button>
      </form>

      <div class="social-divider"><span />or continue with<span /></div>

      <div class="social-grid">
        <button class="btn" type="button" :disabled="!props.socialProviders.google" @click="submitSocial('google')">
          Continue with Google
        </button>
        <button class="btn" type="button" :disabled="!props.socialProviders.github" @click="submitSocial('github')">
          Continue with GitHub
        </button>
      </div>

      <div class="panel panel--soft login-status">
        <template v-if="isAuthenticated">
          <p class="panel__title">Signed in</p>
        </template>
        <template v-else>
          <p class="panel__meta">Use a direct account or social account to access NewsMatrix. A backend JWT is generated after sign in.</p>
        </template>
      </div>
    </section>
  </div>
</template>