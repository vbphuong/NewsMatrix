<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue';
import { useRoute } from 'vue-router';

import { isAuthenticated } from '../lib/auth';
import {
  createNewsComment,
  fetchMyNewsInteractions,
  fetchNewsComments,
  fetchNewsDetail,
  likeNews,
  unlikeNews,
} from '../lib/backend-news';
import {
  followOrganization,
  unfollowOrganization,
} from '../lib/backend-organization';
import '../assets/news-detail-page.css';

const route = useRoute();

const news = ref(null);
const comments = ref([]);
const loading = ref(false);
const submittingComment = ref(false);
const error = ref('');
const success = ref('');

const likedNewsIds = ref(new Set());
const followedOrganizationIds = ref(new Set());

const commentForm = reactive({
  content: '',
});

const newsId = computed(() => Number(route.params.newsId));
const isPublished = computed(() => news.value?.status?.toLowerCase() === 'published');
const hasLiked = computed(() => likedNewsIds.value.has(newsId.value));
const isFollowingOrganization = computed(() => {
  if (!news.value) {
    return false;
  }
  return followedOrganizationIds.value.has(news.value.organization_id);
});

function requireAuth() {
  if (!isAuthenticated.value) {
    window.alert('You need to login to use this feature.');
    return false;
  }
  return true;
}

async function loadInteractionsIfAuthenticated() {
  if (!isAuthenticated.value) {
    likedNewsIds.value = new Set();
    followedOrganizationIds.value = new Set();
    return;
  }

  const interactions = await fetchMyNewsInteractions();
  likedNewsIds.value = new Set(interactions.liked_news_ids ?? []);
  followedOrganizationIds.value = new Set(interactions.followed_organization_ids ?? []);
}

async function loadNewsDetail() {
  loading.value = true;
  error.value = '';

  try {
    news.value = await fetchNewsDetail(newsId.value);
    if (isPublished.value) {
      comments.value = await fetchNewsComments(newsId.value);
    } else {
      comments.value = [];
    }
    await loadInteractionsIfAuthenticated();
  } catch (loadError) {
    error.value = loadError instanceof Error ? loadError.message : 'Failed to load news detail';
  } finally {
    loading.value = false;
  }
}

async function handleLike() {
  if (!requireAuth() || !isPublished.value) {
    return;
  }

  try {
    if (hasLiked.value) {
      const response = await unlikeNews(newsId.value);
      likedNewsIds.value.delete(newsId.value);
      likedNewsIds.value = new Set(likedNewsIds.value);
      if (news.value) {
        news.value.like_count = response.like_count;
      }
      success.value = 'Removed like from this news.';
    } else {
      const response = await likeNews(newsId.value);
      likedNewsIds.value.add(newsId.value);
      likedNewsIds.value = new Set(likedNewsIds.value);
      if (news.value) {
        news.value.like_count = response.like_count;
      }
      success.value = 'Liked this news.';
    }
  } catch (actionError) {
    error.value = actionError instanceof Error ? actionError.message : 'Failed to update like';
  }
}

async function handleFollowOrganization() {
  if (!requireAuth() || !news.value || !isPublished.value) {
    return;
  }

  try {
    if (isFollowingOrganization.value) {
      const response = await unfollowOrganization(news.value.organization_id);
      followedOrganizationIds.value.delete(news.value.organization_id);
      followedOrganizationIds.value = new Set(followedOrganizationIds.value);
      news.value.organization_followers_count = response.followers_count;
      success.value = 'Unfollowed organization.';
    } else {
      const response = await followOrganization(news.value.organization_id);
      followedOrganizationIds.value.add(news.value.organization_id);
      followedOrganizationIds.value = new Set(followedOrganizationIds.value);
      news.value.organization_followers_count = response.followers_count;
      success.value = 'Followed organization.';
    }
  } catch (actionError) {
    error.value = actionError instanceof Error ? actionError.message : 'Failed to update follow state';
  }
}

async function submitComment() {
  if (!requireAuth() || !isPublished.value) {
    return;
  }

  const content = commentForm.content.trim();
  if (!content) {
    error.value = 'Comment content is required.';
    return;
  }

  submittingComment.value = true;
  error.value = '';

  try {
    const comment = await createNewsComment(newsId.value, { content });
    comments.value = [...comments.value, comment];
    commentForm.content = '';
    if (news.value) {
      news.value.comment_count = comments.value.length;
    }
    success.value = 'Comment added successfully.';
  } catch (submitError) {
    error.value = submitError instanceof Error ? submitError.message : 'Failed to add comment';
  } finally {
    submittingComment.value = false;
  }
}

watch(
  () => route.params.newsId,
  () => {
    success.value = '';
    commentForm.content = '';
    void loadNewsDetail();
  },
);

onMounted(() => {
  void loadNewsDetail();
});
</script>

<template>
  <section class="page news-detail-page">
    <article v-if="news" class="panel panel--soft news-detail-card">
      <span class="page__kicker">News Detail</span>
      <h1 class="page__title news-detail-title">{{ news.title }}</h1>
      <p class="panel__meta">
        {{ news.organization_name }} · {{ news.status }} ·
        {{ news.published_at ? new Date(news.published_at).toLocaleString() : 'Draft' }}
      </p>

      <div class="news-detail-stats">
        <span class="badge">Likes: {{ news.like_count }}</span>
        <span class="badge">Comments: {{ news.comment_count }}</span>
        <span class="badge">Followers: {{ news.organization_followers_count }}</span>
      </div>

      <div v-if="news.categories?.length" class="news-detail-categories">
        <span v-for="category in news.categories" :key="category.category_id" class="news-detail-category-chip">
          {{ category.name }}
        </span>
      </div>

      <p class="news-detail-content">{{ news.content }}</p>

      <div class="news-detail-actions">
          <button
            class="icon-btn"
            :class="{ 'icon-btn--active': hasLiked }"
            type="button"
            :disabled="!isPublished"
            @click="handleLike"
            :aria-pressed="hasLiked.toString()"
            :title="hasLiked ? 'Unlike' : 'Like'"
          >
            <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d="M12 21s-7.5-4.35-9.6-6.06C.8 12.9 2 8.99 5 7.2 7.2 5.9 9.6 6 12 8.04 14.4 6 16.8 5.9 19 7.2c3 1.8 4.2 5.7 2.6 7.74C19.5 16.65 12 21 12 21z"/>
            </svg>
            <span class="tooltip">{{ hasLiked ? 'Unlike this content' : 'Like this content' }}</span>
          </button>

          <button
            class="icon-btn"
            :class="{ 'icon-btn--active': isFollowingOrganization }"
            type="button"
            :disabled="!isPublished"
            @click="handleFollowOrganization"
            :aria-pressed="isFollowingOrganization.toString()"
            :title="isFollowingOrganization ? 'Unfollow organization' : 'Follow organization'"
          >
            <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d="M12 2a7 7 0 100 14 7 7 0 000-14zm0 16c-4.42 0-8 1.79-8 4v2h16v-2c0-2.21-3.58-4-8-4z"/>
            </svg>
            <span class="tooltip">{{ isFollowingOrganization ? 'Unfollow this organization' : 'Follow this organization' }}</span>
          </button>
      </div>

      <p v-if="!isPublished" class="panel__notice">This news is draft. Interaction is enabled only for published news.</p>
      <p v-if="error" class="panel__notice notice--error">{{ error }}</p>
      <p v-if="success" class="panel__notice notice--success">{{ success }}</p>
    </article>

    <article class="panel panel--soft news-comment-panel">
      <h2 class="panel__title">Comments</h2>
      <p class="panel__meta">Readers can discuss published news here.</p>

      <form class="form" @submit.prevent="submitComment">
        <label class="label">
          <span class="label__text">Add comment</span>
          <textarea
            v-model="commentForm.content"
            class="input"
            rows="3"
            placeholder="Share your thoughts"
            :disabled="!isPublished"
          />
        </label>
        <button class="btn btn--primary" type="submit" :disabled="submittingComment || !isPublished">Post comment</button>
      </form>

      <div class="news-comment-list">
        <article v-for="comment in comments" :key="comment.comment_id" class="news-comment-item">
          <div class="news-comment-head">
            <strong>{{ comment.user_email }}</strong>
            <span>{{ comment.created_at ? new Date(comment.created_at).toLocaleString() : '' }}</span>
          </div>
          <p>{{ comment.content }}</p>
        </article>
        <p v-if="!comments.length" class="panel__meta">No comments yet.</p>
      </div>
    </article>
  </section>
</template>
