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

export async function fetchAllNews() {
  try {
    return await request('/news');
  } catch (error) {
    throw new Error(parseError(error));
  }
}

export async function fetchWorkspaceNews() {
  try {
    return await request('/news/workspace');
  } catch (error) {
    throw new Error(parseError(error));
  }
}

export async function fetchNewsDetail(newsId) {
  try {
    return await request(`/news/${newsId}`);
  } catch (error) {
    throw new Error(parseError(error));
  }
}

export async function createNews(payload) {
  try {
    return await request('/news', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  } catch (error) {
    throw new Error(parseError(error));
  }
}

export async function updateNews(newsId, payload) {
  try {
    return await request(`/news/${newsId}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
  } catch (error) {
    throw new Error(parseError(error));
  }
}

export async function deleteNews(newsId) {
  try {
    return await request(`/news/${newsId}`, {
      method: 'DELETE',
    });
  } catch (error) {
    throw new Error(parseError(error));
  }
}

export async function fetchMyNewsInteractions() {
  try {
    return await request('/news/interactions/me');
  } catch (error) {
    throw new Error(parseError(error));
  }
}

export async function likeNews(newsId) {
  try {
    return await request(`/news/${newsId}/like`, {
      method: 'POST',
    });
  } catch (error) {
    throw new Error(parseError(error));
  }
}

export async function unlikeNews(newsId) {
  try {
    return await request(`/news/${newsId}/like`, {
      method: 'DELETE',
    });
  } catch (error) {
    throw new Error(parseError(error));
  }
}

export async function fetchNewsComments(newsId) {
  try {
    return await request(`/news/${newsId}/comments`);
  } catch (error) {
    throw new Error(parseError(error));
  }
}

export async function createNewsComment(newsId, payload) {
  try {
    return await request(`/news/${newsId}/comments`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  } catch (error) {
    throw new Error(parseError(error));
  }
}
