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

export async function fetchCategories() {
  try {
    return await request('/categories');
  } catch (error) {
    throw new Error(parseError(error));
  }
}

export async function createCategory(payload) {
  try {
    return await request('/categories', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  } catch (error) {
    throw new Error(parseError(error));
  }
}

export async function updateCategory(categoryId, payload) {
  try {
    return await request(`/categories/${categoryId}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
  } catch (error) {
    throw new Error(parseError(error));
  }
}

export async function deleteCategory(categoryId) {
  try {
    return await request(`/categories/${categoryId}`, {
      method: 'DELETE',
    });
  } catch (error) {
    throw new Error(parseError(error));
  }
}
