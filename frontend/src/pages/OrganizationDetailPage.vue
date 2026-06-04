<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';

import { isAdmin } from '../lib/auth';
import {
  addJournalistToOrganization,
  fetchJournalistPool,
  fetchOrganizationDetail,
  fetchOrganizationJournalists,
  removeJournalistFromOrganization,
} from '../lib/backend-organization';
import '../assets/organization-detail-page.css';

const route = useRoute();

const organization = ref(null);
const journalistPage = ref({
  items: [],
  page: 1,
  page_size: 5,
  total: 0,
  total_pages: 1,
});
const journalistPool = ref([]);
const selectedJournalistId = ref('');

const loading = ref(false);
const error = ref('');
const success = ref('');

const organizationId = computed(() => Number(route.params.organizationId));
const availableJournalists = computed(() => journalistPool.value.filter((journalist) => journalist.organization_id !== organizationId.value));

async function loadOrganization() {
  loading.value = true;
  error.value = '';

  try {
    organization.value = await fetchOrganizationDetail(organizationId.value);
  } catch (loadError) {
    error.value = loadError instanceof Error ? loadError.message : 'Failed to load organization';
  } finally {
    loading.value = false;
  }
}

async function loadJournalists(page = 1) {
  loading.value = true;
  error.value = '';

  try {
    journalistPage.value = await fetchOrganizationJournalists(organizationId.value, page, 5);
  } catch (loadError) {
    error.value = loadError instanceof Error ? loadError.message : 'Failed to load journalists';
  } finally {
    loading.value = false;
  }
}

async function loadJournalistPool() {
  if (!isAdmin.value) {
    return;
  }

  try {
    journalistPool.value = await fetchJournalistPool();
  } catch (loadError) {
    error.value = loadError instanceof Error ? loadError.message : 'Failed to load journalist pool';
  }
}

async function addJournalist() {
  if (!selectedJournalistId.value) {
    return;
  }

  loading.value = true;
  error.value = '';
  success.value = '';

  try {
    await addJournalistToOrganization(organizationId.value, Number(selectedJournalistId.value));
    success.value = 'Journalist added to organization.';
    selectedJournalistId.value = '';
    await Promise.all([loadJournalists(journalistPage.value.page), loadJournalistPool()]);
  } catch (submitError) {
    error.value = submitError instanceof Error ? submitError.message : 'Failed to add journalist';
  } finally {
    loading.value = false;
  }
}

async function removeJournalist(journalistId) {
  if (!window.confirm('Remove this journalist from organization?')) {
    return;
  }

  loading.value = true;
  error.value = '';
  success.value = '';

  try {
    await removeJournalistFromOrganization(organizationId.value, journalistId);
    success.value = 'Journalist removed from organization.';
    await Promise.all([loadJournalists(journalistPage.value.page), loadJournalistPool()]);
  } catch (submitError) {
    error.value = submitError instanceof Error ? submitError.message : 'Failed to remove journalist';
  } finally {
    loading.value = false;
  }
}

async function bootstrap() {
  await Promise.all([loadOrganization(), loadJournalists(1)]);
  if (isAdmin.value) {
    await loadJournalistPool();
  }
}

watch(
  () => route.params.organizationId,
  () => {
    selectedJournalistId.value = '';
    success.value = '';
    void bootstrap();
  },
);

onMounted(() => {
  void bootstrap();
});
</script>

<template>
  <section class="page organization-detail-page">
    <div class="page__hero">
      <span class="page__kicker">Organization Detail</span>
      <h1 class="page__title">{{ organization?.name ?? 'Organization' }}</h1>
      <p class="page__copy">
        {{ organization?.description || 'No description provided for this organization.' }}
      </p>
    </div>

    <div class="page__grid page__grid--2 organization-detail-grid">
      <article class="panel panel--soft">
        <h2 class="panel__title">Settings snapshot</h2>
        <p class="panel__meta">Read-only for User and Journalist.</p>
        <div class="organization-kpi-grid">
          <div class="organization-kpi">
            <span class="organization-kpi__label">Daily post limit</span>
            <strong class="organization-kpi__value">{{ organization?.daily_post_limit ?? '-' }}</strong>
          </div>
          <div class="organization-kpi">
            <span class="organization-kpi__label">Current edit limit</span>
            <strong class="organization-kpi__value">{{ organization?.current_edit_limit ?? '-' }}</strong>
          </div>
          <div class="organization-kpi">
            <span class="organization-kpi__label">Journalists</span>
            <strong class="organization-kpi__value">{{ journalistPage.total }}</strong>
          </div>
          <div class="organization-kpi">
            <span class="organization-kpi__label">Followers</span>
            <strong class="organization-kpi__value">{{ organization?.followers_count ?? 0 }}</strong>
          </div>
        </div>
      </article>

      <article v-if="isAdmin" class="panel panel--soft">
        <h2 class="panel__title">Add journalist</h2>
        <p class="panel__meta">Only users with Journalist role can be assigned.</p>

        <div class="organization-assign-row">
          <select v-model="selectedJournalistId" class="select">
            <option value="">Select journalist</option>
            <option v-for="journalist in availableJournalists" :key="journalist.user_id" :value="journalist.user_id">
              {{ journalist.email }}
            </option>
          </select>
          <button class="btn btn--primary" type="button" :disabled="loading || !selectedJournalistId" @click="addJournalist">
            Add
          </button>
        </div>
      </article>

      <article class="panel panel--soft organization-journalist-panel">
        <div class="organization-panel-head">
          <div>
            <h2 class="panel__title">Journalist members</h2>
            <p class="panel__meta">Showing 5 per page</p>
          </div>
          <button class="btn" type="button" :disabled="loading" @click="loadJournalists(journalistPage.page)">Refresh</button>
        </div>

        <p v-if="error" class="panel__notice notice--error">{{ error }}</p>
        <p v-if="success" class="panel__notice notice--success">{{ success }}</p>

        <div class="table-wrap">
          <table class="table">
            <thead>
              <tr>
                <th>Email</th>
                <th v-if="isAdmin">Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!journalistPage.items.length">
                <td :colspan="isAdmin ? 2 : 1">No journalists in this organization.</td>
              </tr>
              <tr v-for="journalist in journalistPage.items" :key="journalist.user_id">
                <td>{{ journalist.email }}</td>
                <td v-if="isAdmin">
                  <button class="btn btn--danger" type="button" @click="removeJournalist(journalist.user_id)">Remove</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="organization-pagination">
          <button
            class="btn"
            type="button"
            :disabled="journalistPage.page <= 1 || loading"
            @click="loadJournalists(journalistPage.page - 1)"
          >
            Previous
          </button>
          <span class="organization-pagination__text">Page {{ journalistPage.page }} / {{ journalistPage.total_pages }}</span>
          <button
            class="btn"
            type="button"
            :disabled="journalistPage.page >= journalistPage.total_pages || loading"
            @click="loadJournalists(journalistPage.page + 1)"
          >
            Next
          </button>
        </div>
      </article>
    </div>
  </section>
</template>
