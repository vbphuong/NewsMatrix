<script setup>
import { computed, onMounted, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';

import { isAdmin, isAuthenticated } from '../lib/auth';
import {
  createOrganization,
  deleteOrganization,
  fetchMyFollowedOrganizations,
  fetchOrganizations,
  followOrganization,
  unfollowOrganization,
  updateOrganization,
} from '../lib/backend-organization';
import '../assets/organization-page.css';

const router = useRouter();

const organizations = ref([]);
const loading = ref(false);
const error = ref('');
const success = ref('');
const editingOrganizationId = ref(null);
const followedOrganizationIds = ref(new Set());

const form = reactive({
  name: '',
  description: '',
  dailyPostLimit: 5,
  currentEditLimit: 5,
});

const editingOrganization = computed(
  () => organizations.value.find((organization) => organization.organization_id === editingOrganizationId.value) ?? null,
);

function resetForm() {
  form.name = '';
  form.description = '';
  form.dailyPostLimit = 5;
  form.currentEditLimit = 0;
}

function populateFormFromOrganization(organization) {
  form.name = organization.name;
  form.description = organization.description ?? '';
  form.dailyPostLimit = organization.daily_post_limit;
  form.currentEditLimit = organization.current_edit_limit;
}

async function loadOrganizations() {
  loading.value = true;
  error.value = '';

  try {
    organizations.value = await fetchOrganizations();
    if (isAuthenticated.value) {
      const followed = await fetchMyFollowedOrganizations();
      followedOrganizationIds.value = new Set(followed.organization_ids ?? []);
    } else {
      followedOrganizationIds.value = new Set();
    }
  } catch (loadError) {
    error.value = loadError instanceof Error ? loadError.message : 'Failed to load organizations';
  } finally {
    loading.value = false;
  }
}

function startEdit(organization) {
  editingOrganizationId.value = organization.organization_id;
  populateFormFromOrganization(organization);
  error.value = '';
  success.value = '';
}

function cancelEdit() {
  editingOrganizationId.value = null;
  resetForm();
}

async function submitOrganization() {
  loading.value = true;
  error.value = '';
  success.value = '';

  const payload = {
    name: form.name.trim(),
    description: form.description.trim(),
    daily_post_limit: Number(form.dailyPostLimit),
    current_edit_limit: Number(form.currentEditLimit),
  };

  try {
    if (editingOrganizationId.value) {
      await updateOrganization(editingOrganizationId.value, payload);
      success.value = 'Organization updated successfully.';
    } else {
      await createOrganization(payload);
      success.value = 'Organization created successfully.';
    }

    cancelEdit();
    await loadOrganizations();
  } catch (submitError) {
    error.value = submitError instanceof Error ? submitError.message : 'Failed to save organization';
  } finally {
    loading.value = false;
  }
}

async function handleDelete(organizationId) {
  if (!window.confirm('Delete this organization?')) {
    return;
  }

  loading.value = true;
  error.value = '';
  success.value = '';

  try {
    await deleteOrganization(organizationId);
    success.value = 'Organization deleted successfully.';
    if (editingOrganizationId.value === organizationId) {
      cancelEdit();
    }
    await loadOrganizations();
  } catch (deleteError) {
    error.value = deleteError instanceof Error ? deleteError.message : 'Failed to delete organization';
  } finally {
    loading.value = false;
  }
}

function openOrganization(organizationId) {
  router.push(`/organization/${organizationId}`);
}

function requireAuth() {
  if (!isAuthenticated.value) {
    window.alert('You need to login to use this feature.');
    return false;
  }
  return true;
}

async function toggleFollow(organization) {
  if (!requireAuth()) {
    return;
  }

  loading.value = true;
  error.value = '';
  success.value = '';

  try {
    const isFollowing = followedOrganizationIds.value.has(organization.organization_id);
    const response = isFollowing
      ? await unfollowOrganization(organization.organization_id)
      : await followOrganization(organization.organization_id);

    if (isFollowing) {
      followedOrganizationIds.value.delete(organization.organization_id);
      success.value = 'Unfollowed organization.';
    } else {
      followedOrganizationIds.value.add(organization.organization_id);
      success.value = 'Followed organization.';
    }

    followedOrganizationIds.value = new Set(followedOrganizationIds.value);
    organization.followers_count = response.followers_count;
  } catch (toggleError) {
    error.value = toggleError instanceof Error ? toggleError.message : 'Failed to update follow state';
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  void loadOrganizations();
});
</script>

<template>
  <section class="page organization-page">
    <div class="page__hero">
      <span class="page__kicker">Organization</span>
      <h1 class="page__title">Organizations workspace.</h1>
      <p class="page__copy">
        Admin can create, edit, and delete organizations. User and Journalist can view organization details and members.
      </p>
    </div>

    <div class="page__grid page__grid--2 organization-grid">
      <article class="panel panel--soft organization-list-panel">
        <div class="organization-panel-head">
          <div>
            <h2 class="panel__title">Organizations</h2>
            <p class="panel__meta">{{ organizations.length }} records</p>
          </div>
          <button class="btn" type="button" :disabled="loading" @click="loadOrganizations">Refresh</button>
        </div>

        <p v-if="error" class="panel__notice notice--error">{{ error }}</p>
        <p v-if="success" class="panel__notice notice--success">{{ success }}</p>

        <div class="organization-list">
          <article v-for="organization in organizations" :key="organization.organization_id" class="organization-item panel">
            <div>
              <h3 class="organization-item__title">{{ organization.name }}</h3>
              <p class="organization-item__meta">
                Daily limit: {{ organization.daily_post_limit }} | Current edit limit: {{ organization.current_edit_limit }} | Followers: {{ organization.followers_count }}
              </p>
              <p class="organization-item__desc">{{ organization.description || 'No description provided.' }}</p>
            </div>
            <div class="organization-item__actions">
              <button class="btn btn--primary" type="button" @click="openOrganization(organization.organization_id)">
                Open page
              </button>
              <button
                  class="icon-btn"
                  :class="{ 'icon-btn--active': followedOrganizationIds.has(organization.organization_id) }"
                  type="button"
                  @click="toggleFollow(organization)"
                  :aria-pressed="followedOrganizationIds.has(organization.organization_id).toString()"
                >
                  <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                    <path d="M12 2a7 7 0 100 14 7 7 0 000-14zm0 16c-4.42 0-8 1.79-8 4v2h16v-2c0-2.21-3.58-4-8-4z"/>
                  </svg>
                  <span class="tooltip">{{ followedOrganizationIds.has(organization.organization_id) ? 'Unfollow this organization' : 'Follow this organization' }}</span>
                </button>
              <template v-if="isAdmin">
                <button class="btn" type="button" @click="startEdit(organization)">Edit</button>
                <button class="btn btn--danger" type="button" @click="handleDelete(organization.organization_id)">Delete</button>
              </template>
            </div>
          </article>
        </div>
      </article>

      <article v-if="isAdmin" class="panel panel--soft organization-form-panel">
        <h2 class="panel__title">{{ editingOrganizationId ? 'Edit organization' : 'Create organization' }}</h2>
        <p class="panel__meta">
          {{ editingOrganizationId ? `Editing ${editingOrganization?.name ?? 'selected organization'}` : 'Create a new organization space.' }}
        </p>

        <form class="form" @submit.prevent="submitOrganization">
          <label class="label">
            <span class="label__text">Name</span>
            <input v-model="form.name" class="input" type="text" placeholder="Organization name" required />
          </label>

          <label class="label">
            <span class="label__text">Description</span>
            <textarea v-model="form.description" class="input organization-textarea" placeholder="Describe this organization" rows="4" />
          </label>

          <label class="label">
            <span class="label__text">Daily post limit</span>
            <input v-model.number="form.dailyPostLimit" class="input" type="number" min="1" required />
          </label>

          <label class="label">
            <span class="label__text">Current edit limit</span>
            <input v-model.number="form.currentEditLimit" class="input" type="number" min="1" required />
          </label>

          <div class="organization-form-actions">
            <button class="btn btn--primary" type="submit" :disabled="loading">
              {{ editingOrganizationId ? 'Update organization' : 'Create organization' }}
            </button>
            <button v-if="editingOrganizationId" class="btn" type="button" @click="cancelEdit">Cancel</button>
          </div>
        </form>
      </article>

      <article v-else class="panel panel--soft organization-view-panel">
        <h2 class="panel__title">Read-only access</h2>
        <p class="panel__meta">As User/Journalist, you can open each organization page to view journalist members.</p>
      </article>
    </div>
  </section>
</template>
