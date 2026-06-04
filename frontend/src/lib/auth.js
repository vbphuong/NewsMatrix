import { reactive, computed } from 'vue';

const backendBaseUrl = import.meta.env.VITE_BACKEND_URL ?? 'http://127.0.0.1:8000';
const STORAGE_KEY = 'newsmatrix-auth-session';

export const authState = reactive({
  token: '',
  role: '',
  email: '',
  hydrated: false,
});

function persistSession() {
  if (typeof window === 'undefined') {
    return;
  }

  if (authState.token) {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        token: authState.token,
        role: authState.role,
        email: authState.email,
      }),
    );
    return;
  }

  localStorage.removeItem(STORAGE_KEY);
}

export function hydrateAuth() {
  if (typeof window === 'undefined' || authState.hydrated) {
    return;
  }

  const raw = localStorage.getItem(STORAGE_KEY);
  if (raw) {
    try {
      const session = JSON.parse(raw);
      authState.token = session.token ?? '';
      authState.role = session.role ?? '';
      authState.email = session.email ?? '';
    } catch {
      localStorage.removeItem(STORAGE_KEY);
    }
  }

  authState.hydrated = true;
}

function setSession(session) {
  authState.token = session.access_token;
  authState.role = session.role;
  authState.email = session.email;
  persistSession();
}

async function postJson(path, body) {
  const response = await fetch(`${backendBaseUrl}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });

  const payload = await response.json().catch(() => null);

  if (!response.ok) {
    const detail = payload?.detail ?? 'Authentication request failed';
    throw new Error(typeof detail === 'string' ? detail : 'Authentication request failed');
  }

  return payload;
}

export async function loginWithEmail(email, password) {
  const session = await postJson('/auth/token', { email, password });
  setSession(session);
  return session;
}

export async function registerWithEmail(email, password) {
  const session = await postJson('/auth', { email, password });
  setSession(session);
  return session;
}

export async function loginWithSocial(email, provider, name = '') {
  const session = await postJson('/auth/social-login', {
    email,
    provider,
    name,
  });
  setSession(session);
  return session;
}

export function logout() {
  authState.token = '';
  authState.role = '';
  authState.email = '';
  persistSession();
}

export const isAuthenticated = computed(() => Boolean(authState.token));
export const isAdmin = computed(() => authState.role === 'Admin');
export const isJournalist = computed(() => authState.role === 'Journalist');

export function useAuth() {
  return {
    authState,
    isAuthenticated,
    isAdmin,
    isJournalist,
    hydrateAuth,
    loginWithEmail,
    registerWithEmail,
    loginWithSocial,
    logout,
  };
}
