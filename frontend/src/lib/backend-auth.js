const backendBaseUrl = import.meta.env.VITE_BACKEND_URL ?? 'http://127.0.0.1:8000';

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
    const detail = payload?.detail ?? 'Request failed';
    throw new Error(typeof detail === 'string' ? detail : 'Request failed');
  }

  return payload;
}

export function loginWithEmail(email, password) {
  return postJson('/auth/token', { email, password });
}

export function registerWithEmail(email, password) {
  return postJson('/auth', { email, password });
}

export function loginWithSocial(email, provider, name = '') {
  return postJson('/auth/social-login', {
    email,
    provider,
    name,
  });
}
