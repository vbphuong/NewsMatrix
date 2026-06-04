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

export async function fetchDocuments() {
  try {
    return await request('/documents');
  } catch (error) {
    throw new Error(parseError(error));
  }
}

export async function uploadDocument(file) {
  const formData = new FormData();
  formData.append('file', file);

  try {
    const response = await fetch(`${backendBaseUrl}/documents`, {
      method: 'POST',
      headers: {
        Authorization: authState.token ? `Bearer ${authState.token}` : '',
      },
      body: formData,
    });

    const payload = await response.json().catch(() => null);

    if (!response.ok) {
      const detail = payload?.detail ?? 'Upload failed';
      throw new Error(typeof detail === 'string' ? detail : 'Upload failed');
    }

    return payload;
  } catch (error) {
    throw new Error(parseError(error));
  }
}