<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue';

import { authState, isAdmin, isAuthenticated, isJournalist } from '../lib/auth';
import { fetchCategories } from '../lib/backend-category';
import { fetchOrganizations } from '../lib/backend-organization';
import {
  createNews,
  deleteNews,
  fetchWorkspaceNews,
  updateNews,
} from '../lib/backend-news';
import '../assets/workspace-page.css';

const workspaceResponse = ref({
  has_organization: false,
  organization_id: null,
  organization_name: null,
  message: '',
  items: [],
});
const organizations = ref([]);
const categories = ref([]);
const loading = ref(false);
const error = ref('');
const success = ref('');
const editingNewsId = ref(null);

const form = reactive({
  title: '',
  content: '',
  status: 'Draft',
  organizationId: '',
  categoryIds: [],
});

const canManageNews = computed(() => isJournalist.value || isAdmin.value);
const newsItems = computed(() => workspaceResponse.value.items ?? []);
const currentOrganizationId = computed(() => workspaceResponse.value.organization_id ?? null);

const currentPage = ref(1);
const pageSize = 5;

const totalPages = computed(() => Math.ceil(newsItems.value.length / pageSize));

const paginatedNewsItems = computed(() => {
  const start = (currentPage.value - 1) * pageSize;
  return newsItems.value.slice(start, start + pageSize);
});

watch(newsItems, (newItems) => {
  const maxPage = Math.max(1, Math.ceil(newItems.length / pageSize));
  if (currentPage.value > maxPage) {
    currentPage.value = maxPage;
  }
});

function resetForm() {
  form.title = '';
  form.content = '';
  form.status = 'Draft';
  form.organizationId = currentOrganizationId.value ? String(currentOrganizationId.value) : '';
  form.categoryIds = [];
}

function populateForm(news) {
  form.title = news.title;
  form.content = news.content;
  form.status = news.status;
  form.organizationId = String(news.organization_id);
  form.categoryIds = (news.categories ?? []).map(category => String(category.category_id));
}

async function loadWorkspace() {
  loading.value = true;
  error.value = '';

  try {
    workspaceResponse.value = await fetchWorkspaceNews();
    if (!editingNewsId.value) {
      resetForm();
    }
  } catch (loadError) {
    error.value = loadError instanceof Error ? loadError.message : 'Failed to load workspace news';
  } finally {
    loading.value = false;
  }
}

async function loadOrganizations() {
  if (!isAdmin.value) {
    return;
  }

  try {
    organizations.value = await fetchOrganizations();
    if (!form.organizationId && organizations.value.length > 0) {
      form.organizationId = String(organizations.value[0].organization_id);
    }
  } catch (loadError) {
    error.value = loadError instanceof Error ? loadError.message : 'Failed to load organizations';
  }
}

async function loadCategories() {
  try {
    categories.value = await fetchCategories();
  } catch (loadError) {
    error.value = loadError instanceof Error ? loadError.message : 'Failed to load categories';
  }
}

function startEdit(news) {
  editingNewsId.value = news.news_id;
  populateForm(news);
  error.value = '';
  success.value = '';
}

function cancelEdit() {
  editingNewsId.value = null;
  resetForm();
}

async function submitNews() {
  if (!canManageNews.value) {
    return;
  }

  loading.value = true;
  error.value = '';
  success.value = '';

  const payload = {
    title: form.title.trim(),
    content: form.content.trim(),
    status: form.status,
    category_ids: form.categoryIds.map(categoryId => Number(categoryId)),
    ...(isAdmin.value ? { organization_id: Number(form.organizationId) } : {}),
  };

  try {
    if (editingNewsId.value) {
      await updateNews(editingNewsId.value, payload);
      success.value = 'News updated successfully.';
    } else {
      await createNews(payload);
      success.value = 'News created successfully.';
      currentPage.value = 1;
    }

    cancelEdit();
    await loadWorkspace();
  } catch (submitError) {
    error.value = submitError instanceof Error ? submitError.message : 'Failed to save news';
  } finally {
    loading.value = false;
  }
}

async function handleDelete(newsId) {
  if (!window.confirm('Delete this news article?')) {
    return;
  }

  loading.value = true;
  error.value = '';
  success.value = '';

  try {
    await deleteNews(newsId);
    success.value = 'News deleted successfully.';
    if (editingNewsId.value === newsId) {
      cancelEdit();
    }
    await loadWorkspace();
  } catch (deleteError) {
    error.value = deleteError instanceof Error ? deleteError.message : 'Failed to delete news';
  } finally {
    loading.value = false;
  }
}

watch(
  () => authState.token,
  () => {
    if (isAuthenticated.value) {
      void loadWorkspace();
    }
  },
);

onMounted(async () => {
  await loadWorkspace();
  await loadOrganizations();
  await loadCategories();
});
</script>

<template>
  <section class="page workspace-page">
    <div class="page__hero">
      <span class="page__kicker">Workspace</span>
      <h1 class="page__title">News workspace.</h1>
      <p class="page__copy">
        Journalists can manage news only inside their organization. If you are not assigned to any organization, the workspace stays empty.
      </p>
    </div>

    <div class="workspace-grid">
      <article class="panel panel--soft workspace-panel">
        <h2 class="panel__title">Organization scope</h2>
        <p class="panel__meta">
          <template v-if="!isAuthenticated">You need to login to access this site.</template>
          <template v-else-if="!workspaceResponse.has_organization && isJournalist">You are not assigned to any organization yet.</template>
          <template v-else-if="workspaceResponse.has_organization">Current organization: {{ workspaceResponse.organization_name }}</template>
          <template v-else>You can manage news across organizations as admin.</template>
        </p>
      </article>

      <article v-if="canManageNews && (workspaceResponse.has_organization || isAdmin)" class="panel panel--soft workspace-panel">
        <h2 class="panel__title">{{ editingNewsId ? 'Edit news' : 'Create news' }}</h2>
        <p class="panel__meta">
          {{ editingNewsId ? 'Update the selected article.' : 'Create a new article for the active organization.' }}
        </p>

        <div class="workspace-form-grid">
          <label class="label">
            <span class="label__text">Title</span>
            <input v-model="form.title" class="input" type="text" placeholder="News title" />
          </label>

          <label class="label">
            <span class="label__text">Content</span>
            <textarea v-model="form.content" class="input" rows="5" placeholder="Write the article content"></textarea>
          </label>

          <label class="label">
            <span class="label__text">Status</span>
            <select v-model="form.status" class="select">
              <option value="Draft">Draft</option>
              <option value="Published">Published</option>
            </select>
          </label>

          <label v-if="isAdmin" class="label">
            <span class="label__text">Organization</span>
            <select v-model="form.organizationId" class="select">
              <option v-for="organization in organizations" :key="organization.organization_id" :value="String(organization.organization_id)">
                {{ organization.name }}
              </option>
            </select>
          </label>

          <div class="label">
            <span class="label__text">Categories</span>
            <div class="workspace-category-picker">
              <label
                v-for="category in categories"
                :key="category.category_id"
                class="workspace-category-option"
              >
                <input
                  v-model="form.categoryIds"
                  type="checkbox"
                  :value="String(category.category_id)"
                />
                <span>{{ category.name }}</span>
              </label>
            </div>
          </div>

          <div class="workspace-form-actions">
            <button class="btn btn--primary" type="button" :disabled="loading" @click="submitNews">
              {{ editingNewsId ? 'Update news' : 'Create news' }}
            </button>
            <button v-if="editingNewsId" class="btn" type="button" @click="cancelEdit">Cancel</button>
          </div>
        </div>
      </article>

      <article class="panel panel--soft workspace-panel">
        <div style="display:flex;align-items:center;justify-content:space-between;gap:1rem;flex-wrap:wrap;">
          <div>
            <h2 class="panel__title">Workspace news</h2>
            <p class="panel__meta">{{ newsItems.length }} articles</p>
          </div>
          <button class="btn" type="button" :disabled="loading" @click="loadWorkspace">Refresh</button>
        </div>

        <p v-if="error" class="panel__notice notice--error">{{ error }}</p>
        <p v-if="success" class="panel__notice notice--success">{{ success }}</p>

        <template v-if="workspaceResponse.has_organization || isAdmin">
          <div class="workspace-news-list">
            <article v-for="news in paginatedNewsItems" :key="news.news_id" class="workspace-news-card">
              <div style="display:flex;justify-content:space-between;gap:1rem;flex-wrap:wrap;">
                <div>
                  <h3 class="panel__title">{{ news.title }}</h3>
                  <p class="panel__meta">{{ news.organization_name }} · {{ news.status }}</p>
                </div>
                <span class="badge">#{{ news.news_id }}</span>
              </div>

              <p class="panel__meta" style="color: var(--text-2); line-height: 1.6;">{{ news.content }}</p>

              <div class="workspace-authors">
                <span v-for="author in news.authors" :key="author.user_id" class="workspace-author-chip">
                  {{ author.email }}
                </span>
              </div>

              <div v-if="news.categories?.length" class="workspace-categories">
                <span v-for="category in news.categories" :key="category.category_id" class="workspace-category-chip">
                  {{ category.name }}
                </span>
              </div>

              <div v-if="canManageNews" class="workspace-form-actions">
                <button class="btn" type="button" @click="startEdit(news)">Edit</button>
                <button class="btn btn--danger" type="button" @click="handleDelete(news.news_id)">Delete</button>
              </div>
            </article>
          </div>

          <div v-if="totalPages > 1" class="workspace-pagination">
            <button class="btn" :disabled="currentPage <= 1" @click.prevent="currentPage = Math.max(1, currentPage - 1)">
              Prev
            </button>
            <span class="workspace-pagination-info">Page {{ currentPage }} / {{ totalPages }}</span>
            <button class="btn" :disabled="currentPage >= totalPages" @click.prevent="currentPage = Math.min(totalPages, currentPage + 1)">
              Next
            </button>
          </div>
        </template>

        <div v-else class="workspace-status">
          {{ workspaceResponse.message || 'You need to login to access this site.' }}
        </div>
      </article>
    </div>
  </section>
</template>
