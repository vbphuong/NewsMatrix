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

export async function fetchOrganizations() {
  try {
    return await request('/organizations');
  } catch (error) {
    throw new Error(parseError(error));
  }
}

export async function fetchOrganizationDetail(organizationId) {
  try {
    return await request(`/organizations/${organizationId}`);
  } catch (error) {
    throw new Error(parseError(error));
  }
}

export async function fetchOrganizationJournalists(organizationId, page = 1, pageSize = 5) {
  try {
    return await request(`/organizations/${organizationId}/journalists?page=${page}&page_size=${pageSize}`);
  } catch (error) {
    throw new Error(parseError(error));
  }
}

export async function createOrganization(payload) {
  try {
    return await request('/organizations', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  } catch (error) {
    throw new Error(parseError(error));
  }
}

export async function updateOrganization(organizationId, payload) {
  try {
    return await request(`/organizations/${organizationId}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
  } catch (error) {
    throw new Error(parseError(error));
  }
}

export async function deleteOrganization(organizationId) {
  try {
    return await request(`/organizations/${organizationId}`, {
      method: 'DELETE',
    });
  } catch (error) {
    throw new Error(parseError(error));
  }
}

export async function fetchJournalistPool() {
  try {
    return await request('/organizations/journalists/pool');
  } catch (error) {
    throw new Error(parseError(error));
  }
}

export async function addJournalistToOrganization(organizationId, journalistId) {
  try {
    return await request(`/organizations/${organizationId}/journalists`, {
      method: 'POST',
      body: JSON.stringify({ journalist_id: journalistId }),
    });
  } catch (error) {
    throw new Error(parseError(error));
  }
}

export async function removeJournalistFromOrganization(organizationId, journalistId) {
  try {
    return await request(`/organizations/${organizationId}/journalists/${journalistId}`, {
      method: 'DELETE',
    });
  } catch (error) {
    throw new Error(parseError(error));
  }
}

export async function fetchMyFollowedOrganizations() {
  try {
    return await request('/organizations/following/me');
  } catch (error) {
    throw new Error(parseError(error));
  }
}

export async function followOrganization(organizationId) {
  try {
    return await request(`/organizations/${organizationId}/follow`, {
      method: 'POST',
    });
  } catch (error) {
    throw new Error(parseError(error));
  }
}

export async function unfollowOrganization(organizationId) {
  try {
    return await request(`/organizations/${organizationId}/follow`, {
      method: 'DELETE',
    });
  } catch (error) {
    throw new Error(parseError(error));
  }
}
