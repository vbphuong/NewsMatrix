import { authState } from './auth';

const backendBaseUrl = import.meta.env.VITE_BACKEND_URL ?? 'http://127.0.0.1:8000';

function parseError(error) {
  if (error instanceof Error) {
    return error.message;
  }

  return 'Request failed';
}

async function requestFormData(path, options = {}) {
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

export async function chatWithAssistant(message, imageFile = null) {
  try {
    const formData = new FormData();
    formData.append('message', message);
    if (imageFile) {
      formData.append('image', imageFile);
    }
    return await requestFormData('/assistant/chat', {
      method: 'POST',
      body: formData,
    });
  } catch (error) {
    throw new Error(parseError(error));
  }
}
