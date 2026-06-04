<script setup>
import { onMounted, ref } from 'vue';

import {
  createCategory,
  deleteCategory,
  fetchCategories,
  updateCategory,
} from '../lib/backend-category';
import '../assets/category-page.css';

const categories = ref([]);
const loading = ref(false);
const error = ref('');
const success = ref('');

const formName = ref('');
const editingCategoryId = ref(null);

function resetForm() {
  formName.value = '';
  editingCategoryId.value = null;
}

function startEdit(category) {
  editingCategoryId.value = category.category_id;
  formName.value = category.name;
  error.value = '';
  success.value = '';
}

async function loadCategories() {
  loading.value = true;
  error.value = '';

  try {
    categories.value = await fetchCategories();
  } catch (loadError) {
    error.value = loadError instanceof Error ? loadError.message : 'Failed to load categories';
  } finally {
    loading.value = false;
  }
}

async function submitCategory() {
  const name = formName.value.trim();
  if (!name) {
    error.value = 'Category name is required';
    return;
  }

  loading.value = true;
  error.value = '';
  success.value = '';

  try {
    if (editingCategoryId.value) {
      await updateCategory(editingCategoryId.value, { name });
      success.value = 'Category updated successfully.';
    } else {
      await createCategory({ name });
      success.value = 'Category created successfully.';
    }

    resetForm();
    await loadCategories();
  } catch (submitError) {
    error.value = submitError instanceof Error ? submitError.message : 'Failed to save category';
  } finally {
    loading.value = false;
  }
}

async function handleDelete(categoryId) {
  if (!window.confirm('Delete this category?')) {
    return;
  }

  loading.value = true;
  error.value = '';
  success.value = '';

  try {
    await deleteCategory(categoryId);
    success.value = 'Category deleted successfully.';
    if (editingCategoryId.value === categoryId) {
      resetForm();
    }
    await loadCategories();
  } catch (deleteError) {
    error.value = deleteError instanceof Error ? deleteError.message : 'Failed to delete category';
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  void loadCategories();
});
</script>

<template>
  <section class="page category-page">
    <div class="page__hero">
      <span class="page__kicker">Category</span>
      <h1 class="page__title">Manage categories.</h1>
      <p class="page__copy">
        Admin can create, update, and delete categories. These categories are used when creating or editing news.
      </p>
    </div>

    <div class="category-grid">
      <article class="panel panel--soft category-panel">
        <h2 class="panel__title">{{ editingCategoryId ? 'Edit category' : 'Create category' }}</h2>
        <p class="panel__meta">Keep names short and unique so journalists can pick them quickly.</p>

        <div class="category-form">
          <label class="label">
            <span class="label__text">Category name</span>
            <input v-model="formName" class="input" type="text" placeholder="Business, Technology, Sports..." />
          </label>

          <div class="category-actions">
            <button class="btn btn--primary" type="button" :disabled="loading" @click="submitCategory">
              {{ editingCategoryId ? 'Update category' : 'Create category' }}
            </button>
            <button v-if="editingCategoryId" class="btn" type="button" @click="resetForm">Cancel</button>
          </div>
        </div>
      </article>

      <article class="panel panel--soft category-panel">
        <div style="display:flex;align-items:center;justify-content:space-between;gap:1rem;flex-wrap:wrap;">
          <div>
            <h2 class="panel__title">Category list</h2>
            <p class="panel__meta">{{ categories.length }} categories</p>
          </div>
          <button class="btn" type="button" :disabled="loading" @click="loadCategories">Refresh</button>
        </div>

        <p v-if="error" class="panel__notice notice--error">{{ error }}</p>
        <p v-if="success" class="panel__notice notice--success">{{ success }}</p>

        <div v-if="categories.length" class="category-list">
          <article v-for="category in categories" :key="category.category_id" class="category-card">
            <h3 class="category-title">{{ category.name }}</h3>
            <div class="category-actions">
              <button class="btn" type="button" @click="startEdit(category)">Edit</button>
              <button class="btn btn--danger" type="button" @click="handleDelete(category.category_id)">Delete</button>
            </div>
          </article>
        </div>

        <div v-else class="workspace-status">
          {{ loading ? 'Loading categories...' : 'No categories found yet.' }}
        </div>
      </article>
    </div>
  </section>
</template>
