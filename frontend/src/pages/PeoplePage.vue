<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue';

import { authState, isAdmin } from '../lib/auth';
import {
  createPeopleUser,
  deletePeopleUser,
  fetchPeopleRoles,
  fetchPeopleUsers,
  updatePeopleUser,
} from '../lib/backend-people';
import '../assets/people-page.css';

const users = ref([]);
const roles = ref([]);
const loading = ref(false);
const error = ref('');
const success = ref('');
const editingUserId = ref(null);
const form = reactive({
  email: '',
  password: '',
  roleName: 'User',
});

const editingUser = computed(() => users.value.find((user) => user.user_id === editingUserId.value) ?? null);
const totalUsers = computed(() => users.value.length);
const totalRoles = computed(() => roles.value.length);
const activeRoleCount = computed(() => new Set(users.value.map((user) => user.role_name)).size);

function resetForm() {
  form.email = '';
  form.password = '';
  form.roleName = roles.value[0]?.role_name ?? 'User';
}

async function loadData() {
  if (!authState.token) {
    return;
  }

  loading.value = true;
  error.value = '';

  try {
    const [userList, roleList] = await Promise.all([fetchPeopleUsers(), fetchPeopleRoles()]);
    users.value = userList;
    roles.value = roleList;

    if (!editingUserId.value && !form.roleName && roleList.length > 0) {
      form.roleName = roleList[0].role_name;
    }
  } catch (loadError) {
    error.value = loadError instanceof Error ? loadError.message : 'Failed to load people data';
  } finally {
    loading.value = false;
  }
}

watch(
  () => authState.token,
  () => {
    if (isAdmin.value) {
      void loadData();
    }
  },
);

watch(editingUser, (user) => {
  if (user) {
    form.email = user.email;
    form.password = '';
    form.roleName = user.role_name || 'User';
  }
});

onMounted(() => {
  if (isAdmin.value) {
    void loadData();
  }
});

async function handleSubmit() {
  if (!authState.token) {
    error.value = 'Missing backend session token';
    return;
  }

  loading.value = true;
  error.value = '';
  success.value = '';

  try {
    const payload = {
      email: form.email.trim(),
      password: form.password,
      role_name: form.roleName,
    };

    if (editingUserId.value) {
      await updatePeopleUser(editingUserId.value, {
        email: payload.email,
        ...(payload.password ? { password: payload.password } : {}),
        role_name: payload.role_name,
      });
      success.value = 'User updated successfully.';
    } else {
      await createPeopleUser(payload);
      success.value = 'User created successfully.';
    }

    editingUserId.value = null;
    resetForm();
    await loadData();
  } catch (submitError) {
    error.value = submitError instanceof Error ? submitError.message : 'Failed to save user';
  } finally {
    loading.value = false;
  }
}

async function handleDelete(userId) {
  const confirmed = window.confirm('Delete this user?');
  if (!confirmed) {
    return;
  }

  loading.value = true;
  error.value = '';
  success.value = '';

  try {
    await deletePeopleUser(userId);
    success.value = 'User deleted successfully.';
    if (editingUserId.value === userId) {
      editingUserId.value = null;
      resetForm();
    }
    await loadData();
  } catch (deleteError) {
    error.value = deleteError instanceof Error ? deleteError.message : 'Failed to delete user';
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <section class="page people-page">
    <div class="page__hero people-hero">
      <span class="page__kicker">People</span>
      <h1 class="page__title">People control room.</h1>
      <p class="page__copy">Manage accounts with a compact Bento layout tuned for speed, clarity, and admin-only actions.</p>
    </div>

    <template v-if="!isAdmin">
      <div class="panel people-empty-state">Only admin can access this page.</div>
    </template>

    <div v-else class="people-bento">
      <article class="people-card people-card--intro">
        <div class="people-card__header">
          <div>
            <p class="people-eyebrow">Admin overview</p>
            <h2 class="people-card__title">User governance at a glance</h2>
            <p class="people-card__copy">Browse accounts, assign roles, and keep the directory tidy without visual clutter.</p>
          </div>
          <button class="btn btn--primary people-card__button" type="button" :disabled="loading" @click="loadData">
            Refresh
          </button>
        </div>

        <div class="people-chip-row">
          <span class="people-chip">{{ totalUsers }} users</span>
          <span class="people-chip">{{ totalRoles }} roles</span>
          <span class="people-chip">{{ activeRoleCount }} active role groups</span>
        </div>
      </article>

      <article class="people-card people-card--stats">
        <div class="people-stat">
          <span class="people-stat__value">{{ totalUsers }}</span>
          <span class="people-stat__label">Users</span>
        </div>
        <div class="people-stat">
          <span class="people-stat__value">{{ totalRoles }}</span>
          <span class="people-stat__label">Roles</span>
        </div>
        <div class="people-stat">
          <span class="people-stat__value">{{ editingUserId ? '1' : '0' }}</span>
          <span class="people-stat__label">Editing</span>
        </div>
      </article>

      <article class="people-card people-card--table">
        <div class="people-section-head">
          <div>
            <h2 class="people-section-title">Users</h2>
            <p class="people-section-meta">{{ users.length }} records in the directory</p>
          </div>
          <span class="people-section-badge" :class="{ 'is-loading': loading }">{{ loading ? 'Syncing…' : 'Live' }}</span>
        </div>

        <p v-if="error" class="panel__notice notice--error people-notice">{{ error }}</p>
        <p v-if="success" class="panel__notice notice--success people-notice">{{ success }}</p>

        <div class="table-wrap people-table-wrap">
          <table class="table">
            <thead>
              <tr>
                <th>Email</th>
                <th>Role</th>
                <th>Updated</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="user in users" :key="user.user_id" :class="{ 'is-editing': user.user_id === editingUserId }">
                <td>
                  <div class="people-user-cell">
                    <span class="people-avatar">{{ user.email.slice(0, 1).toUpperCase() }}</span>
                    <span>{{ user.email }}</span>
                  </div>
                </td>
                <td><span class="people-role-pill">{{ user.role_name }}</span></td>
                <td>{{ user.updated_at ? new Date(user.updated_at).toLocaleString() : '-' }}</td>
                <td>
                  <div class="table__actions">
                    <button class="btn" type="button" @click="editingUserId = user.user_id; success = ''; error = '';">Edit</button>
                    <button class="btn btn--danger" type="button" @click="handleDelete(user.user_id)">Delete</button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>

      <article class="people-card people-card--form">
        <div class="people-section-head people-section-head--stacked">
          <div>
            <h2 class="people-section-title">{{ editingUserId ? 'Edit user' : 'Create user' }}</h2>
            <p class="people-section-meta">
              {{ editingUserId ? `Editing ${editingUser?.email ?? 'selected user'}` : 'Add a new account for any role.' }}
            </p>
          </div>
          <span class="people-section-badge people-section-badge--accent">{{ editingUserId ? 'Editing mode' : 'New account' }}</span>
        </div>

        <form class="form people-form" @submit.prevent="handleSubmit">
          <label class="label">
            <span class="label__text">Email</span>
            <input v-model="form.email" class="input" type="email" placeholder="user@example.com" autocomplete="email" required />
          </label>

          <label class="label">
            <span class="label__text">Password {{ editingUserId ? '(leave blank to keep current)' : '' }}</span>
            <input
              v-model="form.password"
              class="input"
              type="password"
              placeholder="Enter password"
              :autocomplete="editingUserId ? 'current-password' : 'new-password'"
              :required="!editingUserId"
            />
          </label>

          <label class="label">
            <span class="label__text">Role</span>
            <select v-model="form.roleName" class="select" :disabled="!roles.length">
              <option v-for="roleItem in roles" :key="roleItem.role_id" :value="roleItem.role_name">
                {{ roleItem.role_name }}
              </option>
            </select>
          </label>

          <div class="people-form-actions">
            <button class="btn btn--primary" type="submit" :disabled="loading">
              {{ editingUserId ? 'Update user' : 'Create user' }}
            </button>

            <button
              v-if="editingUserId"
              class="btn"
              type="button"
              @click="editingUserId = null; resetForm(); error = ''; success = '';"
            >
              Cancel edit
            </button>
          </div>
        </form>
      </article>

      <article class="people-card people-card--note">
        <h3 class="people-note-title">Admin notes</h3>
        <ul class="people-note-list">
          <li>Use roles to separate readers, journalists, and admins cleanly.</li>
          <li>Editing a user keeps the password blank unless you want to reset it.</li>
          <li>Cards are intentionally compact so the page feels lighter and more professional.</li>
        </ul>
      </article>
    </div>
  </section>
</template>
