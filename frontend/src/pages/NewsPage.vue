<script setup>
import { computed, onMounted, ref, onUnmounted, watchEffect } from 'vue';
import { useRouter } from 'vue-router';

import { isAuthenticated } from '../lib/auth';
import {
  fetchAllNews,
  fetchMyNewsInteractions,
  likeNews,
  unlikeNews,
} from '../lib/backend-news';
import localNews from '../data/news.json';
import {
  followOrganization,
  unfollowOrganization,
} from '../lib/backend-organization';
import '../assets/news-page.css';

const router = useRouter();

const newsResponse = ref({ items: [] });
const likedNewsIds = ref(new Set());
const followedOrganizationIds = ref(new Set());
const loading = ref(false);
const error = ref('');
const success = ref('');

// Search & pagination
const searchQuery = ref('');
const filterCategory = ref('');
const filterDate = ref('');
const currentPage = ref(1);
const pageSize = ref(5);
// Data source selection: 'system' (database), 'mock' (local JSON), 'external' (external API)
const dataSource = ref('mock');
const externalApiUrl = ref(
  'https://gnews.io/api/v4/top-headlines?lang=en&max=15&token=a8e30c0316454ad2ea9051b7024997c7'
);
let externalRefreshInterval = null;

const newsItems = computed(() => newsResponse.value.items ?? []);

const availableCategories = computed(() => {
  const set = new Set();
  (newsItems.value || []).forEach(n => {
    if (n.category) {
      set.add(n.category);
    }
    if (n.categories && Array.isArray(n.categories)) {
      n.categories.forEach(cat => {
        if (cat && cat.name) {
          set.add(cat.name);
        }
      });
    }
  });
  return Array.from(set).filter(Boolean);
});

const filteredNewsItems = computed(() => {
  const q = (searchQuery.value || '').toLowerCase();
  return (newsItems.value || []).filter(n => {
    if (filterCategory.value) {
      const matchesCategory = n.category === filterCategory.value || 
                              (n.categories && n.categories.some(cat => cat.name === filterCategory.value));
      if (!matchesCategory) return false;
    }
    if (filterDate.value) {
      const nd = n.published_at ? new Date(n.published_at).toISOString().slice(0,10) : '';
      if (nd !== filterDate.value) return false;
    }
    if (!q) return true;
    return (
      (n.title || '').toLowerCase().includes(q) ||
      (n.content || '').toLowerCase().includes(q) ||
      (n.category || '').toLowerCase().includes(q) ||
      (n.categories && n.categories.some(cat => (cat.name || '').toLowerCase().includes(q))) ||
      (n.published_at || '').toLowerCase().includes(q)
    );
  });
});

const paginatedItems = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value;
  return filteredNewsItems.value.slice(start, start + pageSize.value);
});

async function loadNews() {
  loading.value = true;
  error.value = '';
  success.value = '';

  try {
    let response = { items: [] };

    if (dataSource.value === 'system') {
      // fetch from backend API
      const backendResp = await fetchAllNews();
      response = backendResp || { items: [] };
    } else if (dataSource.value === 'external') {
      // call external API URL if provided
      if (!externalApiUrl.value) {
        throw new Error('External API URL is not set');
      }
      const r = await fetch(externalApiUrl.value);
      if (!r.ok) throw new Error(`External API error: ${r.status}`);
      const json = await r.json();
      // Many news APIs return { articles: [...] }
      const articles = Array.isArray(json) ? json : (json.articles || json.items || []);

      // map external articles to internal news item shape
      response.items = (articles || []).map((a, idx) => ({
        news_id: `ext-${Date.now()}-${idx}`,
        title: a.title || a.heading || '',
        content: a.description || a.content || '',
        organization_name: (a.source && a.source.name) || a.source || '',
        published_at: a.publishedAt || a.published_at || a.published_at || a.publishedAt || null,
        like_count: 0,
        comment_count: 0,
        organization_followers_count: 0,
        authors: a.author ? [{ user_id: `ext-a-${idx}`, email: a.author }] : [],
        categories: a.category ? [{ category_id: `ext-c-${idx}`, name: a.category }] : [],
        image_url: a.image || a.urlToImage || a.thumbnail || null,
        external_url: a.url || a.link || null,
        status: 'published',
      }));
    } else {
      // mock local JSON
      response = { items: Array.isArray(localNews) ? localNews : [] };
    }

    newsResponse.value = {
      ...response,
      items: (response.items ?? []).filter(
        news => news.status?.toLowerCase() !== 'draft'
      )
    };

    if (isAuthenticated.value) {
      const interactions = await fetchMyNewsInteractions();
      likedNewsIds.value = new Set(interactions.liked_news_ids ?? []);
      followedOrganizationIds.value = new Set(interactions.followed_organization_ids ?? []);
    } else {
      likedNewsIds.value = new Set();
      followedOrganizationIds.value = new Set();
    }
  } catch (loadError) {
    error.value = loadError instanceof Error ? loadError.message : 'Failed to load news';
  } finally {
    loading.value = false;
  }
}

function openNewsDetail(newsId) {
  const item = (newsItems.value || []).find(n => String(n.news_id) === String(newsId));
  if (item && item.external_url) {
    window.open(item.external_url, '_blank');
    return;
  }
  router.push(`/news/${newsId}`);
}

function requireAuth() {
  if (!isAuthenticated.value) {
    window.alert('You need to login to use this feature.');
    return false;
  }
  return true;
}

async function handleLike(news, event) {
  event.stopPropagation();
  if (!requireAuth()) {
    return;
  }

  error.value = '';
  success.value = '';

  try {
    const hasLiked = likedNewsIds.value.has(news.news_id);
    const response = hasLiked ? await unlikeNews(news.news_id) : await likeNews(news.news_id);

    if (hasLiked) {
      likedNewsIds.value.delete(news.news_id);
      success.value = 'Removed like from this news.';
    } else {
      likedNewsIds.value.add(news.news_id);
      success.value = 'Liked this news.';
    }

    likedNewsIds.value = new Set(likedNewsIds.value);
    news.like_count = response.like_count;
  } catch (actionError) {
    error.value = actionError instanceof Error ? actionError.message : 'Failed to update like';
  }
}

async function handleFollowOrganization(news, event) {
  event.stopPropagation();
  if (!requireAuth()) {
    return;
  }

  error.value = '';
  success.value = '';

  try {
    const orgId = news.organization_id;
    const isFollowing = followedOrganizationIds.value.has(orgId);
    const response = isFollowing ? await unfollowOrganization(orgId) : await followOrganization(orgId);

    if (isFollowing) {
      followedOrganizationIds.value.delete(orgId);
      success.value = 'Unfollowed organization.';
    } else {
      followedOrganizationIds.value.add(orgId);
      success.value = 'Followed organization.';
    }

    followedOrganizationIds.value = new Set(followedOrganizationIds.value);

    newsItems.value.forEach((item) => {
      if (item.organization_id === orgId) {
        item.organization_followers_count = response.followers_count;
      }
    });
  } catch (actionError) {
    error.value = actionError instanceof Error ? actionError.message : 'Failed to update follow state';
  }
}

onMounted(() => {
  void loadNews();
  // start interval if external is selected
  if (dataSource.value === 'external') {
    externalRefreshInterval = setInterval(() => {
      void loadNews();
    }, 60000);
  }
});

// Watch for dataSource changes to manage external refresh interval
const stopOnDataSourceChange = () => {
  if (externalRefreshInterval) {
    clearInterval(externalRefreshInterval);
    externalRefreshInterval = null;
  }
  if (dataSource.value === 'external') {
    externalRefreshInterval = setInterval(() => {
      void loadNews();
    }, 60000);
  }
};

// Simple reactive effect: run when dataSource changes
watchEffect(() => {
  // read value to track
  void dataSource.value;
  stopOnDataSourceChange();
});

onUnmounted(() => {
  if (externalRefreshInterval) {
    clearInterval(externalRefreshInterval);
    externalRefreshInterval = null;
  }
});
</script>

<template>
  <section class="page news-page">
    <div class="page__hero">
      <span class="page__kicker">News</span>
      <h1 class="page__title">News feed.</h1>
      <p class="page__copy">All news articles are visible here for everyone, with authors shown on each item.</p>
    </div>

    <article class="panel panel--soft news-feed">
      <div style="display:flex;align-items:center;justify-content:space-between;gap:1rem;flex-wrap:wrap;">
        <div>
          <h2 class="panel__title">Latest news</h2>
          <p class="panel__meta">{{ filteredNewsItems.length }} articles</p>
        </div>
        <button class="btn" type="button" :disabled="loading" @click="loadNews">Refresh</button>
      </div>

      <div class="news-filters" style="display:flex;gap:0.75rem;margin:0.75rem 0;flex-wrap:wrap;align-items:center;">
        <input class="input" placeholder="Search title, content, category or date" v-model="searchQuery" @input="currentPage = 1" />

        <select class="select" v-model="filterCategory" style="width:auto;min-width:160px;" @change="currentPage = 1">
          <option value="">All categories</option>
          <option v-for="c in availableCategories" :key="c" :value="c">{{ c }}</option>
        </select>

        <input class="input" type="date" v-model="filterDate" style="width:auto;min-width:160px;" @change="currentPage = 1" />

        <div style="display:flex;gap:0.4rem;align-items:center;">
          <button
            type="button"
            class="nav-link"
            :class="{ 'nav-link--active': dataSource === 'system' }"
            @click="(dataSource = 'system', currentPage = 1, loadNews())"
          >System data</button>

          <button
            type="button"
            class="nav-link"
            :class="{ 'nav-link--active': dataSource === 'mock' }"
            @click="(dataSource = 'mock', currentPage = 1, loadNews())"
          >Mock data</button>

          <button
            type="button"
            class="nav-link"
            :class="{ 'nav-link--active': dataSource === 'external' }"
            @click="(dataSource = 'external', currentPage = 1, loadNews())"
          >External data</button>
        </div>

        <input v-if="dataSource === 'external'" class="input" placeholder="External API URL" v-model="externalApiUrl" style="min-width:340px;" />

        <label style="margin-left:auto;display:flex;align-items:center;gap:0.5rem;">Page size:
          <select class="select" v-model.number="pageSize" @change="currentPage = 1">
            <option :value="5">5</option>
            <option :value="10">10</option>
          </select>
        </label>
      </div>

      <p v-if="error" class="panel__notice notice--error">{{ error }}</p>
      <p v-if="success" class="panel__notice notice--success">{{ success }}</p>

      <div v-if="paginatedItems.length" class="news-list">
        <article v-for="news in paginatedItems" :key="news.news_id" class="news-card" @click="openNewsDetail(news.news_id)">
          <img v-if="news.image_url" :src="news.image_url" alt="" class="news-card__image" />
          <div class="news-card__header">
            <div>
              <h3 class="news-card__title">{{ news.title }}</h3>
              <p class="news-card__meta">
                {{ news.organization_name }} · {{ news.status }} · {{ news.published_at ? new Date(news.published_at).toLocaleString() : 'Draft' }}
              </p>
            </div>
            <span class="page__kicker" style="padding: 0.35rem 0.55rem;">#{{ news.news_id }}</span>
          </div>

          <div class="news-stats">
            <span class="badge">Likes: {{ news.like_count }}</span>
            <span class="badge">Comments: {{ news.comment_count }}</span>
            <span class="badge">Followers: {{ news.organization_followers_count }}</span>
          </div>

          <p class="news-card__content">{{ news.content }}</p>

          <div class="news-authors">
            <span v-for="author in news.authors" :key="author.user_id" class="news-author-chip">
              {{ author.email }}
            </span>
          </div>

          <div v-if="news.categories?.length" class="news-categories">
            <span v-for="category in news.categories" :key="category.category_id" class="news-category-chip">
              {{ category.name }}
            </span>
          </div>

          <div class="news-actions">
            <button
              class="icon-btn"
              :class="{ 'icon-btn--active': likedNewsIds.has(news.news_id) }"
              type="button"
              @click="handleLike(news, $event)"
            >
              <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                <path d="M12 21s-7.5-4.35-9.6-6.06C.8 12.9 2 8.99 5 7.2 7.2 5.9 9.6 6 12 8.04 14.4 6 16.8 5.9 19 7.2c3 1.8 4.2 5.7 2.6 7.74C19.5 16.65 12 21 12 21z"/>
              </svg>
              <span class="tooltip">{{ likedNewsIds.has(news.news_id) ? 'Unlike this content' : 'Like this content' }}</span>
            </button>

            <button
              class="icon-btn"
              :class="{ 'icon-btn--active': followedOrganizationIds.has(news.organization_id) }"
              type="button"
              @click="handleFollowOrganization(news, $event)"
            >
              <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                <path d="M12 2a7 7 0 100 14 7 7 0 000-14zm0 16c-4.42 0-8 1.79-8 4v2h16v-2c0-2.21-3.58-4-8-4z"/>
              </svg>
              <span class="tooltip">{{ followedOrganizationIds.has(news.organization_id) ? 'Unfollow this organization' : 'Follow this organization' }}</span>
            </button>

            <button class="btn btn--primary" type="button" @click="openNewsDetail(news.news_id)">
              View detail
            </button>
          </div>
        </article>

        <div v-if="filteredNewsItems.length" class="news-pagination" style="display:flex;gap:0.5rem;align-items:center;justify-content:center;margin-top:1rem;">
          <button class="btn" :disabled="currentPage <= 1" @click.prevent="currentPage = Math.max(1, currentPage - 1)">Prev</button>
          <span>Page {{ currentPage }} / {{ Math.max(1, Math.ceil(filteredNewsItems.length / pageSize)) }}</span>
          <button class="btn" :disabled="currentPage >= Math.ceil(filteredNewsItems.length / pageSize)" @click.prevent="currentPage = Math.min(Math.ceil(filteredNewsItems.length / pageSize), currentPage + 1)">Next</button>
        </div>
      </div>

      <div v-else class="news-empty">
        {{ loading ? 'Loading news...' : 'No news found yet.' }}
      </div>
    </article>
  </section>
</template>