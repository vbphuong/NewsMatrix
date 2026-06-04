import { authState } from './auth';

const backendBaseUrl = import.meta.env.VITE_BACKEND_URL ?? 'http://127.0.0.1:8000';

function parseError(error) {
  if (error instanceof Error) {
    return error.message;
  }

  return 'Request failed';
}

async function request(path, options = {}) {
  const response = await fetch(`${backendBaseUrl}${path}`, {
    ...options,
    headers: {
      Authorization: authState.token ? `Bearer ${authState.token}` : '',
      'Content-Type': 'application/json',
      ...(options.headers ?? {}),
    },
  });

  const payload = await response.json().catch(() => null);

  if (!response.ok) {
    const detail = payload?.detail ?? 'Request failed';
    throw new Error(typeof detail === 'string' ? detail : 'Request failed');
  }

  return payload;
}

export async function fetchPeopleUsers() {
  try {
    return await request('/people/users');
  } catch (error) {
    throw new Error(parseError(error));
  }
}

export async function fetchPeopleRoles() {
  try {
    return await request('/people/roles');
  } catch (error) {
    throw new Error(parseError(error));
  }
}

export async function createPeopleUser(payload) {
  try {
    return await request('/people/users', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  } catch (error) {
    throw new Error(parseError(error));
  }
}

export async function updatePeopleUser(userId, payload) {
  try {
    return await request(`/people/users/${userId}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
  } catch (error) {
    throw new Error(parseError(error));
  }
}

export async function deletePeopleUser(userId) {
  try {
    await request(`/people/users/${userId}`, {
      method: 'DELETE',
    });
  } catch (error) {
    throw new Error(parseError(error));
  }
}
